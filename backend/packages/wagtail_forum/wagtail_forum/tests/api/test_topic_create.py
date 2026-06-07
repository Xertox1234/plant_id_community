import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.spam.base import SpamBackend
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    """Prevent idempotency cache from bleeding between tests (LocMemCache is process-global)."""
    cache.clear()
    yield
    cache.clear()


class RaisingSpamBackend(SpamBackend):
    def check(self, obj):
        raise RuntimeError("spam backend down")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_trusted_user_creates_published_topic_idempotently():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg", password="x")
    p = ForumProfile.for_user(user)
    p.trust_level = TrustLevel.MEMBER
    p.save()

    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "Hello",
        "slug": "hello",
        "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
    }
    headers = {"HTTP_IDEMPOTENCY_KEY": "abc-123"}

    r1 = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json", **headers
    )
    r2 = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json", **headers
    )

    assert r1.status_code == 201
    assert r1.data["status"] == "published"
    assert r2.status_code == 200  # replayed, not duplicated
    assert Topic.objects.filter(board=board).count() == 1


@pytest.mark.django_db
def test_duplicate_slug_returns_409():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg", password="x")
    p = ForumProfile.for_user(user)
    p.trust_level = TrustLevel.MEMBER
    p.save()
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "Hello",
        "slug": "hello",
        "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
    }

    r1 = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="k1",
    )
    r2 = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="k2",
    )
    assert r1.status_code == 201
    assert r2.status_code == 409
    assert Topic.objects.filter(board=board).count() == 1


@override_settings(
    WAGTAILFORUM_SPAM_BACKEND="wagtail_forum.tests.api.test_topic_create.RaisingSpamBackend"
)
@pytest.mark.django_db
def test_spam_backend_exception_leaves_pending_not_500():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="new", password="x")
    ForumProfile.for_user(
        user
    )  # trust NEW -> runs the moderation workflow -> spam check
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "Hi",
        "slug": "hi",
        "body": [{"type": "paragraph", "value": "<p>hello there friend</p>"}],
    }

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )

    assert resp.status_code == 201
    assert resp.data["status"] == "pending"
    post = Post.objects.get(topic__slug="hi")
    assert post.live is False  # nothing published despite the backend crash


@pytest.mark.django_db
def test_dangerous_body_is_sanitized_on_write():
    # A javascript: href, an onerror handler, and a <script> tag are all stripped
    # by the nh3 allowlist before storage; benign text survives. The post is
    # accepted (201) with clean content, not rejected.
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="x", password="x")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "T",
        "slug": "t",
        "body": [
            {
                "type": "paragraph",
                "value": (
                    '<p><a href="javascript:alert(1)">x</a>'
                    '<img src=x onerror="alert(1)">'
                    "<script>alert(1)</script>ok</p>"
                ),
            }
        ],
    }
    resp = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )
    assert resp.status_code == 201
    source = (
        Post.objects.get(topic__slug="t", is_opening_post=True).body[0].value.source
    )
    assert "javascript:" not in source
    assert "onerror" not in source
    assert "<script" not in source
    assert "<img" not in source
    assert "ok" in source  # benign text preserved


@pytest.mark.django_db
def test_safe_link_is_preserved():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="x", password="x")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "T2",
        "slug": "t2",
        "body": [
            {
                "type": "paragraph",
                "value": '<p><a href="https://example.com">ok</a></p>',
            }
        ],
    }
    resp = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )
    assert resp.status_code == 201
    source = (
        Post.objects.get(topic__slug="t2", is_opening_post=True).body[0].value.source
    )
    assert 'href="https://example.com"' in source


@pytest.mark.django_db
def test_oversized_body_is_rejected():
    # DoS guard: a body exceeding MAX_BODY_BLOCKS is a 400, not a parse storm.
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="x", password="x")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "T",
        "slug": "t",
        "body": [{"type": "paragraph", "value": "<p>x</p>"}] * 101,
    }
    resp = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )
    assert resp.status_code == 400
    assert Topic.objects.filter(slug="t").count() == 0
