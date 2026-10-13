"""Send-time eligibility (todo 619, AC1).

A forum event is dispatched (bell rows + queued FCM, browser-push and email
tasks), then the world changes before the worker runs: the post is hidden or
deleted, the topic unpublished, the recipient blocks or mutes the author,
unfollows the topic, turns the channel off or is deactivated. No external
send may go out, on the first run or on a retry, while an untouched control
still gets every channel.

The tasks are captured at enqueue (``.delay`` patched) and then run in
process, the way a worker would run them later.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from apps.core.models import DeliveryIntent
from apps.users.models import PushSubscription
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TopicSubscription,
    UserBlock,
    UserMute,
)

User = get_user_model()

PUSH_ON = {
    "VAPID_PUBLIC_KEY": "BPub",
    "VAPID_PRIVATE_KEY": "priv",  # pragma: allowlist secret
    "VAPID_CLAIMS_EMAIL": "ops@example.com",
}
TASKS = "apps.forum_host.tasks"


def _member(username):
    user = User.objects.create_user(username=username, email=f"{username}@example.com")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = f"token-{username}"
    profile.save(update_fields=["fcm_token"])
    PushSubscription.objects.create(
        user=user,
        endpoint=f"https://fcm.googleapis.com/fcm/send/{username}",
        p256dh_key="BPk-key",
        auth_key="auth-secret",  # pragma: allowlist secret
    )
    return user


def _thread(prefix):
    owner = _member(f"{prefix}owner")
    control = _member(f"{prefix}control")
    replier = _member(f"{prefix}replier")
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title=f"{prefix} forum", slug=f"{prefix}-forum")
    )
    board = index.add_child(
        instance=ForumBoard(title=f"{prefix} board", slug=f"{prefix}-board")
    )
    topic = Topic.objects.create(
        board=board, title="Yellow leaves", slug=f"{prefix}-leaves", author=owner
    )
    TopicSubscription.subscribe(owner, topic)
    TopicSubscription.subscribe(control, topic)
    post = Post.objects.create(
        topic=topic,
        author=replier,
        body=[{"type": "paragraph", "value": "<p>Check the drainage.</p>"}],
    )
    return owner, control, replier, topic, post


def _dispatch(event, capture, **kwargs):
    """Dispatch ``event`` with every enqueue captured: {task name: [call]}."""
    from apps.forum_host.notifications import dispatch

    calls = {}
    names = (
        "send_forum_push",
        "send_forum_push_batch",
        "send_forum_web_push_batch",
        "send_forum_email_batch",
    )
    patches = [patch(f"{TASKS}.{name}.delay") for name in names]
    mocks = [p.start() for p in patches]
    try:
        with capture(execute=True):
            dispatch(event, **kwargs)
    finally:
        for p in patches:
            p.stop()
    for name, mock in zip(names, mocks):
        calls[name] = list(mock.call_args_list)
    return calls


class Sent:
    """Every external send made while running captured tasks."""

    def __init__(self):
        self.fcm_tokens = []
        self.browser_users = []

    @property
    def email_to(self):
        return sorted(m.to[0] for m in mail.outbox)


def _run(calls):
    """Run captured task calls in process, as a worker would, and record the
    sends: FCM tokens, browser-push recipients, email recipients."""
    from apps.forum_host import tasks

    sent = Sent()
    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = lambda message: "ok"

    def fake_web_push(subscription, **kwargs):
        sent.browser_users.append(subscription.user_id)
        return True

    with (
        patch("apps.core.firebase_config.is_firebase_available", return_value=True),
        patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm),
        patch(
            "apps.users.services.NotificationService.send_web_push_notification",
            side_effect=fake_web_push,
        ),
    ):
        for name, task_calls in calls.items():
            for call in task_calls:
                getattr(tasks, name)(*call.args, **call.kwargs)
    sent.fcm_tokens = sorted(c.kwargs["token"] for c in mock_fcm.Message.call_args_list)
    return sent


def _hide_post(owner, replier, topic, post):
    Post.objects.filter(pk=post.pk).update(live=False)


def _delete_post(owner, replier, topic, post):
    Post.objects.filter(pk=post.pk).delete()


def _unpublish_topic(owner, replier, topic, post):
    Topic.objects.filter(pk=topic.pk).update(live=False)


def _block_author(owner, replier, topic, post):
    UserBlock.block(owner, replier)


def _blocked_by_author(owner, replier, topic, post):
    UserBlock.block(replier, owner)


def _mute_author(owner, replier, topic, post):
    UserMute.mute(owner, replier)


def _unfollow(owner, replier, topic, post):
    TopicSubscription.unsubscribe(owner, topic)


def _deactivate(owner, replier, topic, post):
    User.objects.filter(pk=owner.pk).update(is_active=False)


def _forum_notifications_off(owner, replier, topic, post):
    User.objects.filter(pk=owner.pk).update(forum_notifications=False)


def _reply_channels_off(owner, replier, topic, post):
    ForumProfile.objects.filter(user=owner).update(
        notification_preferences={"reply": {"push": False, "email": False}}
    )


CONTENT_CHANGES = [_hide_post, _delete_post, _unpublish_topic]
RECIPIENT_CHANGES = [
    _block_author,
    _blocked_by_author,
    _mute_author,
    _unfollow,
    _deactivate,
    _forum_notifications_off,
    _reply_channels_off,
]


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_an_untouched_reply_reaches_every_channel(django_capture_on_commit_callbacks):
    owner, control, replier, topic, post = _thread("ok")
    calls = _dispatch(
        "reply_added", django_capture_on_commit_callbacks, topic=topic, post=post
    )

    sent = _run(calls)

    assert sent.email_to == [control.email, owner.email]
    assert sent.fcm_tokens == ["token-okcontrol", "token-okowner"]
    assert sorted(sent.browser_users) == sorted([owner.pk, control.pk])


@pytest.mark.django_db
@override_settings(**PUSH_ON)
@pytest.mark.parametrize("change", CONTENT_CHANGES, ids=lambda f: f.__name__)
def test_content_gone_before_send_reaches_nobody(
    change, django_capture_on_commit_callbacks
):
    owner, control, replier, topic, post = _thread("cg")
    calls = _dispatch(
        "reply_added", django_capture_on_commit_callbacks, topic=topic, post=post
    )

    change(owner, replier, topic, post)
    sent = _run(calls)

    assert sent.email_to == []
    assert sent.fcm_tokens == []
    assert sent.browser_users == []


@pytest.mark.django_db
@override_settings(**PUSH_ON)
@pytest.mark.parametrize("change", RECIPIENT_CHANGES, ids=lambda f: f.__name__)
def test_a_recipient_no_longer_eligible_gets_nothing_and_the_control_still_does(
    change, django_capture_on_commit_callbacks
):
    owner, control, replier, topic, post = _thread("rc")
    calls = _dispatch(
        "reply_added", django_capture_on_commit_callbacks, topic=topic, post=post
    )

    change(owner, replier, topic, post)
    sent = _run(calls)

    assert sent.email_to == [control.email]
    assert sent.fcm_tokens == ["token-rccontrol"]
    assert sent.browser_users == [control.pk]


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_mention_rechecks_the_block_at_send_time(django_capture_on_commit_callbacks):
    owner, control, replier, topic, _ = _thread("mn")
    mentioned = _member("mnmentioned")
    post = Post.objects.create(
        topic=topic,
        author=replier,
        body=[
            {
                "type": "paragraph",
                "value": f"<p>@{mentioned.username} @{control.username} look</p>",
            }
        ],
    )
    calls = _dispatch(
        "reply_added", django_capture_on_commit_callbacks, topic=topic, post=post
    )

    UserBlock.block(mentioned, replier)
    sent = _run(
        {
            "send_forum_push_batch": [
                c for c in calls["send_forum_push_batch"] if c.args[0] == "mention"
            ],
            "send_forum_web_push_batch": [
                c for c in calls["send_forum_web_push_batch"] if c.args[0] == "mention"
            ],
        }
    )

    assert sent.fcm_tokens == ["token-mncontrol"]
    assert sent.browser_users == [control.pk]


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_an_accepted_answer_rechecks_content_and_the_acceptor(
    django_capture_on_commit_callbacks,
):
    owner, control, replier, topic, post = _thread("aa")
    calls = _dispatch(
        "answer_accepted",
        django_capture_on_commit_callbacks,
        topic=topic,
        post=post,
        actor=owner,
    )
    assert calls["send_forum_push"] and calls["send_forum_web_push_batch"]

    UserBlock.block(replier, owner)  # the answer's author blocks the acceptor
    sent = _run(calls)

    assert sent.fcm_tokens == []
    assert sent.browser_users == []


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_retry_after_a_transient_failure_is_rechecked_too(
    django_capture_on_commit_callbacks,
):
    """Every channel's retry path: the email and browser outbox rows go back
    to pending on a transient failure, the FCM batch hands a failed device
    to the single task. The post is hidden before any of those retries run:
    none sends, and the outbox rows are finished, not retried again."""
    from apps.core import delivery
    from apps.forum_host import tasks

    owner, control, replier, topic, post = _thread("rt")
    calls = _dispatch(
        "reply_added", django_capture_on_commit_callbacks, topic=topic, post=post
    )

    # First run: SMTP and the push services are down.
    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = ConnectionError("fcm down")
    with (
        patch("apps.core.firebase_config.is_firebase_available", return_value=True),
        patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm),
        patch(
            "apps.users.services.NotificationService.send_web_push_notification",
            return_value=False,
        ),
        patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=ConnectionError("smtp down"),
        ),
        patch(f"{TASKS}.send_forum_push.delay") as handoff,
    ):
        for name in ("send_forum_email_batch", "send_forum_web_push_batch"):
            for call in calls[name]:
                getattr(tasks, name)(*call.args, **call.kwargs)
        for call in calls["send_forum_push_batch"]:
            tasks.send_forum_push_batch(*call.args, **call.kwargs)
    assert mail.outbox == []
    pending = DeliveryIntent.objects.filter(status=DeliveryIntent.Status.PENDING)
    assert pending.count() == 4  # 2 recipients x (email + browser)
    assert handoff.call_count == 2

    Post.objects.filter(pk=post.pk).update(live=False)
    # The backoff has passed.
    pending.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    with (
        patch(f"{TASKS}.send_forum_email_batch.delay") as email_delay,
        patch(f"{TASKS}.send_forum_web_push_batch.delay") as web_delay,
    ):
        delivery.reconcile()
    retries = {
        "send_forum_email_batch": list(email_delay.call_args_list),
        "send_forum_web_push_batch": list(web_delay.call_args_list),
        "send_forum_push": list(handoff.call_args_list),
    }
    assert retries["send_forum_email_batch"] and retries["send_forum_web_push_batch"]

    sent = _run(retries)

    assert sent.email_to == []
    assert sent.fcm_tokens == []
    assert sent.browser_users == []
    assert not DeliveryIntent.objects.filter(
        status=DeliveryIntent.Status.PENDING
    ).exists()
    # The mobile-push rows (todo 624) finished at the hand-off: their retry
    # belongs to send_forum_push, which the recheck above stopped.
    assert set(
        DeliveryIntent.objects.exclude(kind=DeliveryIntent.Kind.FORUM_PUSH)
        .values_list("status", "last_error")
        .distinct()
    ) == {(DeliveryIntent.Status.SUPPRESSED, "content_unavailable")}
