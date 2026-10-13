"""Quiet hours, reply coalescing and read-before-send (todo 624, AC2).

Owner decisions 2026-10-12: quiet hours are opt-in, default 22:00-07:00 in
the client-reported IANA zone (UTC if unknown), held pushes and emails are
released at the window's end, security mail is exempt; replies on one topic
within 10 minutes coalesce into one email/push; nothing goes out externally
for a post the member already read in the app.

Each test dispatches a real reply under a frozen clock, runs the enqueued
send tasks against the outbox rows they wrote, and reads what every channel
actually sent: email (``mail.outbox``), mobile push (the FCM send) and
browser push (the Web Push send). Time then moves on and reconciliation (the
5-minute beat) releases what was held. The window math across zones and DST
is ``wagtail_forum/tests/test_quiet_hours.py``.
"""

import datetime
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from apps.core import delivery
from apps.core.models import DeliveryIntent
from apps.forum_host import tasks
from apps.users.email_verification import deliver_verification_email
from apps.users.models import PushSubscription
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TopicRead,
    TopicSubscription,
)
from wagtail_forum.preferences import merge_preferences

User = get_user_model()
Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status
TASKS = "apps.forum_host.tasks"
UTC = datetime.timezone.utc
PUSH_ON = {
    "VAPID_PUBLIC_KEY": "BPub",
    "VAPID_PRIVATE_KEY": "priv",  # pragma: allowlist secret
    "VAPID_CLAIMS_EMAIL": "ops@example.com",
    "SITE_URL": "https://web.example",
}
# 23:00 MDT on 2026-06-01 (UTC-6): inside a Denver member's 22:00-07:00.
NIGHT = datetime.datetime(2026, 6, 2, 5, 0, tzinfo=UTC)
# 07:00 MDT, when that window ends.
DAWN = datetime.datetime(2026, 6, 2, 13, 0, tzinfo=UTC)
NOON = datetime.datetime(2026, 6, 2, 18, 0, tzinfo=UTC)
CHANNELS = (Kind.FORUM_EMAIL, Kind.FORUM_PUSH, Kind.FORUM_WEB_PUSH)


def _member(username, *, quiet=False, zone="America/Denver", **cells):
    user = User.objects.create_user(username=username, email=f"{username}@example.com")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = f"fcm-{username}"
    profile.quiet_hours_enabled = quiet
    profile.time_zone = zone
    if cells:
        profile.notification_preferences = merge_preferences({}, cells)
    profile.save()
    PushSubscription.objects.create(
        user=user,
        endpoint=f"https://fcm.googleapis.com/fcm/send/{username}",
        p256dh_key="BPk-key",
        auth_key="auth-secret",  # pragma: allowlist secret
    )
    return user


def _topic(prefix, *members):
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title=f"{prefix} forum", slug=f"{prefix}-forum")
    )
    board = index.add_child(
        instance=ForumBoard(title=f"{prefix} board", slug=f"{prefix}-board")
    )
    author = _member(f"{prefix}author")
    topic = Topic.objects.create(
        board=board, title="Root rot", slug=f"{prefix}-rot", author=author
    )
    for member in members:
        TopicSubscription.subscribe(member, topic)
    return topic, author


def _reply(topic, author, text, *, published=None):
    return Post.objects.create(
        topic=topic,
        author=author,
        first_published_at=published,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )


