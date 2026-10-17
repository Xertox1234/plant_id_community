"""Optional important-event email (todo 624, AC1).

Owner decision 2026-10-12: mention, quote and accepted-answer email are
optional and OFF by default (no silent opt-in), and a mentioned subscriber
gets ONE merged email. These tests dispatch a real event, run the enqueued
email task against the outbox rows it wrote, and read what lands in
``mail.outbox``: who got an email, which one, and what its unsubscribe link
turns off.
"""

import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from apps.core.models import DeliveryIntent
from apps.forum_host import tasks
from apps.users.email_unsubscribe import LISTS, read_token
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TopicSubscription,
)
from wagtail_forum.preferences import merge_preferences, wants_channel

User = get_user_model()
TASKS = "apps.forum_host.tasks"
SITE = {"SITE_URL": "https://web.example", "API_PUBLIC_URL": ""}


@pytest.fixture(autouse=True)
def _web_push_off(settings):
    settings.VAPID_PUBLIC_KEY = ""


def _member(username, **cells):
    user = User.objects.create_user(username=username, email=f"{username}@example.com")
    profile = ForumProfile.for_user(user)
    if cells:
        profile.notification_preferences = merge_preferences({}, cells)
        profile.save(update_fields=["notification_preferences"])
    return user


def _topic(prefix, author):
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title=f"{prefix} forum", slug=f"{prefix}-forum")
    )
    board = index.add_child(
        instance=ForumBoard(title=f"{prefix} board", slug=f"{prefix}-board")
    )
    topic = Topic.objects.create(
        board=board, title="Fungus gnats", slug=f"{prefix}-gnats", author=author
    )
    TopicSubscription.subscribe(author, topic)
    return topic


def _reply(topic, author, text):
    return Post.objects.create(
        topic=topic,
        author=author,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )


def _dispatch(capture, event, **kwargs):
    """Dispatch with every enqueue captured; returns the email task calls."""
    from apps.forum_host.notifications import dispatch

    with (
        patch(f"{TASKS}.send_forum_push_batch.delay"),
        patch(f"{TASKS}.send_forum_push.delay"),
        patch(f"{TASKS}.send_forum_web_push_batch.delay"),
        patch(f"{TASKS}.send_forum_email_batch.delay") as email,
        capture(execute=True),
    ):
        dispatch(event, **kwargs)
    return list(email.call_args_list)


def _run_email(calls):
    for call in calls:
        tasks.send_forum_email_batch(*call.args, **call.kwargs)


def _mail_to(user):
    return [m for m in mail.outbox if m.to == [user.email]]


def _unsubscribe_list(message):
    url = re.search(r"Unsubscribe: (\S+)", message.body).group(1)
    token = parse_qs(urlparse(url).query)["token"][0]
    return read_token(token)


@pytest.mark.django_db
@override_settings(**SITE)
def test_mention_email_is_off_by_default(django_capture_on_commit_callbacks):
    author = _member("ie-author")
    mentioned = _member("iequiet")  # never touched mention email
    topic = _topic("ie-default", author)
    post = _reply(topic, author, "@iequiet have a look")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
        )
    )

    assert _mail_to(mentioned) == []
    row = DeliveryIntent.objects.get(
        kind=DeliveryIntent.Kind.FORUM_EMAIL, recipient=mentioned
    )
    assert (row.event, row.status, row.last_error) == (
        "mention",
        DeliveryIntent.Status.SUPPRESSED,
        "preference_off",
    )


@pytest.mark.django_db
@override_settings(**SITE)
def test_a_mention_email_reaches_a_member_with_no_push_device(
    django_capture_on_commit_callbacks,
):
    author = _member("ie-poster")
    # Opted in to mention email; no FCM token, no PushDevice, no browser.
    mentioned = _member("ienopush", mention={"email": True})
    assert not ForumProfile.for_user(mentioned).fcm_token
    topic = _topic("ie-nopush", author)
    post = _reply(topic, author, "@ienopush thoughts on sticky traps?")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
        )
    )

    [message] = _mail_to(mentioned)
    assert message.subject == "You were mentioned in: Fungus gnats"
    assert "ie-poster" in message.body and "sticky traps" in message.body
    user, list_id = _unsubscribe_list(message)
    assert (user, list_id) == (mentioned, "forum_mention")
    assert message.extra_headers["List-Unsubscribe"].startswith("<https://web.example")


