"""Community stats: GET community/stats/ (forum home redesign, task 3; spec
2026-11-02 §6.3).

The "Who's online" panel. The counts are site-wide, one value for every
viewer, cached server-side as one shared dict: members online, registered
members, and live topics/posts in the fully public boards only (visible to a
guest, no password, no permission grant). ``online_sample`` and
``newest_member`` are built per request after the viewer's block/mute filter,
so they are never cached, and the response is always ``private, no-store``.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.models import (
    ForumGrant,
    ForumProfile,
    ForumRole,
    Post,
    Topic,
    UserBlock,
    UserMute,
)
from wagtail_forum.services.forum_permissions import set_grant
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

URL = "/forum/community/stats/"
# An obviously fake test value.
PASSWORD = "fake-test-password-stats"  # pragma: allowlist secret

# A member viewer with a warm counts cache and a throttled presence touch:
# the has_perm moderator check (user perms, group perms), the online sample,
# the newest member.
EXPECTED_QUERIES = 4


@pytest.fixture(autouse=True)
def _clear_cache():
    # The counts live under one fixed shared key; without this, test order
    # would decide what a test reads.
    cache.clear()
    yield
    cache.clear()


def _profile(username, *, seen_minutes_ago=None, active=True, joined_days_ago=None):
    user = User.objects.create_user(username=username, is_active=active)
    if joined_days_ago is not None:
        User.objects.filter(pk=user.pk).update(
            date_joined=timezone.now() - datetime.timedelta(days=joined_days_ago)
        )
    last_seen = None
    if seen_minutes_ago is not None:
        last_seen = timezone.now() - datetime.timedelta(minutes=seen_minutes_ago)
    ForumProfile.objects.create(user=user, last_seen=last_seen)
    return user


def _viewer(username="viewer"):
    """A member with no ForumProfile, so they never count themselves."""
    user = User.objects.create_user(username=username)
    client = APIClient()
    client.force_authenticate(user)
    return user, client


def _topic_with_posts(board, slug, replies=0):
    author, _ = User.objects.get_or_create(username="author")
    topic = Topic.objects.create(
        board=board,
        title=slug,
        slug=slug,
        author=author,
        live=True,
        last_post_at=timezone.now(),
    )
    for i in range(replies + 1):
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=i == 0,
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )
    return topic


def test_community_stats_counts():
    for name in ("a", "b", "c"):
        _profile(name, seen_minutes_ago=1)
    _profile("away", seen_minutes_ago=60)
    _profile("gone", seen_minutes_ago=1, active=False)
    User.objects.create_user(username="no_profile")

    resp = APIClient().get(URL)

    assert resp.status_code == 200
    assert resp.data["members_online"] == 3
    assert resp.data["registered_members"] == 4
    assert set(resp.data) == {
        "members_online",
        "online_sample",
        "registered_members",
        "topic_count",
        "post_count",
        "newest_member",
    }


def test_community_stats_counts_only_public_boards():
    public = make_forum(name="Public", slug="public")
    _topic_with_posts(public, "pub-1", replies=2)  # 1 topic, 3 posts
    _topic_with_posts(public, "pub-2")  # 1 topic, 1 post
    hidden_topic = _topic_with_posts(public, "pub-hidden")
    Topic.objects.filter(pk=hidden_topic.pk).update(live=False)
    dead_post = Post.objects.filter(topic__slug="pub-1").last()
    Post.objects.filter(pk=dead_post.pk).update(live=False)  # 2 live posts left

    locked = make_forum(name="Club", slug="club", password_hash=make_password(PASSWORD))
    _topic_with_posts(locked, "club-1", replies=4)
    restricted = make_forum(name="Staff", slug="staff", is_hidden=True)
    _topic_with_posts(restricted, "staff-1", replies=4)
    # A grant that leaves guests reading it keeps the forum public: counted
    # (1 topic, 5 posts). Grants are copied onto new forums from their
    # category, so "has any grant" would drop most public forums.
    granted = make_forum(name="Experts", slug="experts")
    set_grant(granted, ForumGrant.MEMBERS, ForumRole.FULL)
    _topic_with_posts(granted, "experts-1", replies=4)

    anon = APIClient().get(URL)
    assert anon.status_code == 200
    assert anon.data["topic_count"] == 3
    assert anon.data["post_count"] == 8

    # A member who unlocked the password forum gets the same numbers, built
    # fresh rather than read back from the anonymous request's cache entry.
    member = User.objects.create_user(username="member")
    client = APIClient()
    client.force_login(member)  # a real session: the unlock lives in it
    unlocked = client.post(
        "/forum/boards/club/unlock/", {"password": PASSWORD}, format="json"
    )
    assert unlocked.status_code == 200
    assert client.get("/forum/boards/club/topics/").status_code == 200
    cache.clear()

    resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.data["topic_count"] == 3
    assert resp.data["post_count"] == 8


def test_community_stats_excludes_forum_guests_cannot_read():
    public = make_forum(name="Public", slug="public")
    _topic_with_posts(public, "pub-1")
    # Members still read it (their default role), guests do not.
    members_only = make_forum(name="Members", slug="members")
    set_grant(members_only, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    _topic_with_posts(members_only, "members-1", replies=3)
    _, member = _viewer()
    assert member.get("/forum/boards/members/topics/").status_code == 200

    for client in (APIClient(), member):
        cache.clear()
        resp = client.get(URL)
        assert resp.data["topic_count"] == 1
        assert resp.data["post_count"] == 1


def test_community_stats_online_count_never_below_sample():
    first = _profile("first", seen_minutes_ago=1)
    second = _profile("second")
    # Warms the counts cache with one member online.
    assert APIClient().get(URL).data["members_online"] == 1

    ForumProfile.objects.filter(user=second).update(last_seen=timezone.now())

    resp = APIClient().get(URL)
    assert [a["username"] for a in resp.data["online_sample"]] == [
        second.username,
        first.username,
    ]
    assert resp.data["members_online"] == 2


def test_community_stats_online_sample_limit_and_order():
    for i in range(7):
        _profile(f"m{i}", seen_minutes_ago=i + 1)
    _profile("away", seen_minutes_ago=60)

    resp = APIClient().get(URL)

    assert resp.data["members_online"] == 7
    assert [a["username"] for a in resp.data["online_sample"]] == [
        "m0",
        "m1",
        "m2",
        "m3",
        "m4",
    ]
    first = resp.data["online_sample"][0]
    assert set(first) == {"username", "display_name", "avatar", "trust_level", "title"}


def test_community_stats_online_sample_skips_inactive():
    _profile("gone", seen_minutes_ago=1, active=False)
    _profile("here", seen_minutes_ago=2)

    resp = APIClient().get(URL)

    assert [a["username"] for a in resp.data["online_sample"]] == ["here"]


def test_community_stats_hides_blocked_and_muted():
    viewer, client = _viewer()
    blocked = _profile("blocked", seen_minutes_ago=1)
    muted = _profile("muted", seen_minutes_ago=2)
    _profile("friend", seen_minutes_ago=3)
    UserBlock.objects.create(blocker=viewer, blocked=blocked)
    UserMute.objects.create(muter=viewer, muted=muted)

    resp = client.get(URL)

    assert resp.status_code == 200
    assert [a["username"] for a in resp.data["online_sample"]] == ["friend"]
    # The count is site-wide: the viewer's filter never touches it.
    assert resp.data["members_online"] == 3


def test_community_stats_newest_member_skips_blocked():
    viewer, client = _viewer()
    _profile("old", joined_days_ago=30)
    second = _profile("second", joined_days_ago=2)
    newest = _profile("newest", joined_days_ago=1)
    _profile("inactive_newer", joined_days_ago=0, active=False)
    UserBlock.objects.create(blocker=viewer, blocked=newest)

    assert APIClient().get(URL).data["newest_member"]["username"] == "newest"
    resp = client.get(URL)
    assert resp.data["newest_member"]["username"] == second.username


def test_community_stats_newest_member_null_when_nobody():
    resp = APIClient().get(URL)

    assert resp.status_code == 200
    assert resp.data["newest_member"] is None
    assert resp.data["online_sample"] == []
    assert resp.data["registered_members"] == 0


@override_settings(WAGTAILFORUM_COMMUNITY_STATS_CACHE_SECONDS=60)
def test_community_stats_counts_cached_shared():
    board = make_forum(name="Public", slug="public")
    _topic_with_posts(board, "t1")

    first = APIClient().get(URL)
    assert first.data["topic_count"] == 1

    _topic_with_posts(board, "t2")
    _, client = _viewer()
    # Inside the TTL every viewer reads the one shared counts value.
    assert client.get(URL).data["topic_count"] == 1
    assert APIClient().get(URL).data["topic_count"] == 1

    cache.clear()
    assert APIClient().get(URL).data["topic_count"] == 2


def test_community_stats_per_viewer_filter_not_cached_shared():
    viewer, client = _viewer()
    x = _profile("x", seen_minutes_ago=1)
    _profile("newer_than_x", joined_days_ago=0)
    User.objects.filter(pk=x.pk).update(
        date_joined=timezone.now() + datetime.timedelta(minutes=5)
    )
    UserBlock.objects.create(blocker=viewer, blocked=x)

    a = client.get(URL)
    assert "x" not in [m["username"] for m in a.data["online_sample"]]
    assert a.data["newest_member"]["username"] == "newer_than_x"

    anon = APIClient().get(URL)
    assert "x" in [m["username"] for m in anon.data["online_sample"]]
    assert anon.data["newest_member"]["username"] == "x"


def test_community_stats_is_never_shared_cached():
    _, member = _viewer()
    for client in (APIClient(), member):
        resp = client.get(URL)
        assert resp.status_code == 200
        cache_control = resp["Cache-Control"]
        assert "private" in cache_control
        assert "no-store" in cache_control
        assert "public" not in cache_control
        assert "s-maxage" not in cache_control
        assert "Cookie" in resp["Vary"]
        assert "Authorization" in resp["Vary"]


def test_community_stats_query_count():
    board = make_forum(name="Public", slug="public")
    _topic_with_posts(board, "t1", replies=1)
    for i in range(6):
        _profile(f"m{i}", seen_minutes_ago=i + 1, joined_days_ago=i)
    viewer, client = _viewer()
    # Warms the counts cache and spends the viewer's presence touch.
    assert client.get(URL).status_code == 200
    # A fresh user object, as a real request has: force_authenticate reuses
    # one instance, whose memoised permission cache would hide the has_perm
    # queries every real request pays.
    client.force_authenticate(User.objects.get(pk=viewer.pk))

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(URL)

    assert resp.status_code == 200
    assert len(resp.data["online_sample"]) == 5
    assert len(ctx.captured_queries) == EXPECTED_QUERIES, [
        q["sql"][:120] for q in ctx.captured_queries
    ]
