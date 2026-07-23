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


# Host-only routes with no package counterpart — AI features whose logic reuses
# host-side helpers the package may not import (todo 255). Each must still be a
# real, mounted, throttled host view; they are allow-listed out of the drift
# guard so they do not read as package drift.
HOST_ONLY_ROUTES = {
    ("topics/<int:topic_id>/summary/", "topic-summary"),  # H14 AI thread summary
    ("topics/similar/", "topic-similar"),  # H15 semantic similar topics
}


def test_host_api_routes_match_package():
    """Drift guard: every package endpoint must be mounted host-side (else it
    404s in prod or ships unthrottled) — this fails until api_urls.py is updated.

    Relaxed from strict equality to ``package ⊆ host`` plus an explicit
    HOST_ONLY_ROUTES allow-list, so intentional host-only AI routes are
    permitted while the real invariant (no package route left unmounted, no
    stray host route) is preserved."""
    from apps.forum_host import api_urls as host
    from wagtail_forum.api import urls as pkg

    pkg_routes = {(str(p.pattern), p.name) for p in pkg.urlpatterns}
    host_routes = {(str(p.pattern), p.name) for p in host.urlpatterns}
    # Every package route is mounted host-side.
    assert pkg_routes <= host_routes
    # The only host routes without a package counterpart are the allow-listed
    # host-only ones — a stray/typo'd host route still fails here.
    assert host_routes - pkg_routes == HOST_ONLY_ROUTES


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


@override_settings(FORUM_RATELIMITS={"mention_user_search": "2/m"})
@pytest.mark.django_db
def test_mention_user_search_is_throttled_with_429_and_retry_after():
    """Proves the mention_user_search rate string in constants.py isn't dead
    config (todo 253 slice 4 review) — mirrors
    test_search_is_throttled_with_429_and_retry_after's shape, plus auth
    since this endpoint (unlike search) requires IsAuthenticated."""
    user = User.objects.create_user(username="mentionsearcher")
    client = APIClient()
    client.force_authenticate(user)

    with freeze_time("2026-06-10 12:00:00"):
        for _ in range(2):
            assert client.get("/api/v1/forum/users/search/?q=a").status_code == 200
        r = client.get("/api/v1/forum/users/search/?q=a")

    assert r.status_code == 429  # NOT 403 — Ratelimited subclasses PermissionDenied
    assert r["Retry-After"] == "60"  # derived from the 2/m window


@override_settings(FORUM_RATELIMITS={"topic_create": "2/h"})
@pytest.mark.django_db
def test_topic_create_is_throttled_per_user():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg")
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
        "post-detail": throttled.PostWriteView,
        "image-upload": throttled.PostImageUploadView,
        "reaction-toggle": throttled.ReactionToggleView,
        "post-report": throttled.PostReportView,
        "me-profile": throttled.MeProfileView,
        "search": throttled.SearchView,
        "sync": throttled.SyncView,
        "topic-subscription": throttled.TopicSubscriptionView,
    }
    by_name = {p.name: p.callback.view_class for p in host.urlpatterns}
    for name, view_class in wrapped.items():
        assert by_name[name] is view_class


def test_every_unsafe_handler_is_throttled():
    """Class-identity parity (above) still passes if a NEW unsafe handler is added
    to a wrapped view without a rate. Assert every unsafe method the view actually
    defines a handler for is in _forum_throttled_methods (todo 255, using the 254
    marker). search/sync throttle a safe method (GET) and have no unsafe handler,
    so they satisfy this trivially — but gain protection if one is ever added."""
    from apps.forum_host import api as throttled

    safe = {"GET", "HEAD", "OPTIONS", "TRACE"}
    wrappers = [
        throttled.TopicListView,
        throttled.PostListView,
        throttled.PostWriteView,
        throttled.PostImageUploadView,
        throttled.ReactionToggleView,
        throttled.PostReportView,
        throttled.MeProfileView,
        throttled.SearchView,
        throttled.SyncView,
        throttled.TopicSubscriptionView,
    ]
    for view in wrappers:
        marked = getattr(view, "_forum_throttled_methods", set())
        handled = {
            m.upper() for m in view.http_method_names if hasattr(view, m.lower())
        }
        unthrottled_unsafe = (handled - safe) - marked
        assert (
            not unthrottled_unsafe
        ), f"{view.__name__} has unthrottled unsafe handler(s): {unthrottled_unsafe}"


@override_settings(FORUM_RATELIMITS={"topic_create": "1/h"})
@pytest.mark.django_db
def test_throttle_is_per_user_not_global():
    ensure_default_workflow()
    board = _board()
    users = []
    for name in ("u1", "u2"):
        u = User.objects.create_user(username=name)
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


