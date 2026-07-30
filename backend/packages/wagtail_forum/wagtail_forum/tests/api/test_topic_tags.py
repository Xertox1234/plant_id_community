"""Topic tags — the secondary discovery taxonomy beside boards (audit M5, todo 276).

Covers the write contract (bounds + normalization), read serialization on both
the list and detail endpoints, the ?tag= filter, and the query-count pin that
keeps tag serialization from becoming an N+1.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Topic, TrustLevel
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _trusted_client(username="tagger"):
    """A MEMBER-trust user, so topic create publishes instead of going pending."""
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    client = APIClient()
    client.force_authenticate(user)
    return client, user


@pytest.mark.django_db
def test_create_topic_with_tags_persists_and_serializes_them():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Repotting a monstera",
            "slug": "repotting-a-monstera",
            "body": [{"type": "paragraph", "value": "<p>roots are crowded</p>"}],
            "tags": ["Monstera", "repotting"],
        },
        format="json",
    )

    assert resp.status_code == 201
    topic = Topic.objects.get(id=resp.data["id"])
    # Normalized to lowercase on write so the ?tag= filter has one spelling.
    assert sorted(t.name for t in topic.tags.all()) == ["monstera", "repotting"]

    detail = client.get(f"/forum/topics/{topic.id}/")
    assert detail.status_code == 200
    assert sorted(detail.data["tags"]) == ["monstera", "repotting"]


@pytest.mark.django_db
def test_create_topic_without_tags_is_untagged_not_an_error():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "No tags here",
            "slug": "no-tags-here",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
        },
        format="json",
    )

    assert resp.status_code == 201
    assert list(Topic.objects.get(id=resp.data["id"]).tags.all()) == []


@pytest.mark.django_db
def test_tags_are_deduplicated_and_whitespace_normalized():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Dupes",
            "slug": "dupes",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            # Same tag three ways + an inner-whitespace variant.
            "tags": ["Monstera", "monstera", " MONSTERA ", "root   rot"],
        },
        format="json",
    )

    assert resp.status_code == 201
    topic = Topic.objects.get(id=resp.data["id"])
    assert sorted(t.name for t in topic.tags.all()) == ["monstera", "root rot"]


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_TOPIC_MAX_TAGS=2)
def test_too_many_tags_is_rejected_with_400():
    """The bound is read at request time, so a host override actually applies."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Spray",
            "slug": "spray",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            "tags": ["a", "b", "c"],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert Topic.objects.filter(slug="spray").count() == 0


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_TOPIC_TAG_MAX_LENGTH=5)
def test_overlong_tag_is_rejected_with_400():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Long",
            "slug": "long",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            "tags": ["waytoolong"],
        },
        format="json",
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_tag_containing_a_comma_is_rejected():
    """A comma is taggit's own list separator — one tag would silently become two."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Comma",
            "slug": "comma",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            "tags": ["monstera, aroid"],
        },
        format="json",
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_topic_list_filters_by_tag():
    board = _board()
    author = User.objects.create_user(username="ada")
    tagged = Topic.objects.create(
        board=board, title="Tagged", slug="tagged", author=author, live=True
    )
    tagged.tags.add("monstera")
    other = Topic.objects.create(
        board=board, title="Other", slug="other", author=author, live=True
    )
    other.tags.add("ficus")

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?tag=monstera")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["tagged"]
    assert resp.data["results"][0]["tags"] == ["monstera"]


@pytest.mark.django_db
def test_tag_filter_is_exact_not_substring():
    """`?tag=rot` must not also match "root rot" — tags are labels, not search."""
    board = _board()
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="Rot", slug="rot", author=author, live=True
    )
    topic.tags.add("root rot")

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?tag=rot")

    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_tag_filter_normalizes_the_query_the_same_way_as_writes():
    board = _board()
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="Rot", slug="rot", author=author, live=True
    )
    topic.tags.add("root rot")

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?tag=  ROOT   rot ")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["rot"]


@pytest.mark.django_db
def test_unknown_tag_returns_an_empty_page_not_an_error():
    board = _board()
    author = User.objects.create_user(username="ada")
    Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    ).tags.add("monstera")

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?tag=nope")

    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_tag_serialization_does_not_scale_with_row_count():
    """The real N+1 guard: tags cost ONE prefetch query for the whole page,
    regardless of how many topics carry them. A per-row query would make this
    grow with the fixture size."""
    board = _board()
    author = User.objects.create_user(username="ada")
    for i in range(20):
        topic = Topic.objects.create(
            board=board, title=f"T{i}", slug=f"t{i}", author=author, live=True
        )
        topic.tags.add("monstera", "care")

    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20
    assert sorted(resp.data["results"][0]["tags"]) == ["care", "monstera"]
    # Exactly 4: board lookup, topics page, cursor has-next probe, tags prefetch.
    # (The first three are pinned in test_topics_list.py; the 4th is the prefetch
    # this feature adds.) Pinned EXACTLY per docs/rules/testing.md.
    assert len(ctx.captured_queries) == 4


# --------------------------------------------------------------------------
# Review repairs (code review of this change)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_tag_filter_finds_a_tag_the_cms_admin_created_with_capitals():
    """The API is not the only writer: the Wagtail admin panel writes tags via
    taggit's widget, bypassing normalize_topic_tags, and taggit's Tag.name is
    case-sensitive. An exact (case-SENSITIVE) filter made such a tag permanently
    unreachable from the "#Monstera" chip the UI renders from that same name."""
    board = _board()
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="Admin tagged", slug="admin-tagged", author=author, live=True
    )
    topic.tags.add("Monstera")  # as the CMS admin would store it

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?tag=Monstera")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["admin-tagged"]
    # ...and the lowercase spelling finds it too.
    assert (
        client.get(f"/forum/boards/{board.slug}/topics/?tag=monstera").data["results"][
            0
        ]["slug"]
        == "admin-tagged"
    )


@pytest.mark.django_db
def test_topic_with_both_tag_casings_appears_once_not_twice():
    """`Monstera` and `monstera` are two distinct Tag rows (Tag.name is unique
    and case-sensitive), so a case-insensitive join matches the same topic twice
    — .distinct() is what keeps it off the page as a duplicate."""
    board = _board()
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="Both", slug="both", author=author, live=True
    )
    topic.tags.add("Monstera", "monstera")

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?tag=monstera")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["both"]


@pytest.mark.django_db
def test_absurdly_long_tag_list_is_rejected_before_per_item_validation():
    """DRF enforces ListField(max_length=...) with a validator that runs AFTER
    every child has been validated, so it cannot bound the work a caller
    triggers. _BoundedTagListField checks the raw length first.

    Asserting the MESSAGE, not just the 400: the ordinary TOPIC_MAX_TAGS count
    check would also reject this payload, so a status-only assertion passes even
    with the early guard removed (verified by mutation) and would pin nothing.
    """
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Flood",
            "slug": "flood",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            "tags": [f"t{i}" for i in range(5_000)],
        },
        format="json",
    )

    assert resp.status_code == 400
    # The early-guard message, NOT "At most 5 tags per topic."
    assert "Too many tags." in str(resp.data)
    assert Topic.objects.filter(slug="flood").count() == 0


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_TOPIC_TAG_MAX_LENGTH=500)
def test_tag_length_bound_is_clamped_to_taggits_column_width():
    """A host raising the setting past taggit's Tag.name VARCHAR(100) would
    otherwise pass validation and then fail on INSERT with a DataError — which
    is NOT an IntegrityError, so _create_topic's slug-retry does not catch it,
    and a 400 becomes a 500."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Clamp",
            "slug": "clamp",
            "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
            "tags": ["x" * 200],  # under the override, over taggit's column
        },
        format="json",
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_tag_filter_paginates_for_an_authenticated_viewer():
    """The one shape the other tag tests miss: AUTHENTICATED + .distinct() +
    cursor pagination together.

    Anonymous requests take `_annotate_topic_unread`'s constant branch
    (`Value(False)`), but an authenticated one builds
    `.alias(_read_baseline=Coalesce(Subquery(...), ...))` and annotates off that
    alias — an expression deliberately NOT in the select list. `SELECT DISTINCT`
    constrains what ORDER BY may reference, and the cursor paginator orders by
    (-is_pinned, -last_post_at, -id), so this is where a bad interaction between
    the review-round `.distinct()` and the unread annotation would surface —
    as a 500, or as rows repeating across pages.
    """
    board = _board()
    author = User.objects.create_user(username="ada")
    viewer = User.objects.create_user(username="viewer")
    base = timezone.now()
    for i in range(25):
        topic = Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=base - datetime.timedelta(minutes=i),
        )
        topic.tags.add("monstera")

    client = APIClient()
    client.force_authenticate(viewer)
    first = client.get(f"/forum/boards/{board.slug}/topics/?tag=monstera")

    assert first.status_code == 200
    assert len(first.data["results"]) == 20  # page_size
    assert first.data["next"] is not None

    second = client.get(first.data["next"])  # the cursor URL must carry ?tag=
    assert second.status_code == 200

    slugs = [t["slug"] for t in first.data["results"] + second.data["results"]]
    # Every tagged topic exactly once — no duplicates across the page boundary,
    # and the filter is still applied on page 2.
    assert len(slugs) == 25
    assert len(set(slugs)) == 25
