"""Tests for the forum semantic "similar topics" feature (todo 255 slice 4 / H15):
the gated GET endpoint, the find_similar_topics helper, and an end-to-end
pgvector build+search using a deterministic fake embedder (no OpenAI call).
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from apps.forum_host.vector_indexes import SimilarTopics, find_similar_topics
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django_ai_core.llm import LLMService
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

SIMILAR_URL = "/api/v1/forum/topics/similar/"
FIND = "apps.forum_host.similar.find_similar_topics"

# Any non-empty value satisfies LLMService.create's presence check; the real
# embedding call is patched out, so no OpenAI request is ever made.
_FAKE_OPENAI_KEY = "unit-test-key"  # pragma: allowlist secret

# Deterministic fake embedding: an 8-dim keyword-presence vector. Similar text →
# similar vector → meaningful cosine ranking, with zero network/OpenAI calls.
KEYWORDS = ["tomato", "blight", "rose", "prune", "soil", "compost", "water", "seed"]


def _fake_vector(text: str) -> list[float]:
    t = (text or "").lower()
    v = [1.0 if kw in t else 0.0 for kw in KEYWORDS]
    if not any(v):  # avoid a zero vector (cosine distance is undefined)
        v[-1] = 1e-6
    return v


def _fake_embedding(self, inputs, *args, **kwargs):
    items = [inputs] if isinstance(inputs, str) else list(inputs)
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=_fake_vector(t)) for t in items]
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _board(suffix="", restricted=False):
    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title=f"Forum{suffix}", slug=f"forum{suffix}")
    )
    board = index.add_child(
        instance=ForumBoard(title=f"General{suffix}", slug=f"general{suffix}")
    )
    if restricted:
        PageViewRestriction.objects.create(page=board, restriction_type="login")
    return board


def _topic(title, body_text, *, suffix="", board=None):
    author = User.objects.create_user(username=f"a{suffix}{title[:4]}".replace(" ", ""))
    board = board or _board(suffix)
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=f"t{suffix}{title[:6]}".replace(" ", ""),
        author=author,
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{body_text}</p>"}],
    )
    return topic


# --------------------------------------------------------------------------- #
# Endpoint — gating / validation / serialization (find_similar_topics mocked)  #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=False)
@pytest.mark.django_db
def test_disabled_returns_503():
    with patch(FIND) as mock_find:
        resp = APIClient().get(SIMILAR_URL, {"q": "tomato"})
    assert resp.status_code == 503
    mock_find.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_blank_query_returns_400():
    with patch(FIND) as mock_find:
        resp = APIClient().get(SIMILAR_URL, {"q": "   "})
    assert resp.status_code == 400
    mock_find.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_returns_serialized_ranked_results():
    topic = _topic("Tomato blight", "tomato blight on leaves")
    with patch(FIND, return_value=[topic]) as mock_find:
        resp = APIClient().get(SIMILAR_URL, {"q": "tomato"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == topic.id
    assert results[0]["slug"] == topic.slug
    assert results[0]["board_slug"] == topic.board.slug
    mock_find.assert_called_once()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_board_filter_is_passed_through():
    with patch(FIND, return_value=[]) as mock_find:
        APIClient().get(SIMILAR_URL, {"q": "tomato", "board": "general"})
    assert mock_find.call_args.kwargs.get("board_slug") == "general"


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_result_cache_hit_skips_second_search():
    topic = _topic("Tomato blight", "tomato blight")
    with patch(FIND, return_value=[topic]) as mock_find:
        first = APIClient().get(SIMILAR_URL, {"q": "tomato"})
        second = APIClient().get(SIMILAR_URL, {"q": "tomato"})
    assert first.status_code == second.status_code == 200
    # Second identical query is served from the result cache — no re-embed.
    mock_find.assert_called_once()


@override_settings(
    FORUM_VECTOR_SEARCH_ENABLED=True, FORUM_RATELIMITS={"similar_topics": "1/m"}
)
@pytest.mark.django_db
def test_similar_get_is_throttled_per_ip():
    with freeze_time("2026-07-22 12:00:00"), patch(FIND, return_value=[]):
        first = APIClient().get(SIMILAR_URL, {"q": "tomato"})
        second = APIClient().get(SIMILAR_URL, {"q": "rose"})
    assert first.status_code == 200
    assert second.status_code == 429


# --------------------------------------------------------------------------- #
# find_similar_topics — gating                                                 #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=False)
@pytest.mark.django_db
def test_find_returns_empty_when_feature_disabled():
    assert find_similar_topics("tomato") == []


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_find_returns_empty_for_blank_query():
    assert find_similar_topics("   ") == []


# --------------------------------------------------------------------------- #
# Dedicated query-embedding budget (todo 275 / AC4)                            #
# --------------------------------------------------------------------------- #

# Patching the whole index class keeps these tests key-free: an exhausted budget
# must short-circuit BEFORE SimilarTopics() is constructed (its __init__ builds
# the OpenAI-backed transformer), which is exactly what the first test pins.
INDEX = "apps.forum_host.vector_indexes.SimilarTopics"


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_exhausted_embed_budget_returns_empty_without_searching():
    from apps.forum_host import constants

    cache.set(constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT, 3600)
    with patch(INDEX) as mock_index:
        assert find_similar_topics("tomato blight") == []
    # No index instantiation at all — so no embedding call and no OpenAI spend.
    mock_index.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_successful_search_consumes_one_unit_of_embed_budget():
    from apps.forum_host import constants

    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = []
        assert find_similar_topics("tomato blight") == []
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) == 1


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_provider_failure_does_not_consume_embed_budget():
    """Peek-then-consume, not check-and-increment: a sustained provider outage
    must not drain the cap via failed attempts and lock the feature off."""
    from apps.forum_host import constants

    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.side_effect = RuntimeError("provider")
        assert find_similar_topics("tomato blight") == []
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) is None


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_query_is_capped_inside_the_helper_not_at_the_call_sites():
    """The cap lives in find_similar_topics (todo 275 review) so every caller —
    the endpoint, the M12 search section, a future RAG retrieval — inherits it and
    cannot silently invalidate EMBED_BUDGET_LIMIT's cost math by forgetting it."""
    from apps.forum_host import constants

    long_query = "x" * (constants.SIMILAR_QUERY_MAX_CHARS + 250)
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = []
        find_similar_topics(long_query)
    embedded = mock_index.return_value.search_documents.call_args.args[0]
    assert len(embedded) == constants.SIMILAR_QUERY_MAX_CHARS


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_repeat_query_hits_the_pk_cache_and_does_not_re_embed():
    """A premium client paging `/search/?semantic=1` re-issues the identical query
    per page; without this cache each page re-embeds it (todo 275 review)."""
    from apps.forum_host import constants

    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = []
        find_similar_topics("tomato blight")
        find_similar_topics("tomato blight")
    # One vector search, one budget unit — not two.
    assert mock_index.return_value.search_documents.call_count == 1
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) == 1


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_pk_cache_is_keyed_on_exactly_what_reaches_the_vector_store():
    """Query and limit change the vector query, so each needs its own entry.

    `board_slug` must NOT be in the key: it never reaches `search_documents`, only
    the visibility refetch afterwards, so the cached pk list is identical across
    board slugs. Keying on it would fragment the cache and make a board-scoped
    search re-embed a query the unscoped one already paid for."""
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = []
        find_similar_topics("tomato blight")
        find_similar_topics("rose pruning")  # different query -> re-embeds
        find_similar_topics("tomato blight", limit=2)  # different slice -> re-embeds
        find_similar_topics("tomato blight", board_slug="general")  # reuses entry 1
    assert mock_index.return_value.search_documents.call_count == 3


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_embed_budget_does_not_touch_the_shared_blog_completion_counter():
    """The whole point of AC4: embedding spend has its OWN counter, so it can
    neither starve nor be starved by the blog's `ai_rate_limit:global` quota."""
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = []
        find_similar_topics("tomato blight")
    assert cache.get("ai_rate_limit:global") is None


