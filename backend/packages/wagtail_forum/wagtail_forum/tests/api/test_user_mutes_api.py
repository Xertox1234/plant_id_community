"""Mute (todo 347): the write surface, and what a mute does on every
block-aware surface — one-directionally.

Mirrors test_user_blocks_api.py for the endpoints, then pins the contract
that makes a mute different from a block: the MUTER stops seeing the muted
member's content (posts collapse, topics/search/experts/notifications hide,
profile activity empties), the MUTED member notices nothing (their view of
the muter is unchanged, their mentions and DMs still land), and — like
blocks — a moderator's own mutes are inert.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Message,
    NotificationVerb,
    Post,
    Topic,
    UserMute,
)
from wagtail_forum.notifications import create_notifications

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _topic(board, author, slug, title="Monstera propagation tips"):
    topic = Topic.objects.create(
        board=board, title=title, slug=slug, author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>propagation tips</p>"}],
    )
    return topic


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _moderator(username):
    user = User.objects.create_user(username=username)
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtail_forum", codename="change_post"
        )
    )
    return user


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_mute_creates_row_and_is_idempotent():
    muter = User.objects.create_user(username="muter1")
    target = User.objects.create_user(username="target1")

    client = _client(muter)
    first = client.post(f"/forum/users/{target.username}/mute/")
    second = client.post(f"/forum/users/{target.username}/mute/")

    assert first.status_code == 200 and first.data == {"muted": True}
    assert second.status_code == 200
    assert UserMute.objects.filter(muter=muter, muted=target).count() == 1


@pytest.mark.django_db
def test_unmute_removes_row_and_survives_a_missing_row_or_deactivated_target():
    muter = User.objects.create_user(username="muter2")
    target = User.objects.create_user(username="target2")
    UserMute.mute(muter, target)
    target.is_active = False
    target.save(update_fields=["is_active"])

    client = _client(muter)
    resp = client.delete(f"/forum/users/{target.username}/mute/")
    again = client.delete(f"/forum/users/{target.username}/mute/")

    assert resp.status_code == 200 and resp.data == {"muted": False}
    assert again.status_code == 200
    assert not UserMute.objects.filter(muter=muter).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("target_state", ["self", "missing", "inactive"])
def test_mute_rejects_self_missing_and_inactive_targets(target_state):
    muter = User.objects.create_user(username=f"muter3-{target_state}")
    if target_state == "self":
        username, expected = muter.username, 400
    elif target_state == "missing":
        username, expected = "nobody-here", 404
    else:
        User.objects.create_user(username="inactive-target", is_active=False)
        username, expected = "inactive-target", 404

    resp = _client(muter).post(f"/forum/users/{username}/mute/")

    assert resp.status_code == expected
    assert not UserMute.objects.exists()


@pytest.mark.django_db
def test_mute_endpoints_require_authentication():
    User.objects.create_user(username="target4")
    anon = _client()
    assert anon.post("/forum/users/target4/mute/").status_code == 401
    assert anon.delete("/forum/users/target4/mute/").status_code == 401
    assert anon.get("/forum/me/mutes/").status_code == 401


@pytest.mark.django_db
def test_my_mutes_lists_only_the_callers_mutes_newest_first():
    muter = User.objects.create_user(username="muter5")
    other = User.objects.create_user(username="other5")
    a = User.objects.create_user(username="a5")
    b = User.objects.create_user(username="b5")
    UserMute.mute(muter, a)
    UserMute.mute(muter, b)
    UserMute.mute(other, a)

    resp = _client(muter).get("/forum/me/mutes/")

    assert resp.status_code == 200
    assert [row["username"] for row in resp.data] == ["b5", "a5"]
    assert all("muted_at" in row for row in resp.data)


# --------------------------------------------------------------------------
# What a mute does — for the muter
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_post_list_flags_a_muted_author_as_muted_not_blocked_without_hiding():
    """COLLAPSE like a block (thread continuity), but its own flag so the
    client renders "muted" affordances, not "blocked" ones."""
    board = _board()
    author = User.objects.create_user(username="muted-author")
    viewer = User.objects.create_user(username="muter6")
    topic = _topic(board, author, "t6")
    UserMute.mute(viewer, author)

    resp = _client(viewer).get(f"/forum/topics/{topic.id}/posts/")

    row = resp.data["results"][0]
    assert row["is_muted"] is True
    assert row["is_blocked"] is False
    assert row["can_mute"] is True
    assert row["author"]["username"] == author.username  # not redacted
    assert row["body"]


@pytest.mark.django_db
def test_topic_detail_flags_a_muted_author():
    board = _board()
    author = User.objects.create_user(username="muted-author7")
    viewer = User.objects.create_user(username="muter7")
    topic = _topic(board, author, "t7")
    UserMute.mute(viewer, author)

    resp = _client(viewer).get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200  # still viewable, like a blocked OP
    assert resp.data["is_muted"] is True
    assert resp.data["is_blocked"] is False


@pytest.mark.django_db
def test_topic_list_search_and_experts_hide_a_muted_member():
    board = _board()
    author = User.objects.create_user(username="muted-author8")
    profile = ForumProfile.for_user(author)
    profile.trust_level = 3
    profile.save()
    viewer = User.objects.create_user(username="muter8")
    _topic(board, author, "t8")
    UserMute.mute(viewer, author)

    client = _client(viewer)
    topics = client.get(f"/forum/boards/{board.slug}/topics/")
    search = client.get("/forum/search/", {"q": "propagation"})
    experts = client.get("/forum/users/experts/")

    assert topics.status_code == 200 and topics.data["results"] == []
    assert search.status_code == 200
    assert search.data["topics"] == [] and search.data["posts"] == []
    assert experts.status_code == 200 and experts.data["results"] == []


@pytest.mark.django_db
def test_home_activity_feed_hides_muted_and_blocked_members_for_the_viewer_only():
    """topics/recent/ (the home "Active now" feed) had never been block-aware
    (cross-cutting review of todo 347): now the viewer's own mutes AND blocks
    shape it, exactly like the board topic list — and nobody else's view
    changes (anonymous still sees every live topic)."""
    from django.utils import timezone
    from wagtail_forum.models import UserBlock

    board = _board()
    muted = User.objects.create_user(username="recent-muted")
    blocked = User.objects.create_user(username="recent-blocked")
    fine = User.objects.create_user(username="recent-fine")
    viewer = User.objects.create_user(username="recent-viewer")
    ids = {}
    for slug, author in (("r-muted", muted), ("r-blocked", blocked), ("r-fine", fine)):
        topic = _topic(board, author, slug)
        Topic.objects.filter(pk=topic.pk).update(last_post_at=timezone.now())
        ids[slug] = topic.pk
    UserMute.mute(viewer, muted)
    UserBlock.block(viewer, blocked)

    mine = _client(viewer).get("/forum/topics/recent/")
    anon = _client().get("/forum/topics/recent/")

    assert mine.status_code == 200
    assert [t["id"] for t in mine.data["results"]] == [ids["r-fine"]]
    assert {t["id"] for t in anon.data["results"]} == set(ids.values())


@pytest.mark.django_db
def test_notification_list_hides_a_muted_actor():
    board = _board()
    recipient = User.objects.create_user(username="muter9")
    actor = User.objects.create_user(username="muted-actor9")
    topic = _topic(board, recipient, "t9")
    post = Post.objects.create(topic=topic, author=actor)
    UserMute.mute(recipient, actor)
    create_notifications(
        recipients=[recipient],
        verb=NotificationVerb.REPLY,
        actor=actor,
        topic=topic,
        post=post,
    )

    resp = _client(recipient).get("/forum/notifications/")

    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_public_profile_flags_muted_and_empties_activity():
    board = _board()
    muted = User.objects.create_user(username="muted-profile")
    viewer = User.objects.create_user(username="muter10")
    _topic(board, muted, "t10")
    UserMute.mute(viewer, muted)

    resp = _client(viewer).get(f"/forum/users/{muted.username}/")

    assert resp.status_code == 200
    assert resp.data["is_muted"] is True
    assert resp.data["is_blocked"] is False
    assert resp.data["can_mute"] is True
    assert resp.data["recent_topics"] == [] and resp.data["recent_posts"] == []


# --------------------------------------------------------------------------
# What a mute does NOT do — for the muted member, and for DMs
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_mute_is_one_directional_the_muted_member_notices_nothing():
    board = _board()
    muter = User.objects.create_user(username="muter11")
    muted = User.objects.create_user(username="muted11")
    muter_topic = _topic(board, muter, "t11")
    UserMute.mute(muter, muted)
    post = Post.objects.create(topic=muter_topic, author=muter)
    create_notifications(
        recipients=[muted],
        verb=NotificationVerb.REPLY,
        actor=muter,
        topic=muter_topic,
        post=post,
    )

    client = _client(muted)
    topics = client.get(f"/forum/boards/{board.slug}/topics/")
    posts = client.get(f"/forum/topics/{muter_topic.id}/posts/")
    notifications = client.get("/forum/notifications/")
    profile = client.get(f"/forum/users/{muter.username}/")

    assert [t["id"] for t in topics.data["results"]] == [muter_topic.id]
    assert all(row["is_muted"] is False for row in posts.data["results"])
    assert len(notifications.data["results"]) == 1
    assert profile.data["is_muted"] is False
    assert profile.data["recent_topics"] != []


@pytest.mark.django_db
def test_a_mute_does_not_touch_direct_messages_in_either_direction():
    """Discourse precedent, recorded in the todo-347 Work Log: a muted
    member's messages still arrive; only a BLOCK refuses DMs."""
    muter = User.objects.create_user(username="muter12")
    muted = User.objects.create_user(username="muted12")
    UserMute.mute(muter, muted)

    from_muted = _client(muted).post(
        f"/forum/users/{muter.username}/messages/", {"body": "hi"}
    )
    from_muter = _client(muter).post(
        f"/forum/users/{muted.username}/messages/", {"body": "hi"}
    )

    assert from_muted.status_code == 201, from_muted.data
    assert from_muter.status_code == 201, from_muter.data
    assert Message.objects.count() == 2


