"""Tests for RAG retrieval (todo 289 / M13): the scored search core extracted
from ``find_similar_topics``, the ``BlogChunks`` index, and the passage merge.

No OpenAI call is ever made: gating/budget tests patch the index class (an
exhausted budget must short-circuit BEFORE the index — and its OpenAI-backed
transformer — is constructed); end-to-end tests use ``test_similar``'s
deterministic keyword-vector fake against the REAL pgvector store.
"""

from datetime import date
from unittest.mock import patch

import pytest
from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.forum_host import constants
from apps.forum_host import vector_indexes as vi
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding
from django_ai_core.llm import LLMService
from wagtail.models import Page, PageViewRestriction

from .test_similar import _FAKE_OPENAI_KEY, _fake_embedding

User = get_user_model()

INDEX = "apps.forum_host.vector_indexes.SimilarTopics"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


class _Doc:
    """Stand-in for a BaseStorageDocument (document_key, content, metadata, score)."""

    def __init__(self, key, score=0.9, **metadata):
        self.document_key = key
        self.content = f"content of {key}"
        self.metadata = metadata
        self.score = score


def _blog_index():
    try:
        return BlogIndexPage.objects.get(slug="blog")
    except BlogIndexPage.DoesNotExist:
        index = BlogIndexPage(title="Blog", slug="blog")
        Page.objects.get(id=1).add_child(instance=index)
        return index


def _post(title, blocks, *, slug=None, live=True, restricted=False, author=None):
    author = author or User.objects.create_user(username=f"author-{slug or title[:8]}")
    page = BlogPostPage(
        title=title,
        slug=slug or title.lower().replace(" ", "-"),
        author=author,
        publish_date=date(2026, 5, 1),
        introduction="<p>Intro.</p>",
        content_blocks=blocks,
        live=live,
    )
    _blog_index().add_child(instance=page)
    if live:
        page.save_revision().publish()
    if restricted:
        PageViewRestriction.objects.create(page=page, restriction_type="login")
    return page


# --------------------------------------------------------------------------- #
# _scored_search — the single place search_documents() is called              #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=False)
@pytest.mark.django_db
def test_scored_search_returns_none_when_feature_disabled():
    with patch(INDEX) as mock_index:
        assert vi._scored_search(vi.SimilarTopics, "tomato", 5) is None
    mock_index.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_scored_search_returns_none_for_blank_query():
    with patch(INDEX) as mock_index:
        assert vi._scored_search(vi.SimilarTopics, "   ", 5) is None
    mock_index.assert_not_called()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_scored_search_returns_none_when_embed_budget_exhausted_without_instantiating_index():
    cache.set(constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT, 3600)
    with patch(INDEX) as mock_index:
        assert vi._scored_search(vi.SimilarTopics, "tomato blight", 5) is None
    # No index instantiation — so no transformer, no embedding, no spend.
    mock_index.assert_not_called()
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) == constants.EMBED_BUDGET_LIMIT


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_scored_search_returns_scored_docs_and_consumes_one_unit():
    docs = [_Doc("wagtail_forum.Topic:1:0", 0.9), _Doc("wagtail_forum.Topic:2:0", 0.4)]
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = docs
        result = vi._scored_search(vi.SimilarTopics, "tomato blight", 5)
    # Scores survive — this is the whole reason the core exists (the Topic
    # wrapper throws them away, so a similarity floor cannot reuse it).
    assert [d.score for d in result] == [0.9, 0.4]
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) == 1


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_scored_search_distinguishes_an_empty_result_from_no_search():
    """Tri-state contract: ``[]`` means the search RAN (and was charged);
    ``None`` means it did not. A wrapper that caches results must never cache
    a ``None`` as an empty result during a budget outage."""
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = []
        result = vi._scored_search(vi.SimilarTopics, "tomato blight", 5)
    assert result == []
    assert result is not None
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) == 1


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_scored_search_provider_failure_returns_none_and_charges_nothing():
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.side_effect = RuntimeError("provider")
        assert vi._scored_search(vi.SimilarTopics, "tomato blight", 5) is None
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) is None


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_scored_search_caps_the_query_and_slices_to_limit():
    """The cap lives in the core so EVERY wrapper inherits it and cannot
    silently invalidate EMBED_BUDGET_LIMIT's cost math; the slice is what keeps
    an unsliced django-ai-core queryset from silently capping at 20."""
    long_query = "x" * (constants.SIMILAR_QUERY_MAX_CHARS + 250)
    docs = [_Doc(f"wagtail_forum.Topic:{i}:0") for i in range(10)]
    with patch(INDEX) as mock_index:
        mock_index.return_value.search_documents.return_value = docs
        result = vi._scored_search(vi.SimilarTopics, long_query, 3)
    embedded = mock_index.return_value.search_documents.call_args.args[0]
    assert len(embedded) == constants.SIMILAR_QUERY_MAX_CHARS
    assert len(result) == 3


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_find_similar_topics_does_not_cache_when_no_search_ran():
    """Refactor guard: with the budget exhausted the Topic wrapper must return
    ``[]`` WITHOUT writing a pk-cache entry — otherwise the outage would be
    remembered as "no similar topics" for SIMILAR_CACHE_TTL_SECONDS."""
    cache.set(constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT, 3600)
    with patch(INDEX):
        assert vi.find_similar_topics("tomato blight") == []
    assert (
        cache.get(vi._search_cache_key("tomato blight", constants.SIMILAR_TOPICS_LIMIT))
        is None
    )


