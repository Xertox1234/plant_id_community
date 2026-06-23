"""Rate limiting on the host-mounted forum API (2026-06-10 audit H1).

Runs against the real project URLconf — the throttled wrappers in
apps/forum_host/api.py are what production serves at /api/v1/forum/.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, TrustLevel
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_ratelimit_cache():
    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def test_host_api_routes_match_package():
    """Drift guard: a new package endpoint must not silently ship unmounted
    (404 in prod) or unthrottled — this fails until api_urls.py is updated."""
    from apps.forum_host import api_urls as host
    from wagtail_forum.api import urls as pkg

    pkg_routes = {(str(p.pattern), p.name) for p in pkg.urlpatterns}
    host_routes = {(str(p.pattern), p.name) for p in host.urlpatterns}
    assert pkg_routes == host_routes


@override_settings(FORUM_RATELIMITS={"search": "2/m"})
@pytest.mark.django_db
def test_search_is_throttled_with_429_and_retry_after():
    client = APIClient()
    # Freeze time so all requests share one ratelimit window (jittered windows
    # can roll over mid-hammer and flake the 429 assertion).
    with freeze_time("2026-06-10 12:00:00"):
        for _ in range(2):
            assert client.get("/api/v1/forum/search/?q=x").status_code == 200
        r = client.get("/api/v1/forum/search/?q=x")

    assert r.status_code == 429  # NOT 403 — Ratelimited subclasses PermissionDenied
    assert r["Retry-After"] == "60"  # derived from the 2/m window


@override_settings(FORUM_RATELIMITS={"topic_create": "2/h"})
@pytest.mark.django_db
def test_topic_create_is_throttled_per_user():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg", password="x")
    p = ForumProfile.for_user(user)
    p.trust_level = TrustLevel.MEMBER
    p.save()

    client = APIClient()
    client.force_authenticate(user)

    def create(slug):
        return client.post(
            f"/api/v1/forum/boards/{board.slug}/topics/",
            {
                "title": slug,
                "slug": slug,
                "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            },
            format="json",
        )

    with freeze_time("2026-06-10 12:00:00"):
        assert create("one").status_code == 201
        assert create("two").status_code == 201
        r = create("three")

    assert r.status_code == 429
    assert "Retry-After" in r


def test_wrapped_routes_use_the_throttled_views():
    """Parity by (pattern, name) alone passes if a route is re-pointed at the
    unthrottled package view — pin the callbacks (review finding 21)."""
    from apps.forum_host import api as throttled
    from apps.forum_host import api_urls as host

    wrapped = {
        "topic-list": throttled.TopicListView,
        "post-list": throttled.PostListView,
        "reaction-toggle": throttled.ReactionToggleView,
        "me-profile": throttled.MeProfileView,
        "search": throttled.SearchView,
        "sync": throttled.SyncView,
    }
    by_name = {p.name: p.callback.view_class for p in host.urlpatterns}
    for name, view_class in wrapped.items():
        assert by_name[name] is view_class


@override_settings(FORUM_RATELIMITS={"topic_create": "1/h"})
@pytest.mark.django_db
def test_throttle_is_per_user_not_global():
    ensure_default_workflow()
    board = _board()
    users = []
    for name in ("u1", "u2"):
        u = User.objects.create_user(username=name, password="x")
        p = ForumProfile.for_user(u)
        p.trust_level = TrustLevel.MEMBER
        p.save()
        users.append(u)

    client = APIClient()
    with freeze_time("2026-06-10 12:00:00"):
        client.force_authenticate(users[0])
        first = client.post(
            f"/api/v1/forum/boards/{board.slug}/topics/",
            {
                "title": "a",
                "slug": "a",
                "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            },
            format="json",
        )
        blocked = client.post(
            f"/api/v1/forum/boards/{board.slug}/topics/",
            {
                "title": "b",
                "slug": "b",
                "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            },
            format="json",
        )
        client.force_authenticate(users[1])  # a DIFFERENT user is not throttled
        other = client.post(
            f"/api/v1/forum/boards/{board.slug}/topics/",
            {
                "title": "c",
                "slug": "c",
                "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            },
            format="json",
        )

    assert first.status_code == 201
    assert blocked.status_code == 429
    assert other.status_code == 201