@pytest.mark.django_db
@override_settings(**SITE)
@pytest.mark.parametrize(
    "cells, expected",
    [
        # Mention email on: the mention email, never also the reply email.
        ({"mention": {"email": True}}, ("You were mentioned in", "forum_mention")),
        # Mention email off (the default), reply email on: the reply email
        # they follow the topic for, not nothing.
        ({}, ("New reply in", "forum_reply")),
        # Both off: nothing.
        ({"reply": {"email": False}}, None),
    ],
)
def test_a_mentioned_subscriber_gets_one_email(
    django_capture_on_commit_callbacks, cells, expected
):
    author = _member("ie-op")
    both = _member("ieboth", **cells)
    topic = _topic("ie-both", author)
    TopicSubscription.subscribe(both, topic)
    post = _reply(topic, author, "@ieboth replying with a mention")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
        )
    )

    received = _mail_to(both)
    if expected is None:
        assert received == []
        return
    [message] = received
    subject, list_id = expected
    assert message.subject.startswith(subject)
    # The link turns off the cell that let this email through, nothing else.
    assert _unsubscribe_list(message)[1] == list_id


@pytest.mark.django_db
@override_settings(**SITE)
def test_an_unfollowing_mentioned_member_with_only_reply_email_gets_none(
    django_capture_on_commit_callbacks,
):
    # The reply fallback is for subscribers: a mention of a non-follower whose
    # mention email is off sends nothing, whatever their reply cell says.
    author = _member("ie-op2")
    stranger = _member("iestranger")
    topic = _topic("ie-stranger", author)
    post = _reply(topic, author, "@iestranger hello")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
        )
    )

    assert _mail_to(stranger) == []


@pytest.mark.django_db
@override_settings(**SITE)
def test_quote_and_accepted_answer_emails_follow_their_own_cells(
    django_capture_on_commit_callbacks,
):
    asker = _member("ie-asker")
    helper = _member("ie-helper", quote={"email": True}, solution={"email": True})
    topic = _topic("ie-quote", asker)
    answer = _reply(topic, helper, "Let the soil dry out between waterings.")
    quoting = Post.objects.create(
        topic=topic,
        author=asker,
        body=[
            {
                "type": "post_quote",
                "value": {"post": answer.pk, "text": "Let the soil dry out"},
            },
            {"type": "paragraph", "value": "<p>Worked, thanks!</p>"},
        ],
    )

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks,
            "reply_added",
            topic=topic,
            post=quoting,
        )
    )
    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks,
            "answer_accepted",
            topic=topic,
            post=answer,
            actor=asker,
        )
    )

    subjects = sorted(m.subject for m in _mail_to(helper))
    assert subjects == [
        "Your answer was accepted in: Fungus gnats",
        "Your post was quoted in: Fungus gnats",
    ]
    by_subject = {m.subject: m for m in _mail_to(helper)}
    accepted = by_subject["Your answer was accepted in: Fungus gnats"]
    # The accepted-answer email names who accepted it, not the recipient.
    assert "ie-asker marked your reply as the answer" in accepted.body
    assert _unsubscribe_list(accepted)[1] == "forum_solution"
    assert (
        _unsubscribe_list(by_subject["Your post was quoted in: Fungus gnats"])[1]
        == "forum_quote"
    )