# --------------------------------------------------------------------------- #
# BlogChunks — the chunked blog index                                          #
# --------------------------------------------------------------------------- #

BLOCKS = [
    {"type": "heading", "value": "Watering"},
    {"type": "paragraph", "value": "<p>Water pothos only when the soil is dry.</p>"},
    {"type": "heading", "value": "Light"},
    {
        "type": "paragraph",
        "value": "<p>Bright, indirect light keeps the leaves green.</p>",
    },
]


@pytest.mark.django_db
def test_blog_chunk_source_emits_per_chunk_documents_with_metadata_and_prefixed_keys():
    page = _post("Pothos care", BLOCKS, slug="pothos-care")
    source = vi.BlogChunkSource(BlogPostPage.objects.live().public())

    docs = list(source.get_documents())

    assert len(docs) == 2  # one chunk per heading section
    prefix = f"blog.BlogPostPage:{page.pk}:"
    assert all(d.document_key.startswith(prefix) for d in docs)
    assert len({d.document_key for d in docs}) == 2
    # Per-CHUNK metadata (the base class reuses one per-object dict for every
    # chunk, which is why _object_to_documents is overridden).
    assert [d.metadata["block_index"] for d in docs] == [0, 2]
    assert [d.metadata["heading_path"] for d in docs] == ["Watering", "Light"]
    assert docs[0].metadata["slug"] == "pothos-care"
    assert docs[0].metadata["title"] == "Pothos care"
    assert docs[0].metadata["pk"] == page.pk
    assert docs[0].metadata["source_id"] == "blog.BlogPostPage"
    assert "Water pothos only when the soil is dry." in docs[0].content


@pytest.mark.django_db
def test_blog_chunk_source_excludes_draft_and_restricted_pages():
    live = _post("Live post", BLOCKS, slug="live-post")
    _post("Draft post", BLOCKS, slug="draft-post", live=False)
    _post("Secret post", BLOCKS, slug="secret-post", restricted=True)

    docs = list(
        vi.BlogChunkSource(BlogPostPage.objects.live().public()).get_documents()
    )

    pks = {d.metadata["pk"] for d in docs}
    assert pks == {live.pk}


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_blog_chunks_build_purges_only_its_own_index_rows():
    """A rebuild must drop this index's stale rows (add() only upserts the keys
    it is handed, so a page that shrank would keep serving its old tail) — but
    NEVER touch another index's rows: every index shares one table, and the
    provider's clear() wipes all of them."""
    PgVectorEmbedding.objects.create(
        index_name=vi._index_name(vi.SimilarTopics),
        document_key="wagtail_forum.Topic:1:0",
        content="a topic",
        vector=[1.0] + [0.0] * 7,
    )
    PgVectorEmbedding.objects.create(
        index_name=vi._index_name(vi.BlogChunks),
        document_key="blog.BlogPostPage:999:0",
        content="stale chunk of a deleted page",
        vector=[1.0] + [0.0] * 7,
    )
    page = _post("Tomato care", BLOCKS, slug="tomato-care")

    with patch.object(LLMService, "embedding", _fake_embedding):
        vi.BlogChunks().build()

    keys = set(PgVectorEmbedding.objects.values_list("document_key", flat=True))
    assert "wagtail_forum.Topic:1:0" in keys  # the other index survives
    assert "blog.BlogPostPage:999:0" not in keys  # the stale row is gone
    assert {k for k in keys if k.startswith(f"blog.BlogPostPage:{page.pk}:")}
    assert vi._index_name(vi.BlogChunks) == "blogchunks_index"


