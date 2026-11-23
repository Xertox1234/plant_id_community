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
    policy, and this one is idempotent (purge-then-add) so it can be acked late.
    ``retry_backoff`` is the FACTOR: ``True`` would mean a factor of 1 (~1s/2s/4s
    countdowns) and ``default_retry_delay`` is ignored on the autoretry path."""
    assert Exception in sync_blog_page_chunks.autoretry_for
    assert sync_blog_page_chunks.retry_backoff == constants.RAG_INDEX_RETRY_DELAY
    assert sync_blog_page_chunks.max_retries == constants.RAG_INDEX_MAX_RETRIES
    assert sync_blog_page_chunks.acks_late is True
    assert sync_blog_page_chunks.ignore_result is True  # side-effect only


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
@pytest.mark.parametrize("prior_retries, ceiling", [(0, 30), (1, 60), (2, 120)])
def test_autoretry_countdown_is_exponential_from_the_retry_delay(
    prior_retries, ceiling
):
    """.apply() proves attempt COUNTS but ignores countdown (docs/rules/celery.md),
    so the values are pinned the send_forum_push way: fake the retry counter,
    mock retry(), and read the countdown the autoretry wrapper computes. Full
    jitter is patched to its maximum so the ceiling is observable."""
    from celery.exceptions import Retry
    from django_ai_core.contrib.index.embedding_cache import CachedEmbeddingTransformer

    with patch(TASK):
        page = _post("Pothos care", BLOCKS, slug=f"pothos-backoff-{prior_retries}")

    with patch.object(
        CachedEmbeddingTransformer, "embed_documents", side_effect=RuntimeError("down")
    ), patch(
        "celery.utils.time.random.randrange", side_effect=lambda n: n - 1
    ), patch.object(
        sync_blog_page_chunks, "retry", side_effect=Retry("retried")
    ) as mock_retry:
        sync_blog_page_chunks.push_request(retries=prior_retries)
        try:
            with pytest.raises(Retry):
                sync_blog_page_chunks.run(page.pk)
        finally:
            sync_blog_page_chunks.pop_request()

    assert mock_retry.call_args.kwargs["countdown"] == ceiling


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_chunking_failure_is_logged_and_not_retried():
    """A malformed content_blocks value is a PERMANENT error — retrying it three
    times with backoff cannot help. Logged with the page id, existing rows kept
    (stale content beats none), no Retry raised."""
    with patch(TASK):
        page = _post("Pothos care", BLOCKS, slug="pothos-badblocks")
    _seed(vi.BlogChunks, f"blog.BlogPageold:{page.pk}:0")  # unrelated prefix, untouched
    _seed(vi.BlogChunks, f"blog.BlogPostPage:{page.pk}:0", "old but valid chunk")

    with patch(
        "apps.forum_host.vector_indexes.chunk_blocks",
        side_effect=ValueError("bad block"),
    ), patch("apps.forum_host.tasks.logger") as mock_logger, patch.object(
        sync_blog_page_chunks, "retry"
    ) as mock_retry:
        sync_blog_page_chunks.run(page.pk)  # must not raise

    mock_retry.assert_not_called()
    mock_logger.exception.assert_called_once()
    assert "[CELERY]" in mock_logger.exception.call_args.args[0]
    assert _page_keys(page.pk) == {f"blog.BlogPostPage:{page.pk}:0"}


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_page_unpublished_during_the_embed_is_not_resurrected():
    """Idempotency under interleaving: a run whose embed straddles a concurrent
    unpublish (whose own task already purged) must not add the page back. The
    live/public state is re-checked inside the swap transaction."""
    from django_ai_core.contrib.index.embedding_cache import CachedEmbeddingTransformer

    with patch(TASK):
        page = _post("Pothos care", BLOCKS, slug="pothos-race")
    original = CachedEmbeddingTransformer.embed_documents

    def unpublish_then_embed(self, documents, batch_size=100):
        from apps.blog.models import BlogPostPage

        BlogPostPage.objects.filter(pk=page.pk).update(live=False)
        return original(self, documents, batch_size=batch_size)

    with patch.object(LLMService, "embedding", _fake_embedding), patch.object(
        CachedEmbeddingTransformer,
        "embed_documents",
        autospec=True,
        side_effect=unpublish_then_embed,
    ):
        sync_blog_page_chunks(page.pk)

    assert _page_keys(page.pk) == set()


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
def test_page_published_enqueues_the_sync_when_the_feature_is_on(
    django_capture_on_commit_callbacks,
):
    with patch(TASK) as mock_task, django_capture_on_commit_callbacks(execute=True):
        page = _post("Pothos care", BLOCKS, slug="pothos-publish")
    mock_task.delay.assert_called_once_with(page.pk)


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_enqueue_is_deferred_to_commit(django_capture_on_commit_callbacks):
    """Wagtail's admin publish and Django's Model.delete() cascade both run
    inside transaction.atomic() — a task enqueued straight from the receiver can
    run on the worker BEFORE the commit and see the pre-publish page (a first
    publish would then purge-only and never index) or re-embed a page mid-delete
    (orphan rows). Deferred with transaction.on_commit, like notifications.py."""
    with patch(TASK) as mock_task:  # stays patched while the callback runs
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            page = _post("Pothos care", BLOCKS, slug="pothos-deferred")
            mock_task.delay.assert_not_called()  # nothing enqueued before commit
        # Run every captured callback, not just the first: other receivers
        # (blog cache invalidation, todo 442) also defer to commit.
        for callback in callbacks:
            callback()
        mock_task.delay.assert_called_once_with(page.pk)


@override_settings(FORUM_RAG_ENABLED=False, FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_page_published_does_not_enqueue_when_the_feature_is_off(
    django_capture_on_commit_callbacks,
):
    with patch(TASK) as mock_task, django_capture_on_commit_callbacks(execute=True):
        _post("Pothos care", BLOCKS, slug="pothos-off")
    mock_task.delay.assert_not_called()


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_page_unpublished_and_deleted_enqueue_the_sync(
    django_capture_on_commit_callbacks,
):
    with patch(TASK), django_capture_on_commit_callbacks(execute=True):
        page = _post("Pothos care", BLOCKS, slug="pothos-unpublish")
    with patch(TASK) as mock_task, django_capture_on_commit_callbacks(execute=True):
        page.unpublish()
    mock_task.delay.assert_called_once_with(page.pk)

    pk = page.pk
    with patch(TASK) as mock_task, django_capture_on_commit_callbacks(execute=True):
        page.delete()
    mock_task.delay.assert_called_once_with(pk)


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_non_blog_pages_are_ignored(django_capture_on_commit_callbacks):
    """page_published fires for EVERY Wagtail page type."""
    index = BlogIndexPage(title="Another index", slug="another-index")
    Page.objects.get(id=1).add_child(instance=index)
    with patch(TASK) as mock_task, django_capture_on_commit_callbacks(execute=True):
        index.save_revision().publish()
    mock_task.delay.assert_not_called()


@override_settings(**ENABLED)
@pytest.mark.django_db
def test_broker_failure_is_logged_not_raised(django_capture_on_commit_callbacks):
    """A publish must never fail because the broker is down (the blog signals'
    own <5ms / try-except posture) — and since the enqueue runs in an on_commit
    callback, an exception there would surface AFTER the commit, from the view.
    Asserted on the module logger: the project's JSON logging does not
    propagate to caplog."""
    with patch(TASK) as mock_task, patch(
        "apps.forum_host.signals.logger"
    ) as mock_logger, django_capture_on_commit_callbacks(execute=True):
        mock_task.delay.side_effect = RuntimeError("broker down")
        page = _post("Pothos care", BLOCKS, slug="pothos-broker")
    assert page.live is True
    mock_logger.exception.assert_called_once()
    assert "[CELERY]" in mock_logger.exception.call_args.args[0]


# --------------------------------------------------------------------------- #
# Permanent provider errors are not retried (todo 732, audit 2026-11-21 L12)   #
# --------------------------------------------------------------------------- #

_FAKE_REJECTED_KEY = "sk-fake-rejected-0000"  # pragma: allowlist secret


def _openai_status_error(name, status):
    """An OpenAI SDK status error as the client raises it: built from a real
    httpx response, with the provider's message quoting the key."""
    import httpx
    import openai

    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(status, request=request)
    message = f"Incorrect API key provided: {_FAKE_REJECTED_KEY}"
    return getattr(openai, name)(message, response=response, body=None)