@contextmanager
def _captured():
    """Every task enqueue captured: the dispatch's .delay() calls and a
    coalescing hold's countdown (apply_async)."""
    calls: list = []

    def recorder(task):
        return lambda *args, **kwargs: calls.append((task, args, kwargs))

    def scheduled(task):
        def apply_async(args=(), kwargs=None, **options):
            calls.append((task, tuple(args), dict(kwargs or {})))

        return apply_async

    names = ("send_forum_push_batch", "send_forum_email_batch")
    names += ("send_forum_web_push_batch",)
    with (
        patch(f"{TASKS}.send_forum_push.delay", side_effect=recorder("push_one")),
        patch(
            f"{TASKS}.send_forum_push_batch.delay",
            side_effect=recorder(names[0]),
        ),
        patch(
            f"{TASKS}.send_forum_email_batch.delay",
            side_effect=recorder(names[1]),
        ),
        patch(
            f"{TASKS}.send_forum_web_push_batch.delay",
            side_effect=recorder(names[2]),
        ),
        patch(
            f"{TASKS}.send_forum_push_batch.apply_async",
            side_effect=scheduled(names[0]),
        ),
        patch(
            f"{TASKS}.send_forum_email_batch.apply_async",
            side_effect=scheduled(names[1]),
        ),
        patch(
            f"{TASKS}.send_forum_web_push_batch.apply_async",
            side_effect=scheduled(names[2]),
        ),
    ):
        yield calls


@contextmanager
def _channels_up():
    """FCM and Web Push accept every send; yields what each one sent."""
    sent = SimpleNamespace(fcm=[], web=[])

    def fcm_send(fcm, token, data, content, collapse_key):
        sent.fcm.append((token, data, content))
        return "ok"

    def web_send(subscription, **kwargs):
        sent.web.append((subscription.user_id, kwargs["title"], kwargs["body"]))
        return True

    with (
        patch("apps.core.firebase_config.is_firebase_available", return_value=True),
        patch("apps.core.firebase_config.get_fcm_client", return_value=MagicMock()),
        patch("apps.core.fcm.send_fcm_message", side_effect=fcm_send),
        patch(
            "apps.users.services.NotificationService.send_web_push_notification",
            side_effect=web_send,
        ),
    ):
        yield sent


def _run(calls):
    """Run captured task calls (single pushes included), with every channel
    up; returns what was sent. Follow-on enqueues are captured, not run."""
    runnable = {
        "send_forum_push_batch": tasks.send_forum_push_batch,
        "send_forum_email_batch": tasks.send_forum_email_batch,
        "send_forum_web_push_batch": tasks.send_forum_web_push_batch,
        "push_one": tasks.send_forum_push,
    }
    with _channels_up() as sent, _captured() as later:
        for name, args, kwargs in calls:
            runnable[name](*args, **kwargs)
    sent.later = later
    return sent


def _dispatch_and_run(capture, event, **kwargs):
    from apps.forum_host.notifications import dispatch

    with _captured() as calls, capture(execute=True):
        dispatch(event, **kwargs)
    return _run(calls)


def _reconcile_and_run():
    with _captured() as calls:
        delivery.reconcile()
    return _run(calls)


def _to(sent, user):
    """What ``user`` got, per channel."""
    return SimpleNamespace(
        email=[m for m in mail.outbox if m.to == [user.email]],
        fcm=[s for s in sent.fcm if s[0] == f"fcm-{user.username}"],
        web=[s for s in sent.web if s[0] == user.pk],
    )


def _rows(user, **filters):
    return DeliveryIntent.objects.filter(recipient=user, **filters)