# --------------------------------------------------------------------------- #
# retrieve_grounding_passages — floor, refetch, dedupe, merge, cap             #
# --------------------------------------------------------------------------- #

CORE = "apps.forum_host.rag_retrieval._scored_search"


def _topic_doc(topic, score, chunk=0):
    return _Doc(
        f"wagtail_forum.Topic:{topic.pk}:{chunk}",
        score,
        source_id="wagtail_forum.Topic",
        pk=topic.pk,
        model="wagtail_forum.Topic",
    )


def _blog_doc(page, score, block_index=0, chunk=0):
    return _Doc(
        f"blog.BlogPostPage:{page.pk}:{chunk}",
        score,
        source_id="blog.BlogPostPage",
        pk=page.pk,
        model="blog.BlogPostPage",
        block_index=block_index,
        heading_path="",
        slug=page.slug,
        title=page.title,
    )


def _core_returning(topic_docs=None, blog_docs=None):
    """A fake core: per-index results, ``None`` where nothing is configured."""

    def fake(index_cls, query, limit):
        if index_cls is vi.SimilarTopics:
            return topic_docs
        if index_cls is vi.BlogChunks:
            return blog_docs
        return None

    return fake


def _retrieve(question="how often to water", **kwargs):
    from apps.forum_host.rag_retrieval import retrieve_grounding_passages

    return retrieve_grounding_passages(question, **kwargs)


@pytest.mark.django_db
def test_below_floor_docs_are_discarded():
    from .test_similar import _topic

    strong = _topic("Tomato blight", "tomato blight", suffix="str")
    weak = _topic("Rose pruning", "prune a rose", suffix="wea")
    docs = [
        _topic_doc(strong, 0.9),
        _topic_doc(weak, constants.RAG_SIMILARITY_FLOOR - 0.01),
    ]
    with patch(CORE, side_effect=_core_returning(topic_docs=docs)):
        passages = _retrieve()
    assert [p.pk for p in passages] == [strong.pk]


@pytest.mark.django_db
def test_floor_is_read_at_call_time():
    from .test_similar import _topic

    topic = _topic("Tomato blight", "tomato blight", suffix="flo")
    with patch(CORE, side_effect=_core_returning(topic_docs=[_topic_doc(topic, 0.9)])):
        with patch.object(constants, "RAG_SIMILARITY_FLOOR", 0.95):
            assert _retrieve() == []
        assert [p.pk for p in _retrieve()] == [topic.pk]


@pytest.mark.django_db
def test_no_search_at_all_returns_none_not_an_empty_list():
    """Tri-state, like the core: when NO index searched (budget exhausted,
    provider down) the caller must say "unavailable", not "no information" —
    the latter is a confident claim about the corpus that was never checked."""
    with patch(CORE, side_effect=_core_returning()):
        assert _retrieve() is None


@pytest.mark.django_db
def test_one_index_searching_is_enough_for_a_list():
    from .test_similar import _topic

    topic = _topic("Tomato blight", "tomato blight", suffix="par")
    with patch(CORE, side_effect=_core_returning(topic_docs=[_topic_doc(topic, 0.9)])):
        passages = _retrieve()  # BlogChunks returned None (no search)
    assert [p.pk for p in passages] == [topic.pk]
    # Searched-but-empty is a list too: the corpus WAS checked.
    with patch(CORE, side_effect=_core_returning(topic_docs=[], blog_docs=[])):
        assert _retrieve() == []