@override_settings(FORUM_RATELIMITS={"image_upload": "1/h"})
@pytest.mark.django_db
def test_image_upload_is_throttled_per_user():
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image as PILImage

    user = User.objects.create_user(username="up")
    client = APIClient()
    client.force_authenticate(user)

    def upload():
        buf = io.BytesIO()
        PILImage.new("RGB", (10, 10), "red").save(buf, format="JPEG")
        buf.seek(0)
        return client.post(
            "/api/v1/forum/images/",
            {"image": SimpleUploadedFile("a.jpg", buf.read(), "image/jpeg")},
            format="multipart",
        )

    with freeze_time("2026-06-10 12:00:00"):
        first = upload()
        blocked = upload()

    assert first.status_code == 201
    assert blocked.status_code == 429  # NOT 403 — Ratelimited subclasses it
    assert "Retry-After" in blocked


@override_settings(FORUM_RATELIMITS={"post_update": "1/h"})
@pytest.mark.django_db
def test_post_update_is_throttled_per_user():
    """The new PATCH handler is throttled by the host wrapper (post_update).
    DELETE uses the identical @method_decorator mechanism on the same class."""
    from wagtail_forum.blocks import ForumBodyBlock
    from wagtail_forum.models import Post, Topic
    from wagtail_forum.workflow import submit_for_moderation

    ensure_default_workflow()
    board = _board()
    author = User.objects.create_user(username="ed")
    p = ForumProfile.for_user(author)
    p.trust_level = TrustLevel.MEMBER  # >= autopublish, so create+edit go live
    p.save()

    topic = Topic(board=board, title="t", slug="t", author=author, live=False)
    topic.save()
    op = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=ForumBodyBlock().to_python([{"type": "paragraph", "value": "<p>op</p>"}]),
        live=False,
    )
    op.save()
    submit_for_moderation(op, author)
    reply = Post(
        topic=topic,
        author=author,
        body=ForumBodyBlock().to_python([{"type": "paragraph", "value": "<p>r</p>"}]),
        live=False,
    )
    reply.save()
    submit_for_moderation(reply, author)

    client = APIClient()
    client.force_authenticate(author)
    payload = {"body": [{"type": "paragraph", "value": "<p>e</p>"}]}
    with freeze_time("2026-06-10 12:00:00"):
        first = client.patch(f"/api/v1/forum/posts/{reply.id}/", payload, format="json")
        blocked = client.patch(
            f"/api/v1/forum/posts/{reply.id}/", payload, format="json"
        )

    assert first.status_code == 200
    assert blocked.status_code == 429
    assert "Retry-After" in blocked


@override_settings(FORUM_RATELIMITS={"report_create": "1/h"})
@pytest.mark.django_db
def test_report_is_throttled_per_user():
    from wagtail_forum.models import Post, Topic

    ensure_default_workflow()
    board = _board()
    author = User.objects.create_user(username="op")
    topic = Topic.objects.create(board=board, title="t", slug="t", author=author)
    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    opening.save_revision().publish()

    reporter = User.objects.create_user(username="reporter")
    client = APIClient()
    client.force_authenticate(reporter)

    def report(reason):
        return client.post(
            f"/api/v1/forum/posts/{opening.id}/reports/",
            {"reason": reason},
            format="json",
        )

    with freeze_time("2026-06-10 12:00:00"):
        first = report("spam")
        blocked = report("abuse")

    assert first.status_code == 200
    assert blocked.status_code == 429
    assert "Retry-After" in blocked


@override_settings(FORUM_RATELIMITS={"subscription_create": "1/h"})
@pytest.mark.django_db
def test_subscription_create_is_throttled_per_user():
    """Proves the subscription_create/subscription_delete rate strings in
    constants.py aren't dead config (todo 253 slice 3) — mirrors
    test_report_is_throttled_per_user's shape for a POST-only rate."""
    from wagtail_forum.models import Topic

    board = _board()
    topic = Topic.objects.create(board=board, title="t", slug="t", live=True)
    other_topic = Topic.objects.create(board=board, title="t2", slug="t2", live=True)

    user = User.objects.create_user(username="subscriber")
    client = APIClient()
    client.force_authenticate(user)

    with freeze_time("2026-06-10 12:00:00"):
        first = client.post(f"/api/v1/forum/topics/{topic.id}/subscription/")
        blocked = client.post(f"/api/v1/forum/topics/{other_topic.id}/subscription/")

    assert first.status_code == 200
    assert blocked.status_code == 429  # NOT 403 — Ratelimited subclasses it
    assert "Retry-After" in blocked