def _topic_with_posts(board, author, slug, n):
    topic = _topic(board, author, slug)
    for _ in range(n - 1):
        Post.objects.create(topic=topic, author=author, live=True)
    return topic


def _page_queries(client, topic):
    """Query count for one post-list page, after warming the per-request
    presence touch (one UPDATE gated by a cache key, docs/rules/testing.md)."""
    client.get(f"/forum/topics/{topic.id}/posts/")
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    return resp, len(ctx.captured_queries)


@pytest.mark.django_db
def test_a_moderators_own_mutes_are_inert_and_the_flag_stays_flat():
    """Same policy as blocks (test_block_filtering_moderator_bypass.py): a
    moderator's view is never shaped by mutes. Pinned as 1-post vs 10-post
    FLATNESS (review of this slice): if the constant-False annotation were
    skipped for moderators, get_is_muted would fall back to one .exists()
    per row and the 10-post page would cost nine more queries."""
    board = _board()
    author = User.objects.create_user(username="muted-author13")
    one = _topic_with_posts(board, author, "t13-one", 1)
    ten = _topic_with_posts(board, author, "t13-ten", 10)
    mod = _moderator("mod13")
    UserMute.mute(mod, author)

    client = _client(mod)
    resp_ten, n_ten = _page_queries(client, ten)
    _resp_one, n_one = _page_queries(client, one)

    assert len(resp_ten.data["results"]) == 10
    assert all(row["is_muted"] is False for row in resp_ten.data["results"])
    assert n_ten == n_one
    assert client.get(f"/forum/boards/{board.slug}/topics/").data["results"] != []