@pytest.mark.django_db
def test_unpublished_topic_is_dropped_by_the_refetch():
    """The index may still hold a topic that was unpublished/moderated away
    after indexing; `live=True` in the refetch is what keeps it out (pinned on
    its own — the restricted-board test cannot catch this arm)."""
    from .test_similar import _topic

    live = _topic("Tomato live", "tomato", suffix="liv")
    gone = _topic("Tomato gone", "tomato", suffix="gon")
    gone.live = False
    gone.save(update_fields=["live"])
    docs = [_topic_doc(live, 0.9), _topic_doc(gone, 0.95)]
    with patch(CORE, side_effect=_core_returning(topic_docs=docs)):
        assert [p.pk for p in _retrieve()] == [live.pk]


@pytest.mark.django_db
def test_restricted_blog_page_is_dropped_by_the_refetch():
    """`.public()` in the blog refetch — a page restricted AFTER indexing must
    not leak through a stale chunk (pinned on its own, like the draft case)."""
    public = _post("Public post", BLOCKS, slug="public-rag")
    secret = _post("Secret post", BLOCKS, slug="secret-rag", restricted=True)
    docs = [_blog_doc(public, 0.9), _blog_doc(secret, 0.95)]
    with patch(CORE, side_effect=_core_returning(blog_docs=docs)):
        assert [p.pk for p in _retrieve()] == [public.pk]


@pytest.mark.django_db
def test_passages_are_deduped_per_source_object_keeping_the_best_chunk():
    page = _post("Pothos care", BLOCKS, slug="pothos-dedupe")
    docs = [
        _blog_doc(page, 0.5, block_index=0, chunk=0),
        _blog_doc(page, 0.8, block_index=2, chunk=1),
    ]
    with patch(CORE, side_effect=_core_returning(blog_docs=docs)):
        passages = _retrieve()
    assert len(passages) == 1
    assert passages[0].score == 0.8
    assert passages[0].anchor == "block-2"


@pytest.mark.django_db
def test_merge_orders_by_score_across_corpora_and_renumbers_from_one():
    from .test_similar import _topic

    t_low = _topic("Tomato low", "tomato", suffix="low")
    t_mid = _topic("Tomato mid", "tomato", suffix="mid")
    page = _post("Pothos care", BLOCKS, slug="pothos-merge")
    with patch(
        CORE,
        side_effect=_core_returning(
            topic_docs=[_topic_doc(t_mid, 0.7), _topic_doc(t_low, 0.6)],
            blog_docs=[_blog_doc(page, 0.9)],
        ),
    ):
        passages = _retrieve()
    assert [(p.kind, p.pk) for p in passages] == [
        ("blog", page.pk),
        ("topic", t_mid.pk),
        ("topic", t_low.pk),
    ]
    assert [p.n for p in passages] == [1, 2, 3]


@pytest.mark.django_db
def test_caps_at_max_passages_and_max_context_chars():
    from .test_similar import _topic

    topics = [_topic(f"Tomato {i}", "tomato", suffix=f"cap{i}") for i in range(4)]
    docs = [_topic_doc(t, 0.9 - i * 0.01) for i, t in enumerate(topics)]
    with patch(CORE, side_effect=_core_returning(topic_docs=docs)):
        with patch.object(constants, "RAG_MAX_PASSAGES", 2):
            assert len(_retrieve()) == 2
        # Each fake doc's content is ~35 chars; a 40-char context budget fits one.
        with patch.object(constants, "RAG_MAX_CONTEXT_CHARS", 40):
            assert len(_retrieve()) == 1


@pytest.mark.django_db
def test_topic_passages_refetch_through_visible_boards_and_block_filter():
    from wagtail_forum.models import UserBlock

    from .test_similar import _board, _topic

    public = _topic("Tomato public", "tomato", suffix="pub")
    secret = _topic(
        "Tomato secret",
        "tomato",
        suffix="sec",
        board=_board(suffix="sec", restricted=True),
    )
    blocked = _topic("Tomato blocked", "tomato", suffix="blk")
    viewer = User.objects.create_user(username="rag-viewer")
    UserBlock.block(viewer, blocked.author)
    docs = [_topic_doc(public, 0.9), _topic_doc(secret, 0.9), _topic_doc(blocked, 0.9)]

    with patch(CORE, side_effect=_core_returning(topic_docs=docs)):
        unfiltered = {p.pk for p in _retrieve()}
        for_viewer = {p.pk for p in _retrieve(user=viewer)}

    # Restricted-board content never leaks, whoever asks; the block filter is
    # opt-in via user= (safe here: the RAG response is never cross-user cached).
    assert unfiltered == {public.pk, blocked.pk}
    assert for_viewer == {public.pk}


