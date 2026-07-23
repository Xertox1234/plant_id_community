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