# --- quiet hours ---------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_quiet_hours_hold_every_channel_and_release_at_the_window_end(
    django_capture_on_commit_callbacks,
):
    sleeper = _member("qhsleeper", quiet=True)
    awake = _member("qhawake")  # the control: quiet hours off
    topic, author = _topic("qh", sleeper, awake)

    with freeze_time(NIGHT):
        sent = _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=topic,
            post=_reply(topic, author, "Repot into dry mix"),
        )
    got = _to(sent, sleeper)
    assert (got.email, got.fcm, got.web) == ([], [], [])
    control = _to(sent, awake)
    assert (len(control.email), len(control.fcm), len(control.web)) == (1, 1, 1)
    held = _rows(sleeper)
    assert {row.kind for row in held} == set(CHANNELS)
    assert {(row.status, row.last_error, row.next_attempt_at) for row in held} == {
        (Status.PENDING, delivery.HOLD_QUIET_HOURS, DAWN)
    }
    # A hold is not a failed attempt.
    assert {row.attempts for row in held} == {0}

    # Still night a minute before the end: reconciliation leaves them.
    with freeze_time(DAWN - datetime.timedelta(minutes=1)):
        early = _reconcile_and_run()
    got = _to(early, sleeper)
    assert (got.email, got.fcm, got.web) == ([], [], [])

    # The window has ended: one of each, then nothing left open.
    mail.outbox.clear()
    with freeze_time(DAWN + datetime.timedelta(minutes=1)):
        released = _reconcile_and_run()
    got = _to(released, sleeper)
    assert (len(got.email), len(got.fcm), len(got.web)) == (1, 1, 1)
    assert got.email[0].subject == "New reply in: Root rot"
    assert set(_rows(sleeper).values_list("status", flat=True)) == {Status.SENT}
    assert _to(released, awake).email == []


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_an_unknown_zone_is_utc(django_capture_on_commit_callbacks):
    # 05:00 UTC is inside 22:00-07:00 UTC: held to 07:00 UTC, not Denver's.
    member = _member("qhutc", quiet=True, zone="")
    topic, author = _topic("qhutc", member)

    with freeze_time(NIGHT):
        _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=topic,
            post=_reply(topic, author, "Hello"),
        )

    assert set(_rows(member).values_list("next_attempt_at", flat=True)) == {
        datetime.datetime(2026, 6, 2, 7, 0, tzinfo=UTC)
    }


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_an_accepted_answer_push_is_held_and_released_as_a_solution_push(
    django_capture_on_commit_callbacks,
):
    helper = _member("qhhelper", quiet=True, solution={"email": True})
    topic, asker = _topic("qhsol")
    answer = _reply(topic, helper, "Cut away the mushy roots")

    with freeze_time(NIGHT):
        sent = _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "answer_accepted",
            topic=topic,
            post=answer,
            actor=asker,
        )
    got = _to(sent, helper)
    assert (got.email, got.fcm, got.web) == ([], [], [])
    assert set(_rows(helper).values_list("kind", "last_error")) == {
        (kind, delivery.HOLD_QUIET_HOURS) for kind in CHANNELS
    }

    with freeze_time(DAWN + datetime.timedelta(minutes=1)):
        released = _reconcile_and_run()
    got = _to(released, helper)
    assert [m.subject for m in got.email] == ["Your answer was accepted in: Root rot"]
    [(_, data, content)] = got.fcm
    assert data["event"] == "answer_accepted"
    assert content == (
        'Your answer was accepted in "Root rot"',
        f"{asker.display_name} marked your reply as the answer",
    )
    assert len(got.web) == 1


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_preferences_changed_while_held_are_honoured_at_release(
    django_capture_on_commit_callbacks,
):
    member = _member("qhchange", quiet=True)
    topic, author = _topic("qhchange", member)
    with freeze_time(NIGHT):
        _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=topic,
            post=_reply(topic, author, "Hello"),
        )
    assert _rows(member, status=Status.PENDING).count() == 3

    # During the night the member turns reply email off.
    profile = ForumProfile.for_user(member)
    profile.notification_preferences = merge_preferences(
        profile.notification_preferences, {"reply": {"email": False}}
    )
    profile.save(update_fields=["notification_preferences"])

    with freeze_time(DAWN + datetime.timedelta(minutes=1)):
        released = _reconcile_and_run()
    got = _to(released, member)
    assert got.email == []
    assert (len(got.fcm), len(got.web)) == (1, 1)
    email_row = _rows(member, kind=Kind.FORUM_EMAIL).get()
    assert (email_row.status, email_row.last_error) == (
        Status.SUPPRESSED,
        "preference_off",
    )