@pytest.mark.django_db
def test_topic_passage_carries_the_fields_the_client_needs_to_build_a_link():
    from .test_similar import _topic

    topic = _topic("Tomato blight", "tomato blight", suffix="lnk")
    with patch(CORE, side_effect=_core_returning(topic_docs=[_topic_doc(topic, 0.9)])):
        (p,) = _retrieve()
    assert p.kind == "topic"
    assert (p.topic_id, p.topic_slug, p.board_id, p.board_slug) == (
        topic.pk,
        topic.slug,
        topic.board_id,
        topic.board.slug,
    )
    assert p.title == "Tomato blight"
    assert p.date == topic.created_at.isoformat()
    assert p.text and p.snippet


@pytest.mark.django_db
def test_blog_passages_refetch_through_live_public_and_null_anchor_on_index_drift():
    live = _post("Live post", BLOCKS, slug="live-rag")
    draft = _post("Draft post", BLOCKS, slug="draft-rag", live=False)
    docs = [
        _blog_doc(live, 0.9, block_index=2),
        _blog_doc(draft, 0.95, block_index=0),
        _blog_doc(live, 0.8, block_index=99, chunk=1),
    ]
    with patch(CORE, side_effect=_core_returning(blog_docs=docs)):
        passages = _retrieve()
    assert [p.pk for p in passages] == [live.pk]  # draft dropped; deduped
    assert passages[0].anchor == "block-2"
    assert passages[0].slug == "live-rag"
    assert passages[0].date == "2026-05-01"

    # An edit that removed blocks after indexing: the best chunk now points past
    # the end of raw_data, so the citation degrades to the article, not a 404.
    drifted = [_blog_doc(live, 0.9, block_index=99)]
    with patch(CORE, side_effect=_core_returning(blog_docs=drifted)):
        (p,) = _retrieve()
    assert p.anchor is None


@pytest.mark.django_db
def test_unknown_source_id_is_ignored():
    stray = _Doc("plant_care.Note:1:0", 0.99, source_id="plant_care.Note", pk=1)
    with patch(CORE, side_effect=_core_returning(topic_docs=[stray])):
        assert _retrieve() == []


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_end_to_end_retrieves_a_blog_chunk_and_a_topic_above_the_floor():
    from .test_similar import _topic

    topic = _topic("Tomato blight help", "my tomato has blight", suffix="e2e")
    page = _post(
        "Tomato blight",
        [
            {"type": "heading", "value": "Blight"},
            {
                "type": "paragraph",
                "value": "<p>Tomato blight spreads in wet weather.</p>",
            },
        ],
        slug="tomato-blight-e2e",
    )
    _topic("Compost and soil", "best compost for soil", suffix="e2s")

    with patch.object(LLMService, "embedding", _fake_embedding):
        vi.SimilarTopics().build()
        vi.BlogChunks().build()
        passages = _retrieve("tomato blight")

    assert {(p.kind, p.pk) for p in passages} == {
        ("topic", topic.pk),
        ("blog", page.pk),
    }
    assert all(p.score >= constants.RAG_SIMILARITY_FLOOR for p in passages)
    assert cache.get(constants.EMBED_BUDGET_CACHE_KEY) == 2  # one unit per index


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_end_to_end_unrelated_question_returns_nothing_above_the_floor():
    from .test_similar import _topic

    _topic("Tomato blight help", "my tomato has blight", suffix="unr")
    _post("Tomato blight", BLOCKS, slug="tomato-unrelated")

    with patch.object(LLMService, "embedding", _fake_embedding):
        vi.SimilarTopics().build()
        vi.BlogChunks().build()
        passages = _retrieve("rose pruning")

    assert passages == []