@pytest.mark.django_db
@override_settings(**SITE)
def test_accepted_answer_email_is_off_by_default(django_capture_on_commit_callbacks):
    asker = _member("ie-asker2")
    helper = _member("ie-helper2")
    topic = _topic("ie-solution", asker)
    answer = _reply(topic, helper, "Bottom watering.")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks,
            "answer_accepted",
            topic=topic,
            post=answer,
            actor=asker,
        )
    )

    assert _mail_to(helper) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "list_id, verb",
    [
        ("forum_mention", "mention"),
        ("forum_quote", "quote"),
        ("forum_solution", "solution"),
    ],
)
def test_each_unsubscribe_list_turns_off_only_its_own_cell(list_id, verb):
    user = _member(
        f"ie-unsub-{verb}",
        mention={"email": True},
        quote={"email": True},
        solution={"email": True},
    )
    email_list = LISTS[list_id]
    assert email_list.is_subscribed(user)

    email_list.unsubscribe(user)

    overrides = ForumProfile.for_user(user).notification_preferences
    assert email_list.is_subscribed(user) is False
    assert wants_channel(overrides, verb, "email") is False
    for other in {"mention", "quote", "solution"} - {verb}:
        assert wants_channel(overrides, other, "email") is True
    # The reply cell and the master switch are untouched.
    assert wants_channel(overrides, "reply_added", "email") is True
    user.refresh_from_db()
    assert user.email_notifications is True


@pytest.mark.django_db
@override_settings(**SITE)
def test_the_email_master_switch_stops_important_event_email(
    django_capture_on_commit_callbacks,
):
    author = _member("ie-op3")
    mentioned = _member("iemaster", mention={"email": True})
    User.objects.filter(pk=mentioned.pk).update(email_notifications=False)
    topic = _topic("ie-master", author)
    post = _reply(topic, author, "@iemaster ping")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
        )
    )

    assert _mail_to(mentioned) == []


# --- review round 2 (PR #1132) -------------------------------------------------


@pytest.mark.django_db
@override_settings(**SITE)
@pytest.mark.parametrize("acceptor", [True, False], ids=["acceptor", "no-acceptor"])
def test_the_accepted_answer_email_credits_the_answer_to_its_author(
    django_capture_on_commit_callbacks, acceptor
):
    asker = _member(f"ie-ack-asker-{acceptor}")
    helper = _member(f"ie-ack-helper-{acceptor}", solution={"email": True})
    topic = _topic(f"ie-ack-{acceptor}", asker)
    answer = _reply(topic, helper, "Let the soil dry out between waterings.")

    _run_email(
        _dispatch(
            django_capture_on_commit_callbacks,
            "answer_accepted",
            topic=topic,
            post=answer,
            actor=asker if acceptor else None,
        )
    )

    [message] = _mail_to(helper)
    html = message.alternatives[0][0]
    who = asker.display_name if acceptor else "Someone"
    # The event line names who accepted it; the excerpt is still the
    # recipient's own answer, labelled with its real author.
    assert f"{who} marked your reply as the answer" in message.body
    assert f"{helper.display_name}: Let the soil dry out" in message.body
    assert f"<strong>{helper.display_name}</strong>" in html
    assert f"<strong>{asker.display_name}</strong>" not in html
    # The HTML body carries a visible unsubscribe link (emails/base.html).
    assert ">Unsubscribe</a>" in html


@pytest.mark.django_db
@override_settings(**SITE)
def test_a_read_mention_stops_the_fallback_reply_email(
    django_capture_on_commit_callbacks,
):
    from django.utils import timezone
    from wagtail_forum.models import Notification, NotificationVerb

    author = _member("ie-readop")
    follower = _member("iereader")  # mention email off: the reply fallback
    topic = _topic("ie-read", author)
    TopicSubscription.subscribe(follower, topic)
    post = _reply(topic, author, "@iereader see this")

    calls = _dispatch(
        django_capture_on_commit_callbacks, "reply_added", topic=topic, post=post
    )
    # Read in the app before the worker sends: the bell row is a MENTION.
    assert Notification.objects.filter(
        recipient=follower, post=post, verb=NotificationVerb.MENTION
    ).update(read_at=timezone.now())
    _run_email(calls)

    assert _mail_to(follower) == []
    row = DeliveryIntent.objects.get(
        kind=DeliveryIntent.Kind.FORUM_EMAIL, recipient=follower
    )
    assert (row.status, row.last_error) == (
        DeliveryIntent.Status.SUPPRESSED,
        "already_read",
    )
