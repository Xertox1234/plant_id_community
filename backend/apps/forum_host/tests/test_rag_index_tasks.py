"""Tests for BlogChunks index maintenance (todo 289 / M13): the per-page
``sync_blog_page_chunks`` task and the blog page-lifecycle receivers that
enqueue it. Rebuild-on-publish is 100% host code — django-ai-core's own
``post_save`` receiver is never connected (and would be wrong if it were).
"""

from unittest.mock import patch

import pytest
from apps.blog.models import BlogIndexPage
from apps.forum_host import constants
from apps.forum_host import vector_indexes as vi
from apps.forum_host.tasks import sync_blog_page_chunks
from django.core.cache import cache
from django.test import override_settings
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding
from django_ai_core.llm import LLMService
from wagtail.models import Page

from .test_rag_retrieval import BLOCKS, _post
from .test_similar import _FAKE_OPENAI_KEY, _fake_embedding

ENABLED = dict(FORUM_RAG_ENABLED=True, FORUM_VECTOR_SEARCH_ENABLED=True)
TASK = "apps.forum_host.signals.sync_blog_page_chunks"
# BlogChunks.__init__ builds the OpenAI transformer through this; "it was never
# called" is the key-free proof that the task embedded nothing.
TRANSFORMER = "apps.forum_host.vector_indexes._build_embedding_transformer"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _seed(index_cls, key, content="stale"):
    return PgVectorEmbedding.objects.create(
        index_name=vi._index_name(index_cls),
        document_key=key,
        content=content,
        vector=[1.0] + [0.0] * 7,
    )


def _page_keys(page_id):
    return set(
        PgVectorEmbedding.objects.filter(
            index_name=vi._index_name(vi.BlogChunks),
            document_key__startswith=f"blog.BlogPostPage:{page_id}:",
        ).values_list("document_key", flat=True)
    )


# --------------------------------------------------------------------------- #
# The task                                                                     #
# --------------------------------------------------------------------------- #


def test_task_declares_retry_config():
    """docs/rules/celery.md: every network-touching task declares its retry
    policy, and this one is idempotent (purge-then-add) so it can be acked late."""
    assert Exception in sync_blog_page_chunks.autoretry_for
    assert sync_blog_page_chunks.retry_backoff is True
    assert sync_blog_page_chunks.max_retries == constants.RAG_INDEX_MAX_RETRIES
    assert sync_blog_page_chunks.acks_late is True


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_task_reindexes_a_live_public_page_replacing_stale_chunks():
    """add() only upserts the keys it is handed, so a page that shrank from 9
    chunks to 2 would keep serving :2–:8 forever without the purge."""
    with patch(TASK):  # keep the publish signal from enqueueing during setup
        page = _post("Pothos care", BLOCKS, slug="pothos-sync")
    for i in range(9):
        _seed(vi.BlogChunks, f"blog.BlogPostPage:{page.pk}:{i}")
    _seed(vi.BlogChunks, "blog.BlogPostPage:999:0", "another page's chunk")
    _seed(vi.SimilarTopics, "wagtail_forum.Topic:1:0", "a topic")

    with patch.object(LLMService, "embedding", _fake_embedding):
        sync_blog_page_chunks(page.pk)

    assert _page_keys(page.pk) == {
        f"blog.BlogPostPage:{page.pk}:0",
        f"blog.BlogPostPage:{page.pk}:1",
    }
    fresh = PgVectorEmbedding.objects.get(document_key=f"blog.BlogPostPage:{page.pk}:0")
    assert "Water pothos only when the soil is dry." in fresh.content
    assert fresh.metadata["block_index"] == 0
    # Other pages and the other index are untouched.
    assert PgVectorEmbedding.objects.filter(
        document_key="blog.BlogPostPage:999:0"
    ).exists()
    assert PgVectorEmbedding.objects.filter(
        document_key="wagtail_forum.Topic:1:0"
    ).exists()


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_task_purges_chunks_for_a_missing_or_unpublished_page():
    with patch(TASK):
        draft = _post("Draft post", BLOCKS, slug="draft-sync", live=False)
    _seed(vi.BlogChunks, f"blog.BlogPostPage:{draft.pk}:0")
    _seed(vi.BlogChunks, "blog.BlogPostPage:424242:0")

    with patch(TRANSFORMER) as mock_transformer:
        sync_blog_page_chunks(draft.pk)
        sync_blog_page_chunks(424242)

    assert _page_keys(draft.pk) == set()
    assert _page_keys(424242) == set()
    mock_transformer.assert_not_called()  # nothing to embed → no transformer, no key


@override_settings(FORUM_RAG_ENABLED=False, FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_task_purges_but_does_not_embed_when_the_feature_is_off():
    """Deleting is free; embedding is not. A task that raced a flag flip must
    not spend on a dark feature."""
    with patch(TASK):
        page = _post("Pothos care", BLOCKS, slug="pothos-dark")
    _seed(vi.BlogChunks, f"blog.BlogPostPage:{page.pk}:7")

    with patch(TRANSFORMER) as mock_transformer:
        sync_blog_page_chunks(page.pk)

    assert _page_keys(page.pk) == set()
    mock_transformer.assert_not_called()


# --------------------------------------------------------------------------- #
# The receivers                                                                #
# --------------------------------------------------------------------------- #


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_page_published_enqueues_the_sync_when_the_feature_is_on():
    with patch(TASK) as mock_task:
        page = _post("Pothos care", BLOCKS, slug="pothos-publish")
    mock_task.delay.assert_called_once_with(page.pk)


@override_settings(FORUM_RAG_ENABLED=False, FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_page_published_does_not_enqueue_when_the_feature_is_off():
    with patch(TASK) as mock_task:
        _post("Pothos care", BLOCKS, slug="pothos-off")
    mock_task.delay.assert_not_called()


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_page_unpublished_and_deleted_enqueue_the_sync():
    with patch(TASK):
        page = _post("Pothos care", BLOCKS, slug="pothos-unpublish")
    with patch(TASK) as mock_task:
        page.unpublish()
    mock_task.delay.assert_called_once_with(page.pk)

    pk = page.pk
    with patch(TASK) as mock_task:
        page.delete()
    mock_task.delay.assert_called_once_with(pk)


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_non_blog_pages_are_ignored():
    """page_published fires for EVERY Wagtail page type."""
    index = BlogIndexPage(title="Another index", slug="another-index")
    Page.objects.get(id=1).add_child(instance=index)
    with patch(TASK) as mock_task:
        index.save_revision().publish()
    mock_task.delay.assert_not_called()


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_broker_failure_is_logged_not_raised():
    """A publish must never fail because the broker is down (the blog signals'
    own <5ms / try-except posture). Asserted on the module logger: the
    project's JSON logging does not propagate to caplog."""
    with patch(TASK) as mock_task, patch(
        "apps.forum_host.signals.logger"
    ) as mock_logger:
        mock_task.delay.side_effect = RuntimeError("broker down")
        page = _post("Pothos care", BLOCKS, slug="pothos-broker")
    assert page.live is True
    mock_logger.exception.assert_called_once()
    assert "[CELERY]" in mock_logger.exception.call_args.args[0]
