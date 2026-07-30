"""Tests for the premium semantic section on forum search (todo 275 / M12).

The vector layer itself is covered by test_similar.py; here find_similar_topics is
patched so these tests pin the *endpoint* contract: opt-in, entitlement gating,
feature gating, response shape, FTS-paging non-interference, and — the one place
this feature could leak — that a semantic-bearing response is never
shared-cacheable.
"""

from unittest.mock import patch

import pytest
from apps.forum_host import constants
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

SEARCH_URL = "/api/v1/forum/search/"
FIND = "apps.forum_host.semantic_search.find_similar_topics"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _topic(title="Tomato blight", body="tomato blight on leaves"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="poster")
    topic = Topic.objects.create(
        board=board, title=title, slug="tomato-blight", author=author
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{body}</p>"}],
    )
    return topic


def _premium_client():
    user = User.objects.create_user(username="premiumsearcher", is_premium=True)
    client = APIClient()
    client.force_authenticate(user)
    return client


# --------------------------------------------------------------------------- #
# Opt-in: without ?semantic=1 nothing changes                                  #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_without_semantic_param_response_has_no_semantic_keys():
    """The default response must stay byte-compatible for existing clients, and
    must not embed (spend) for callers who never asked for semantic results."""
    client = _premium_client()
    with patch(FIND) as mock_find:
        resp = client.get(SEARCH_URL, {"q": "tomato"})
    assert resp.status_code == 200
    body = resp.json()
    assert "semantic" not in body
    assert "semantic_status" not in body
    mock_find.assert_not_called()


# --------------------------------------------------------------------------- #
# Entitlement + feature gating                                                 #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_anonymous_semantic_request_reports_premium_required():
    with patch(FIND) as mock_find:
        resp = APIClient().get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
    assert resp.status_code == 200  # FTS search itself stays public
    body = resp.json()
    assert body["semantic"] == []
    assert body["semantic_status"] == "premium_required"
    mock_find.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_non_premium_user_semantic_request_reports_premium_required():
    user = User.objects.create_user(username="basicsearcher")  # is_premium False
    client = APIClient()
    client.force_authenticate(user)
    with patch(FIND) as mock_find:
        resp = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
    assert resp.json()["semantic_status"] == "premium_required"
    mock_find.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=False)
@pytest.mark.django_db
def test_premium_user_gets_unavailable_when_vector_search_is_disabled():
    client = _premium_client()
    with patch(FIND) as mock_find:
        resp = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
    body = resp.json()
    assert body["semantic"] == []
    assert body["semantic_status"] == "unavailable"
    # Gated BEFORE the helper, so a disabled deployment cannot embed at all.
    mock_find.assert_not_called()