@pytest.mark.django_db
@override_settings(**PUSH_ON)
@pytest.mark.urls("plant_community_backend.urls")
def test_turning_quiet_hours_off_releases_what_they_held(
    django_capture_on_commit_callbacks,
):
    member = _member("qhoff", quiet=True)
    topic, author = _topic("qhoff", member)
    with freeze_time(NIGHT):
        _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=topic,
            post=_reply(topic, author, "Hello"),
        )
        assert set(_rows(member).values_list("next_attempt_at", flat=True)) == {DAWN}

    later = NIGHT + datetime.timedelta(hours=1)
    with freeze_time(later):
        client = APIClient()
        client.force_authenticate(member)
        resp = client.patch(
            "/api/v1/forum/me/profile/",
            {"quiet_hours_enabled": False},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        assert set(_rows(member).values_list("next_attempt_at", flat=True)) == {later}

    with freeze_time(later + datetime.timedelta(minutes=5)):
        released = _reconcile_and_run()
    got = _to(released, member)
    assert (len(got.email), len(got.fcm), len(got.web)) == (1, 1, 1)


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_moving_the_window_moves_the_release(django_capture_on_commit_callbacks):
    member = _member("qhmove", quiet=True)
    topic, author = _topic("qhmove", member)
    with freeze_time(NIGHT):
        _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=topic,
            post=_reply(topic, author, "Hello"),
        )
        profile = ForumProfile.for_user(member)
        profile.quiet_hours_end = datetime.time(9, 0)
        profile.save()

    # 09:00 MDT is 15:00 UTC.
    assert set(_rows(member).values_list("next_attempt_at", flat=True)) == {
        datetime.datetime(2026, 6, 2, 15, 0, tzinfo=UTC)
    }


@pytest.mark.django_db
def test_security_mail_is_never_held_by_quiet_hours():
    member = User.objects.create_user(
        username="qhsecurity", email="qhsecurity@example.com"
    )
    profile = ForumProfile.for_user(member)
    profile.quiet_hours_enabled = True
    profile.time_zone = "America/Denver"
    profile.save()

    from apps.core.services.email_service import EmailService, EmailType

    with freeze_time(NIGHT):
        assert deliver_verification_email(member)
        assert EmailService().send_email(
            email_type=EmailType.SECURITY_ALERT,
            recipient=member,
            subject="New sign-in to your account",
            template_name="generic_notification",
            context={"notification_message": "A new sign-in."},
        )
    assert [m.to for m in mail.outbox] == [[member.email]] * 2
    assert not DeliveryIntent.objects.filter(
        last_error=delivery.HOLD_QUIET_HOURS
    ).exists()


