"""New-topic fan-out to forum watchers (todo 672).

Owner decisions: Discourse's four levels; a new topic notifies members
watching the forum or its first posts in-app and by push (its own
``new_topic`` preference row, push on, no email); ``watching`` also follows
the topic so its replies notify. The author never notifies themselves, and
the fan-out costs a fixed number of queries whatever the number of watchers.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from wagtail_forum.models import (
    ForumGrant,
    ForumRole,
    ForumSubscription,
    ForumWatchLevel,
    Notification,
    NotificationVerb,
    Post,
    Topic,
    TopicSubscription,
    UserBlock,
)
from wagtail_forum.preferences import NOTIFICATION_MATRIX, default_preferences
from wagtail_forum.services.forum_permissions import set_grant
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = pytest.mark.django_db

_counter = iter(range(10_000))


def _topic(forum, author):
    n = next(_counter)
    topic = Topic.objects.create(
        board=forum,
        title=f"New topic {n}",
        slug=f"new-topic-{n}",
        author=author,
        live=True,
    )
    opening = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>Look at this fern.</p>"}],
    )
    return topic, opening


def _dispatch(captured, topic, opening):
    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as email,
    ):
        from apps.forum_host.notifications import dispatch

        with captured(execute=True):
            dispatch("topic_created", topic=topic, post=opening)
    return push, email


def _watch(user, forum, level):
    ForumSubscription.objects.create(user=user, forum=forum, level=level)


def test_a_watcher_gets_one_notification_per_new_topic_and_the_author_none(
    django_capture_on_commit_callbacks,
):
    forum = make_forum(name="Ferns", slug="ferns")
    author = User.objects.create_user(username="author")
    watcher = User.objects.create_user(username="watcher")
    first_post = User.objects.create_user(username="first-post")
    tracker = User.objects.create_user(username="tracker")
    muter = User.objects.create_user(username="muter")
    _watch(author, forum, ForumWatchLevel.WATCHING)  # the author watches too
    _watch(watcher, forum, ForumWatchLevel.WATCHING)
    _watch(first_post, forum, ForumWatchLevel.WATCHING_FIRST_POST)
    _watch(tracker, forum, ForumWatchLevel.TRACKING)
    _watch(muter, forum, ForumWatchLevel.MUTED)

    for _ in range(2):
        topic, opening = _topic(forum, author)
        push, email = _dispatch(django_capture_on_commit_callbacks, topic, opening)
        rows = Notification.objects.filter(verb=NotificationVerb.NEW_TOPIC, topic=topic)
        assert sorted(rows.values_list("recipient__username", flat=True)) == [
            "first-post",
            "watcher",
        ]
        # The author never notifies themselves.
        assert not rows.filter(recipient=author).exists()
        # One push batch for the watchers, with its own event; no email.
        new_topic_calls = [c for c in push.call_args_list if c.args[0] == "new_topic"]
        assert len(new_topic_calls) == 1
        assert sorted(new_topic_calls[0].args[1]) == sorted([watcher.pk, first_post.pk])
        assert not email.called
        # `watching` follows the topic; `watching_first_post` does not.
        followers = set(
            TopicSubscription.objects.filter(topic=topic).values_list(
                "user__username", flat=True
            )
        )
        assert "watcher" in followers and "first-post" not in followers

    # One row per watcher per new topic, and re-firing the event adds none.
    assert (
        Notification.objects.filter(
            recipient=watcher, verb=NotificationVerb.NEW_TOPIC
        ).count()
        == 2
    )
    _dispatch(django_capture_on_commit_callbacks, topic, opening)
    assert (
        Notification.objects.filter(
            recipient=watcher, verb=NotificationVerb.NEW_TOPIC
        ).count()
        == 2
    )


def test_a_watcher_mentioned_in_the_opening_post_still_follows_the_topic(
    django_capture_on_commit_callbacks,
):
    """The mention alert replaces the watcher's new_topic alert, not their
    subscription: `watching` = every post, so the replies must notify too."""
    forum = make_forum(name="Mosses", slug="mosses")
    author = User.objects.create_user(username="m_author")
    watcher = User.objects.create_user(username="m_watcher")
    _watch(watcher, forum, ForumWatchLevel.WATCHING)
    topic = Topic.objects.create(
        board=forum, title="Moss", slug="moss", author=author, live=True
    )
    opening = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": f"<p>@{watcher.username} look</p>"}],
    )

    _dispatch(django_capture_on_commit_callbacks, topic, opening)

    alerts = Notification.objects.filter(recipient=watcher, topic=topic)
    assert list(alerts.values_list("verb", flat=True)) == [NotificationVerb.MENTION]
    assert TopicSubscription.objects.filter(user=watcher, topic=topic).exists()


def test_watchers_who_cannot_read_or_are_blocked_are_skipped(
    django_capture_on_commit_callbacks,
):
    forum = make_forum(name="Private", slug="private")
    set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    set_grant(forum, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    author = User.objects.create_user(username="author", is_staff=True)
    outsider = User.objects.create_user(username="outsider")
    staff = User.objects.create_user(username="staff-watcher", is_staff=True)
    blocker = User.objects.create_user(username="blocker", is_staff=True)
    UserBlock.objects.create(blocker=blocker, blocked=author)
    for user in (outsider, staff, blocker):
        _watch(user, forum, ForumWatchLevel.WATCHING)

    topic, opening = _topic(forum, author)
    _dispatch(django_capture_on_commit_callbacks, topic, opening)
    recipients = list(
        Notification.objects.filter(
            verb=NotificationVerb.NEW_TOPIC, topic=topic
        ).values_list("recipient__username", flat=True)
    )
    assert recipients == ["staff-watcher"]


def test_fan_out_query_count_is_bounded(django_capture_on_commit_callbacks):
    forum = make_forum(name="Ferns", slug="ferns")
    author = User.objects.create_user(username="author")

    def run(n_watchers):
        for _ in range(n_watchers):
            user = User.objects.create_user(username=f"w{next(_counter)}")
            _watch(user, forum, ForumWatchLevel.WATCHING)
        topic, opening = _topic(forum, author)
        with CaptureQueriesContext(connection) as ctx:
            _dispatch(django_capture_on_commit_callbacks, topic, opening)
        return len(ctx), Notification.objects.filter(topic=topic).count()

    run(1)  # warm per-process caches
    small, small_rows = run(1)
    large, large_rows = run(20)
    assert (small_rows, large_rows) == (2, 22)
    assert large == small, (small, large)


def test_new_topic_preference_row_is_push_only_and_on_by_default():
    assert NOTIFICATION_MATRIX["new_topic"] == ("push",)
    assert default_preferences()["new_topic"] == {"push": True}


def test_new_topic_push_copy_exists():
    from apps.forum_host.notification_copy import email_content, push_content

    title, body = push_content("new_topic", "Fern spores", "ada")
    assert "Fern spores" in title and "ada" in body
    assert email_content("new_topic", "Fern spores", "ada") is None
