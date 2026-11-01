"""Watch / Track / Mute per forum (todo 672), the package half.

The new-topic fan-out to watchers lives in the host
(``apps/forum_host/tests/test_new_topic_fanout.py``). Here: the level API,
muting (a muted forum's topics are absent from that member's digest and
Recent feed, nobody else's), and the tracked forum's unread count.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.digest import build_digest
from wagtail_forum.models import (
    ForumSubscription,
    ForumWatchLevel,
    Notification,
    NotificationVerb,
    Post,
    Topic,
    TopicRead,
)
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _topic(forum, author, title, *, minutes_ago=60, replies=3):
    at = timezone.now() - timedelta(minutes=minutes_ago)
    topic = Topic.objects.create(
        board=forum,
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        live=True,
    )
    Topic.objects.filter(pk=topic.pk).update(reply_count=replies, last_post_at=at)
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": f"<p>{title}</p>"}],
    )
    topic.refresh_from_db()
    return topic


def _row(client, forum):
    return next(
        f
        for c in client.get("/forum/categories/").json()["results"]
        for f in c["forums"]
        if f["id"] == forum.pk
    )


# ------------------------------------------------------------------ level API


def test_a_member_sets_reads_and_clears_their_level():
    forum = make_forum(name="Ferns", slug="ferns")
    me = User.objects.create_user(username="me")
    client = _client(me)
    url = "/forum/boards/ferns/subscription/"

    assert client.get(url).json() == {"level": None}
    for level in ForumWatchLevel.values:
        resp = client.put(url, {"level": level}, format="json")
        assert resp.status_code == 200
        assert client.get(url).json() == {"level": level}
    assert ForumSubscription.objects.filter(user=me, forum=forum).count() == 1
    assert _row(client, forum)["watch_level"] == ForumWatchLevel.MUTED

    assert client.put(url, {"level": "loud"}, format="json").status_code == 400
    assert client.delete(url).json() == {"level": None}
    assert not ForumSubscription.objects.filter(user=me).exists()
    # Guests cannot set one; a hidden forum is 404.
    assert APIClient().put(url, {"level": "muted"}, format="json").status_code in (
        401,
        403,
    )
    make_forum(name="Hidden", slug="hidden", is_hidden=True)
    assert (
        client.put(
            "/forum/boards/hidden/subscription/", {"level": "muted"}, format="json"
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------- mute


def test_a_muted_forums_topics_are_absent_from_that_members_digest_and_recent_feed():
    muted = make_forum(name="Muted", slug="muted")
    kept = make_forum(name="Kept", slug="kept")
    me = User.objects.create_user(username="me", email="me@example.com")
    other = User.objects.create_user(username="other")
    friend = User.objects.create_user(username="friend")
    ForumSubscription.objects.create(user=me, forum=muted, level=ForumWatchLevel.MUTED)
    hidden_topic = _topic(muted, friend, "Muted chatter", replies=50)
    _topic(kept, friend, "Kept chatter", replies=5)
    # A reply notification on a muted forum's topic stays out of Watched too.
    Notification.objects.create(
        recipient=me, actor=friend, verb=NotificationVerb.REPLY, topic=hidden_topic
    )

    digest = build_digest(me, timezone.now() - timedelta(days=7))
    assert [t.title for t in digest.trending] == ["Kept chatter"]
    assert digest.watched == []

    def recent(client):
        resp = client.get("/forum/topics/recent/?limit=10")
        assert resp.status_code == 200
        return [t["title"] for t in resp.json()["results"]]

    assert recent(_client(me)) == ["Kept chatter"]
    # Only the member who muted it: others and guests still see it.
    assert set(recent(_client(other))) == {"Kept chatter", "Muted chatter"}
    assert set(recent(APIClient())) == {"Kept chatter", "Muted chatter"}
    other_digest = build_digest(other, timezone.now() - timedelta(days=7))
    assert {t.title for t in other_digest.trending} == {"Kept chatter", "Muted chatter"}


# -------------------------------------------------------------------- track


def test_a_tracked_forum_row_shows_its_unread_count():
    forum = make_forum(name="Ferns", slug="ferns")
    me = User.objects.create_user(username="me")
    friend = User.objects.create_user(username="friend")
    client = _client(me)
    topics = [_topic(forum, friend, f"Topic {n}", minutes_ago=10 + n) for n in range(3)]

    # No level: the has_unread dot only, no count.
    row = _row(client, forum)
    assert row["unread_count"] is None and row["has_unread"] is True

    for level in (
        ForumWatchLevel.TRACKING,
        ForumWatchLevel.WATCHING,
        ForumWatchLevel.WATCHING_FIRST_POST,
    ):
        ForumSubscription.objects.update_or_create(
            user=me, forum=forum, defaults={"level": level}
        )
        assert _row(client, forum)["unread_count"] == 3
    TopicRead.objects.create(user=me, topic=topics[0], last_read_at=timezone.now())
    assert _row(client, forum)["unread_count"] == 2

    ForumSubscription.objects.filter(user=me).update(level=ForumWatchLevel.MUTED)
    assert _row(client, forum)["unread_count"] is None
    # Guests have no read state.
    assert _row(APIClient(), forum)["unread_count"] is None


def test_watch_level_and_unread_count_add_no_query_to_the_category_index():
    me = User.objects.create_user(username="me")
    friend = User.objects.create_user(username="friend")
    client = _client(me)
    forums = [make_forum(name=f"F{n}", slug=f"f{n}") for n in range(2)]
    _topic(forums[0], friend, "First")

    def count():
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/forum/categories/").status_code == 200
        return len(ctx)

    count()  # warm per-process caches (content types, permissions)
    baseline = count()
    for n in range(2, 6):
        forum = make_forum(name=f"F{n}", slug=f"f{n}")
        ForumSubscription.objects.create(
            user=me, forum=forum, level=ForumWatchLevel.TRACKING
        )
        _topic(forum, friend, f"Topic {n}")
    assert count() == baseline