# --- coalescing ----------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_rapid_replies_coalesce_into_one_message_per_channel(
    django_capture_on_commit_callbacks,
):
    member = _member("cofollower")
    topic, author = _topic("co", member)

    def reply(at, text):
        with freeze_time(at):
            return _dispatch_and_run(
                django_capture_on_commit_callbacks,
                "reply_added",
                topic=topic,
                post=_reply(topic, author, text),
            )

    # The first reply goes out at once.
    first = reply(NOON, "First")
    got = _to(first, member)
    assert (len(got.email), len(got.fcm), len(got.web)) == (1, 1, 1)
    assert got.email[0].subject == "New reply in: Root rot"

    # Two more inside the 10-minute window: held, nothing sent.
    mail.outbox.clear()
    second = reply(NOON + datetime.timedelta(minutes=2), "Second")
    third = reply(NOON + datetime.timedelta(minutes=4), "Third, the newest")
    for sent in (second, third):
        got = _to(sent, member)
        assert (got.email, got.fcm, got.web) == ([], [], [])
    window_end = NOON + datetime.timedelta(minutes=10)
    held = _rows(member, last_error=delivery.HOLD_COALESCING)
    assert held.count() == 6  # 2 replies x 3 channels
    assert set(held.values_list("next_attempt_at", flat=True)) == {
        held.first().next_attempt_at
    }
    assert held.first().next_attempt_at >= window_end
    # Only the older held reply schedules the fold; the newer one rides it.
    assert len(second.later) == 3 and third.later == []

    # At the window's end: ONE message per channel covering both replies,
    # showing the newest.
    with freeze_time(NOON + datetime.timedelta(minutes=10, seconds=30)):
        folded = _run(second.later)
    got = _to(folded, member)
    assert (len(got.email), len(got.fcm), len(got.web)) == (1, 1, 1)
    assert got.email[0].subject == "2 new replies in: Root rot"
    assert "Third, the newest" in got.email[0].body
    assert got.fcm[0][2] == (
        '2 new replies in "Root rot"',
        f"Latest from {author.display_name}",
    )
    assert got.web[0][1] == '2 new replies in "Root rot"'
    assert set(_rows(member).values_list("status", flat=True)) == {
        Status.SENT,
        Status.SUPPRESSED,
    }
    assert set(
        _rows(member, status=Status.SUPPRESSED).values_list("last_error", flat=True)
    ) == {"coalesced"}

    # A reply right after the fold starts a new window: held again.
    mail.outbox.clear()
    fourth = reply(NOON + datetime.timedelta(minutes=11), "Fourth")
    assert _to(fourth, member).email == []


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_replies_on_another_topic_are_not_coalesced(django_capture_on_commit_callbacks):
    member = _member("coother")
    one, author_one = _topic("coone", member)
    two, author_two = _topic("cotwo", member)

    with freeze_time(NOON):
        _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=one,
            post=_reply(one, author_one, "On one"),
        )
    mail.outbox.clear()
    with freeze_time(NOON + datetime.timedelta(minutes=1)):
        sent = _dispatch_and_run(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=two,
            post=_reply(two, author_two, "On two"),
        )
    got = _to(sent, member)
    assert (len(got.email), len(got.fcm), len(got.web)) == (1, 1, 1)


# --- read before send ----------------------------------------------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_post_read_in_the_app_is_not_sent_externally(
    django_capture_on_commit_callbacks,
):
    # Members who joined before the reply: a new account's read watermark
    # is its join time, which would cover an older post.
    with freeze_time(NIGHT - datetime.timedelta(days=1)):
        reader = _member("rbsreader", quiet=True)
        unread = _member("rbsunread", quiet=True)
        topic, author = _topic("rbs", reader, unread)

    with freeze_time(NIGHT):
        post = _reply(topic, author, "Overnight reply", published=NIGHT)
        _dispatch_and_run(
            django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
        )
    # Held overnight; in the morning the reader opens the topic in the app.
    TopicRead.mark_read(reader, topic.pk, when=DAWN - datetime.timedelta(minutes=30))

    with freeze_time(DAWN + datetime.timedelta(minutes=1)):
        released = _reconcile_and_run()
    got = _to(released, reader)
    assert (got.email, got.fcm, got.web) == ([], [], [])
    assert set(_rows(reader).values_list("status", "last_error")) == {
        (Status.SUPPRESSED, "already_read")
    }
    got = _to(released, unread)
    assert (len(got.email), len(got.fcm), len(got.web)) == (1, 1, 1)


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_read_bell_row_stops_the_send(django_capture_on_commit_callbacks):
    from wagtail_forum.models import Notification

    member = _member("rbsbell")
    topic, author = _topic("rbsbell", member)
    post = _reply(topic, author, "Hi")
    from apps.forum_host.notifications import dispatch

    with _captured() as calls, django_capture_on_commit_callbacks(execute=True):
        dispatch("reply_added", topic=topic, post=post)
    # Read in the app before the worker picks the tasks up.
    Notification.objects.filter(recipient=member, post=post).update(
        read_at=datetime.datetime.now(tz=UTC)
    )
    got = _to(_run(calls), member)
    assert (got.email, got.fcm, got.web) == ([], [], [])