def _openai_connection_error(name):
    import httpx
    import openai

    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    return getattr(openai, name)(request=request)


def _any_llm_error(name):
    from any_llm import exceptions

    return getattr(exceptions, name)(f"refused: {_FAKE_REJECTED_KEY}")


def _any_llm_missing_key():
    from any_llm import exceptions

    return exceptions.MissingApiKeyError("openai", "OPENAI_API_KEY")


PERMANENT = {
    "openai-401": lambda: _openai_status_error("AuthenticationError", 401),
    "openai-403": lambda: _openai_status_error("PermissionDeniedError", 403),
    "openai-400": lambda: _openai_status_error("BadRequestError", 400),
    "any-llm-auth": lambda: _any_llm_error("AuthenticationError"),
    "any-llm-missing-key": _any_llm_missing_key,
    "any-llm-invalid-request": lambda: _any_llm_error("InvalidRequestError"),
}
TRANSIENT = {
    "openai-429": lambda: _openai_status_error("RateLimitError", 429),
    "openai-500": lambda: _openai_status_error("InternalServerError", 500),
    "openai-timeout": lambda: _openai_connection_error("APITimeoutError"),
    "openai-connection": lambda: _openai_connection_error("APIConnectionError"),
    "any-llm-rate-limit": lambda: _any_llm_error("RateLimitError"),
    "any-llm-provider": lambda: _any_llm_error("ProviderError"),
}