# --------------------------------------------------------------------------- #
# Happy path + response shape                                                  #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_premium_semantic_hits_use_the_same_shape_as_fts_topic_hits():
    """Identical keys let clients reuse one result renderer for both sections."""
    topic = _topic()
    client = _premium_client()
    with patch(FIND, return_value=[topic]) as mock_find:
        resp = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
    body = resp.json()
    assert body["semantic_status"] == "ok"
    assert len(body["semantic"]) == 1
    hit = body["semantic"][0]
    assert hit["id"] == topic.id
    assert hit["slug"] == topic.slug
    assert hit["board_id"] == topic.board_id
    assert hit["board_slug"] == topic.board.slug
    assert set(hit) == {
        "id",
        "slug",
        "title",
        "reply_count",
        "view_count",
        "last_post_at",
        "board_id",
        "board_slug",
    }
    mock_find.assert_called_once()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_semantic_hits_are_not_spliced_into_the_paged_fts_list():
    """The semantic array is deliberately a SEPARATE key: merging it into
    `topics` would make `page`/`*_has_more` describe a window that no longer
    exists, so a client paging the FTS list would skip or repeat rows.

    Uses a semantic hit that the FTS query does NOT match, so "did it leak into
    `topics`?" has an unambiguous answer."""
    fts_hit = _topic()  # title/body both contain "tomato"
    semantic_only = Topic.objects.create(
        board=fts_hit.board,
        title="Watering schedule for seedlings",
        slug="watering-schedule",
        author=fts_hit.author,
    )
    client = _premium_client()
    with patch(FIND, return_value=[semantic_only]):
        body = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"}).json()

    assert {"topics", "posts", "topics_has_more", "posts_has_more"} <= set(body)
    assert [h["id"] for h in body["semantic"]] == [semantic_only.id]
    # The semantic-only topic must NOT appear in the keyword-ranked, paged list.
    assert semantic_only.id not in [t["id"] for t in body["topics"]]
    assert body["topics_has_more"] is False


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_board_filter_is_forwarded_to_the_semantic_search():
    client = _premium_client()
    with patch(FIND, return_value=[]) as mock_find:
        client.get(SEARCH_URL, {"q": "tomato", "semantic": "1", "board": "general"})
    assert mock_find.call_args.kwargs.get("board_slug") == "general"


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_long_query_is_forwarded_for_the_helper_to_cap():
    """The length cap lives in `find_similar_topics`, not here (todo 275 review) —
    one place, so a future caller cannot forget it and silently invalidate
    EMBED_BUDGET_LIMIT's cost math. `test_similar.py` pins the cap itself; this
    pins that the section forwards the query and survives a long one.

    Uses ONE long token rather than many repeated terms: a many-term query
    (~500 terms) trips a RecursionError in Wagtail's search-query parser and
    500s the endpoint — a pre-existing FTS bug on the public search path,
    unrelated to this feature and tracked as todo 290."""
    client = _premium_client()
    long_q = "tomato" + "a" * (constants.SIMILAR_QUERY_MAX_CHARS + 100)
    with patch(FIND, return_value=[]) as mock_find:
        resp = client.get(SEARCH_URL, {"q": long_q, "semantic": "1"})
    assert resp.status_code == 200
    assert mock_find.call_args.args[0] == long_q


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_semantic_helper_raising_still_returns_fts_results():
    """find_similar_topics is contractually non-raising, but core keyword search
    must not 500 for premium users if that contract is ever broken upstream."""
    _topic()
    client = _premium_client()
    with patch(FIND, side_effect=RuntimeError("vector store down")):
        resp = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["semantic"] == []
    # Deliberately still "ok", not a distinct failure status: this endpoint does
    # not surface operational state to clients (same reason an exhausted embedding
    # budget reports "ok" with no results). Pinned so the value reads as intended
    # rather than as an accident of exception-handling order.
    assert body["semantic_status"] == "ok"
    assert len(body["topics"]) == 1  # FTS results still served


# --------------------------------------------------------------------------- #
# Cache-header safety — the one place this feature could leak                  #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_semantic_response_is_never_shared_cacheable():
    """A semantic-bearing response is entitlement-dependent, so it must never be
    storable by the CDN (PublicForumReadCacheMixin marks anonymous reads
    `public, s-maxage=...`). It is only ever produced for an AUTHENTICATED user,
    which forces `private, no-store` — asserted here rather than inferred."""
    topic = _topic()
    client = _premium_client()
    with patch(FIND, return_value=[topic]):
        resp = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
    assert resp["Cache-Control"] == "private, no-store"
    assert "Cookie" in resp["Vary"]
    assert "Authorization" in resp["Vary"]


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_anonymous_search_is_still_shared_cacheable():
    """Regression guard: adding the mixin must not have downgraded the public
    anonymous-search caching that audit M42 established."""
    _topic()
    resp = APIClient().get(SEARCH_URL, {"q": "tomato"})
    assert resp.status_code == 200
    assert resp["Cache-Control"].startswith("public, s-maxage=")


# --------------------------------------------------------------------------- #
# Throttling still applies to the composed view                                #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, FORUM_RATELIMITS={"search": "1/m"})
@pytest.mark.django_db
def test_throttle_survives_the_mixin_and_429_carries_no_semantic_keys():
    """The mixin composes UNDER the throttle decorator (`_throttled` is applied
    to the host class, so it wraps the mixin's `get`). A subclass that overrode
    `get` instead would silently drop the throttle — this fails if that happens.
    The 429 body must also stay untouched (no `semantic` keys grafted onto it)."""
    client = _premium_client()
    with freeze_time("2026-07-29 12:00:00"), patch(FIND, return_value=[]):
        first = client.get(SEARCH_URL, {"q": "tomato", "semantic": "1"})
        second = client.get(SEARCH_URL, {"q": "rose", "semantic": "1"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert "semantic" not in second.json()
