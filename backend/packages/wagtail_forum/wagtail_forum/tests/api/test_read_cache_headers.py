"""M42 (audit 2026-07-11): Cache-Control / Vary on the forum read path.

Two tiers:

- **Public-cacheable** (board list, topic list, search): anonymous success
  responses carry `public, s-maxage` so a CDN like Cloudflare can offload
  read-heavy public traffic. These are identical across all anonymous users.
- **Never shared-cached** (topic detail, post list): always `private, no-store`.
  Topic detail increments `view_count` per hit (a CDN cache would undercount a
  user-visible sortable metric); a report-hidden/unpublished post must stop
  serving immediately and there is no CDN purge wired.

The correctness trap these guard: forum posts serialize per-user capability
fields (`can_edit`/`can_delete`/`can_report`/`reacted`), topic list `is_unread`,
topic detail `is_subscribed`. No authenticated response — and nothing carrying a
per-user field — may ever be stored by a shared cache. `Vary` covers both
`Cookie` and `Authorization` because `CookieJWTAuthentication` accepts the
Authorization header (the cookie-less mobile client), so a cache keyed only on
Cookie could otherwise hand the anon entry to a header-authenticated request.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board_topic_post():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    return board, topic, post


def _public_paths(board):
    # Anonymous → shared-cacheable (no per-request side effect, list-level staleness).
    # topics/recent/ and users/experts/ (Canopy landing rails) both use
    # PublicForumReadCacheMixin + AllowAny like the others here — confirmed
    # empirically, not just by mixin inspection, before adding them.
    return [
        "/forum/boards/",
        f"/forum/boards/{board.slug}/topics/",
        "/forum/search/",
        "/forum/topics/recent/",
        "/forum/users/experts/",
    ]


def _private_paths(topic):
    # Never shared-cached (view_count side effect / content-removal staleness).
    return [f"/forum/topics/{topic.id}/", f"/forum/topics/{topic.id}/posts/"]


def _assert_varies_on_auth(resp, path):
    vary = resp["Vary"]
    assert "Cookie" in vary, path
    assert "Authorization" in vary, path


@pytest.mark.django_db
def test_public_reads_are_shared_cacheable_when_anonymous():
    board, topic, _ = _board_topic_post()
    client = APIClient()
    for path in _public_paths(board):
        resp = client.get(path)
        assert resp.status_code == 200, path
        cache_control = resp["Cache-Control"]
        assert "public" in cache_control, path
        assert "s-maxage=60" in cache_control, path
        assert "max-age=0" in cache_control, path
        assert "no-store" not in cache_control, path
        _assert_varies_on_auth(resp, path)


@pytest.mark.django_db
def test_public_reads_are_private_when_authenticated():
    board, topic, _ = _board_topic_post()
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="viewer"))
    for path in _public_paths(board):
        resp = client.get(path)
        assert resp.status_code == 200, path
        cache_control = resp["Cache-Control"]
        assert "no-store" in cache_control, path
        assert "private" in cache_control, path
        assert "public" not in cache_control, path
        assert "s-maxage" not in cache_control, path
        _assert_varies_on_auth(resp, path)


@pytest.mark.django_db
def test_side_effect_reads_are_never_shared_cached():
    # Topic detail (view_count) and post list (moderation-removal staleness) are
    # no-store for EVERYONE — anonymous included — so every hit reaches origin.
    board, topic, _ = _board_topic_post()
    anon = APIClient()
    authed = APIClient()
    authed.force_authenticate(User.objects.create_user(username="viewer"))
    for client in (anon, authed):
        for path in _private_paths(topic):
            resp = client.get(path)
            assert resp.status_code == 200, path
            cache_control = resp["Cache-Control"]
            assert "no-store" in cache_control, path
            assert "public" not in cache_control, path
            assert "s-maxage" not in cache_control, path
            _assert_varies_on_auth(resp, path)


@pytest.mark.django_db
def test_anon_post_list_leaks_no_per_user_capability():
    # Even though post list is no-store, pin the anonymous baseline: an anon
    # reader never sees an owner's edit/delete rights or reactions.
    board, topic, _ = _board_topic_post()
    client = APIClient()

    posts = client.get(f"/forum/topics/{topic.id}/posts/")
    post = posts.data["results"][0]
    assert post["can_edit"] is False
    assert post["can_delete"] is False
    assert post["can_report"] is False
    assert post["reacted"] == []

    topic_list = client.get(f"/forum/boards/{board.slug}/topics/")
    assert topic_list.data["results"][0]["is_unread"] is False
    detail = client.get(f"/forum/topics/{topic.id}/")
    assert detail.data["is_subscribed"] is False


@pytest.mark.django_db
def test_write_response_is_not_shared_cacheable():
    # The mixin only touches GET/HEAD, so a mutating POST (topic create) never
    # receives a shared-cacheable header — guards against a future widening of
    # the method check silently caching a write response.
    board, _, _ = _board_topic_post()
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="writer"))
    resp = client.post(f"/forum/boards/{board.slug}/topics/", {}, format="json")
    cache_control = resp.get("Cache-Control", "")
    assert "public" not in cache_control
    assert "s-maxage" not in cache_control


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_PUBLIC_READ_CACHE_SECONDS=123)
def test_anon_smaxage_honors_the_configured_setting():
    board, _, _ = _board_topic_post()
    resp = APIClient().get("/forum/boards/")
    assert "s-maxage=123" in resp["Cache-Control"]


def _authenticated_only_paths(post):
    # IsAuthenticated-gated GETs — an anon request 401s, not 200, so these
    # can't join _private_paths()'s anon+authed loop (that's why me/stats/
    # needed its own dedicated assertion pre-todo-303). Todo 303: swept every
    # IsAuthenticated GET in the package and applied PrivateForumReadCacheMixin
    # to each — any future one added without the mixin fails this pin.
    return [
        "/forum/me/profile/",
        "/forum/me/stats/",
        f"/forum/posts/{post.id}/revisions/",
        f"/forum/posts/{post.id}/revisions/{post.revisions.first().id}/",
        "/forum/notifications/",
        "/forum/notifications/unread-count/",
        "/forum/users/search/?q=a",
    ]


@pytest.mark.django_db
def test_authenticated_only_reads_are_never_shared_cached():
    # Per-user payloads (profile, stats, edit history, notifications, mention
    # search) must never be storable by a shared cache — same reasoning as
    # topic detail/post list, but these 401 anonymously so they need their own
    # authenticated-only loop rather than joining _private_paths().
    board, topic, post = _board_topic_post()
    # Author-only revision-privacy gate (todo 282): the post's own author,
    # unedited by anyone else, may always read its revision history.
    post.save_revision(user=post.author)
    client = APIClient()
    client.force_authenticate(post.author)
    for path in _authenticated_only_paths(post):
        resp = client.get(path)
        assert resp.status_code == 200, path
        cache_control = resp["Cache-Control"]
        assert "no-store" in cache_control, path
        assert "private" in cache_control, path
        assert "public" not in cache_control, path
        assert "s-maxage" not in cache_control, path
        _assert_varies_on_auth(resp, path)