def _run_with_embed_error(slug, error):
    """Run the task once with the embed raising ``error``; returns
    (page, the retry mock, the logger mock, what the run raised or None)."""
    from celery.exceptions import Retry
    from django_ai_core.contrib.index.embedding_cache import CachedEmbeddingTransformer

    with patch(TASK):
        page = _post("Pothos care", BLOCKS, slug=slug)
    _seed(vi.BlogChunks, f"blog.BlogPostPage:{page.pk}:0", "old but valid chunk")
    raised = None
    with patch.object(
        CachedEmbeddingTransformer, "embed_documents", side_effect=error
    ), patch("apps.forum_host.tasks.logger") as mock_logger, patch.object(
        sync_blog_page_chunks, "retry", side_effect=Retry("retried")
    ) as mock_retry:
        try:
            sync_blog_page_chunks.run(page.pk)
        except Exception as exc:  # the test asserts on what it was
            raised = exc
    return page, mock_retry, mock_logger, raised


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
@pytest.mark.parametrize("case", sorted(PERMANENT))
def test_a_permanent_provider_error_is_not_retried_and_is_logged_once(case):
    error = PERMANENT[case]()

    page, mock_retry, mock_logger, raised = _run_with_embed_error(
        f"pothos-permanent-{case}", error
    )

    # Not retried, and not raised either: Celery's own failure trace would
    # be a second log line for the same error.
    assert raised is None
    mock_retry.assert_not_called()
    # Logged once, at ERROR, with the page id and the error's class.
    mock_logger.error.assert_called_once()
    mock_logger.exception.assert_not_called()
    template, *args = mock_logger.error.call_args.args
    assert template.startswith("[ERROR]")
    assert args == [page.pk, type(error).__name__]
    # Never the provider's message: it can quote the key it rejected.
    assert _FAKE_REJECTED_KEY not in (template % tuple(args))
    # The page's existing chunks are kept: stale content beats none.
    assert _page_keys(page.pk) == {f"blog.BlogPostPage:{page.pk}:0"}


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
@pytest.mark.parametrize("case", sorted(TRANSIENT))
def test_a_transient_provider_error_is_still_retried(case):
    from celery.exceptions import Retry

    error = TRANSIENT[case]()

    page, mock_retry, mock_logger, raised = _run_with_embed_error(
        f"pothos-transient-{case}", error
    )

    assert isinstance(raised, Retry)
    mock_retry.assert_called_once()
    assert mock_retry.call_args.kwargs["exc"] is error
    mock_logger.error.assert_not_called()
    assert _page_keys(page.pk) == {f"blog.BlogPostPage:{page.pk}:0"}


@override_settings(**ENABLED, OPENAI_API_KEY=_FAKE_OPENAI_KEY)
@pytest.mark.django_db
def test_a_soft_time_limit_during_the_embed_is_still_retried():
    """Audit L12 declined this half on purpose: a soft-limit timeout on one
    page's embed is usually provider slowness, and retrying it is right."""
    from celery.exceptions import Retry, SoftTimeLimitExceeded

    error = SoftTimeLimitExceeded()

    page, mock_retry, mock_logger, raised = _run_with_embed_error(
        "pothos-soft-limit", error
    )

    assert isinstance(raised, Retry)
    mock_retry.assert_called_once()
    assert mock_retry.call_args.kwargs["exc"] is error
    mock_logger.error.assert_not_called()


def test_the_permanent_list_never_covers_a_transient_provider_error():
    """Each class is named on its own: ``openai.APIStatusError`` (or any
    other shared base) would also swallow 429 and 5xx."""
    from apps.forum_host.tasks import _permanent_embedding_errors
    from celery.exceptions import SoftTimeLimitExceeded

    permanent = _permanent_embedding_errors()

    assert len(permanent) == 11
    for make in TRANSIENT.values():
        assert not isinstance(make(), permanent)
    assert not isinstance(SoftTimeLimitExceeded(), permanent)
    assert not isinstance(RuntimeError("down"), permanent)
    for make in PERMANENT.values():
        assert isinstance(make(), permanent)