@pytest.mark.django_db
def test_mute_flags_stay_flat_across_a_page_for_a_regular_viewer():
    """The muter's is_muted flags come from the per-row EXISTS annotation,
    not a per-object fallback: a 10-post page costs what a 1-post page
    costs (review of this slice — a mute-present vs mute-absent comparison
    would let an N+1 through, since it inflates both sides equally)."""
    board = _board()
    author = User.objects.create_user(username="muted-author14")
    one = _topic_with_posts(board, author, "t14-one", 1)
    ten = _topic_with_posts(board, author, "t14-ten", 10)
    viewer = User.objects.create_user(username="muter14")
    UserMute.mute(viewer, author)

    client = _client(viewer)
    resp_ten, n_ten = _page_queries(client, ten)
    _resp_one, n_one = _page_queries(client, one)

    assert len(resp_ten.data["results"]) == 10
    assert all(row["is_muted"] is True for row in resp_ten.data["results"])
    assert n_ten == n_one


@pytest.mark.django_db
def test_my_mutes_with_avatars_adds_no_per_row_queries():
    """Mirror of test_my_blocks_with_avatars_adds_no_per_row_queries:
    MyMutesView's select_related("muted__wagtail_forum_profile__avatar") is
    only proven by fixtures that traverse its last leg (Pattern 30). Every
    muted user gets an avatar and the endpoint is pinned EXACTLY."""
    from django.core.cache import cache
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    muter = User.objects.create_user(username="muter15")
    for i in range(4):
        target = User.objects.create_user(username=f"avatar-muted{i}")
        profile = ForumProfile.for_user(target)
        profile.avatar = get_image_model().objects.create(
            title=f"muted-avatar-{i}",
            file=get_test_image_file(),
            collection=get_forum_image_collection(),
            uploaded_by_user=target,
        )
        profile.save(update_fields=["avatar"])
        UserMute.mute(muter, target)

    client = _client(muter)
    # The presence touch is throttled by cache.add() on a key the test cache
    # keeps across runs and DB rebuilds (docs/rules/testing.md).
    cache.delete(f"forum:presence:{muter.pk}")
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/me/mutes/")

    assert resp.status_code == 200
    assert len(resp.data) == 4
    assert all(row["avatar"] for row in resp.data)
    # Pinned EXACTLY: the presence touch UPDATE + one SELECT joining
    # muted -> profile -> avatar.
    assert len(ctx.captured_queries) == 2, [q["sql"][:80] for q in ctx.captured_queries]