# --------------------------------------------------------------------------- #
# End-to-end pgvector build + search (deterministic fake embedder)             #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_similar_topics_ranks_by_semantic_similarity():
    tomato = _topic("Tomato blight help", "my tomato has blight", suffix="tom")
    _topic("Rose pruning", "how to prune a rose", suffix="ros")
    _topic("Compost and soil", "best compost for soil", suffix="soi")

    with patch.object(LLMService, "embedding", _fake_embedding):
        SimilarTopics().build()  # real pgvector store
        results = find_similar_topics("tomato blight", limit=2)

    assert results, "expected at least one similar topic"
    assert results[0].id == tomato.id  # closest by keyword-vector cosine


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_similar_topics_excludes_restricted_board():
    public = _topic("Tomato blight", "tomato blight", suffix="pub")
    secret_board = _board(suffix="secret", restricted=True)
    secret = _topic(
        "Tomato secret", "tomato blight classified", suffix="sec", board=secret_board
    )

    with patch.object(LLMService, "embedding", _fake_embedding):
        SimilarTopics().build()
        results = find_similar_topics("tomato blight")

    ids = {t.id for t in results}
    assert public.id in ids
    # A restricted-board topic is never embedded nor returned (authz boundary).
    assert secret.id not in ids


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_user_param_excludes_a_blocked_authors_topic():
    # todo 284/M9: user= is opt-in — the compose-time SimilarTopicsView never
    # passes it (shared, unkeyed-by-user result cache), but the helper itself
    # must filter correctly when a caller (semantic_search.py) does.
    from wagtail_forum.models import UserBlock

    public = _topic("Tomato blight", "tomato blight", suffix="pub")
    blocked_topic = _topic("Tomato secrets", "tomato blight advice", suffix="blk")
    viewer = User.objects.create_user(username="similar-viewer")
    UserBlock.block(viewer, blocked_topic.author)

    with patch.object(LLMService, "embedding", _fake_embedding):
        SimilarTopics().build()
        results = find_similar_topics("tomato blight", user=viewer)

    ids = {t.id for t in results}
    assert public.id in ids
    assert blocked_topic.id not in ids


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_default_user_none_does_not_filter_by_block():
    # The default (no user=) must stay unfiltered — SimilarTopicsView relies
    # on this for its shared cross-user result cache.
    from wagtail_forum.models import UserBlock

    topic = _topic("Tomato blight", "tomato blight", suffix="nou")
    someone = User.objects.create_user(username="similar-blocker")
    UserBlock.block(someone, topic.author)

    with patch.object(LLMService, "embedding", _fake_embedding):
        SimilarTopics().build()
        results = find_similar_topics("tomato blight")

    assert topic.id in {t.id for t in results}


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_board_filter_narrows_results_to_that_board():
    board_a = _board(suffix="a")
    board_b = _board(suffix="b")
    ta = _topic("Tomato A", "tomato blight", suffix="ta", board=board_a)
    _topic("Tomato B", "tomato blight", suffix="tb", board=board_b)

    with patch.object(LLMService, "embedding", _fake_embedding):
        SimilarTopics().build()
        results = find_similar_topics("tomato blight", board_slug=board_a.slug)

    ids = {t.id for t in results}
    assert ta.id in ids
    assert all(t.board_id == board_a.id for t in results)
