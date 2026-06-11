import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.api.sanitize import MAX_BODY_BLOCKS
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
    # Replay carries the ORIGINAL status (IETF idempotency-key draft), not 200.
    assert r2.status_code == 201
    assert r2.data == r1.data
    assert Topic.objects.filter(board=board).count() == 1


@pytest.mark.django_db
def test_api_topic_create_publishes_topic_and_updates_board_counters():
    """The API creates topics live=False; the workflow must flip the TOPIC live
    (not just the post) and the board counters must include it (audit H2/H5)."""
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg", password="x")
    p = ForumProfile.for_user(user)
    p.trust_level = TrustLevel.MEMBER
    p.save()

    client = APIClient()
    client.force_authenticate(user)
    r = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        {
            "title": "Hello",
            "slug": "hello",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
        },
        format="json",
    )

    assert r.status_code == 201
    topic = Topic.objects.get(board=board, slug="hello")
    assert topic.live is True
    board.refresh_from_db()
    assert board.topic_count == 1
    assert board.post_count == 1


@override_settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["casino"])
@pytest.mark.django_db
def test_spam_in_topic_title_is_screened():
    """Banned words in the TITLE alone must hold the topic in moderation —
    titles are the most visible surface (lists, search, sync) (audit M1)."""
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="newbie", password="x")  # trust NEW

    client = APIClient()
    client.force_authenticate(user)
    r = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        {
            "title": "Best casino deals",
            "slug": "casino-deals",
            "body": [{"type": "paragraph", "value": "<p>a perfectly normal body</p>"}],
        },
        format="json",
    )

    assert r.status_code == 201
    assert r.data["status"] == "pending"
    topic = Topic.objects.get(board=board, slug="casino-deals")
    assert topic.live is False
    assert topic.posts.get().live is False


@pytest.mark.django_db
def test_duplicate_slug_is_auto_suffixed():
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
    # A taken slug auto-suffixes instead of 409ing: a conflict response would
    # leak the existence of a hidden DRAFT topic with that slug (audit L4).
    assert r2.status_code == 201
    assert r2.data["slug"] == "hello-2"
    assert Topic.objects.filter(board=board).count() == 2


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


@override_settings(
    WAGTAILFORUM_SPAM_BACKEND="wagtail_forum.tests.api.test_topic_create.RaisingSpamBackend"
)
@pytest.mark.django_db
def test_spam_backend_crash_replays_pending_on_retry():
    # The draft topic commits before moderation runs, so a retry with the same
    # idempotency key must replay the cached "pending" result, not allocate a
    # second (suffixed) topic.
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="new", password="x")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "Hi",
        "slug": "hi",
        "body": [{"type": "paragraph", "value": "<p>hello there friend</p>"}],
    }

    r1 = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="key1",
    )
    r2 = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="key1",
    )
    assert r1.status_code == 201
    assert r1.data["status"] == "pending"
    assert r2.status_code == 201  # clean replay with the original status
    assert r2.data == r1.data
    assert Topic.objects.filter(board=board).count() == 1


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
        "body": [{"type": "paragraph", "value": "<p>x</p>"}] * (MAX_BODY_BLOCKS + 1),
    }
    resp = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )
    assert resp.status_code == 400
    # Flat field error — body maps to a list of strings, not the double-nested
    # {"body": {"body": [...]}} shape (M14). The project envelope nests field
    # errors under "errors" when the custom exception handler is active.
    field_errors = resp.data.get("errors", resp.data)
    assert isinstance(field_errors["body"][0], str)
    assert Topic.objects.filter(slug="t").count() == 0


@pytest.mark.django_db
def test_unauthenticated_writes_are_rejected():
    """All three write endpoints require auth (audit M16) — dropping
    permission_classes must fail this, not pass silently."""
    board = _board()
    client = APIClient()  # no credentials

    create = client.post(
        f"/forum/boards/{board.slug}/topics/create/",
        {"title": "x", "slug": "x", "body": []},
        format="json",
    )
    reply = client.post("/forum/topics/1/posts/create/", {"body": []}, format="json")
    react = client.post("/forum/posts/1/reactions/", {"type": "like"}, format="json")

    assert create.status_code == 401
    assert reply.status_code == 401
    assert react.status_code == 401


@pytest.mark.django_db
def test_slug_suffix_never_exceeds_max_length():
    """A max-length slug that conflicts must truncate before suffixing —
    Postgres raises DataError past SlugField(max_length=255) (review finding 5)."""
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg", password="x")
    p = ForumProfile.for_user(user)
    p.trust_level = TrustLevel.MEMBER
    p.save()
    client = APIClient()
    client.force_authenticate(user)
    long_slug = "s" * 255
    payload = {
        "title": "Hello",
        "slug": long_slug,
        "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
    }

    r1 = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )
    r2 = client.post(
        f"/forum/boards/{board.slug}/topics/create/", payload, format="json"
    )

    assert r1.status_code == r2.status_code == 201
    assert len(r2.data["slug"]) <= 255
    assert r2.data["slug"].endswith("-2")


def test_reserve_rejects_concurrent_same_key():
    """cache.add() is the atomic in-flight gate (review finding 8)."""
    from django.core.cache import cache
    from wagtail_forum.api.exceptions import Conflict as ForumConflict
    from wagtail_forum.api.idempotency import reserve

    cache.clear()
    reserve("forum:idem:test:1:abc")  # first caller reserves
    with pytest.raises(ForumConflict):
        reserve("forum:idem:test:1:abc")  # concurrent twin is rejected
    cache.clear()
