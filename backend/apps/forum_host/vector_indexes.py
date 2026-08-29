"""Semantic "similar topics" vector index for the forum (todo 255 slice 4 / H15).

Host-side (not the wagtail_forum package) so it may reach the forum models and
the visibility predicate. Registers a django-ai-core ``VectorIndex`` over live,
publicly-visible forum topics, backed by pgvector storage + OpenAI embeddings.

Import-safety contract (this module is imported at ``AppConfig.ready()``):
- NOTHING at module/class-definition scope may need ``OPENAI_API_KEY`` or hit the
  DB. ``LLMService.create`` raises ``MissingApiKeyError`` with an empty key, so
  the embedding transformer AND the source queryset are built lazily in
  ``SimilarTopics.__init__`` (instance attrs, read by the base ``__init__``).
- ``storage_provider = PgVectorProvider()`` is safe at class-def (no key/DB).

The feature gates on ``settings.FORUM_VECTOR_SEARCH_ENABLED`` (default False):
``find_similar_topics`` short-circuits to ``[]`` when off, so no embedding API
call ever fires in dev/CI. Populate the index with
``python manage.py rebuild_indexes SimilarTopics``.

See docs/superpowers/specs/2026-07-22-forum-similar-topics-pgvector-design.md.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django_ai_core.contrib.index import (
    CoreEmbeddingTransformer,
    ModelSource,
    VectorIndex,
    registry,
)
from django_ai_core.contrib.index.embedding_cache import CachedEmbeddingTransformer
from django_ai_core.contrib.index.storage.pgvector.provider import PgVectorProvider
from django_ai_core.llm import LLMService
from wagtail_forum.api.views import (
    _exclude_blocked_authors,
    _visible_boards,
    plain_text_excerpt,
)
from wagtail_forum.models import Topic

from . import constants

logger = logging.getLogger(__name__)


def _build_embedding_transformer():
    """Build the OpenAI-backed, content-hash-caching embedding transformer.

    Reads ``OPENAI_API_KEY`` — call only at index instantiation (never import),
    and only when the feature is enabled. The cache wrapper means a rebuild
    re-embeds only changed topics.
    """
    llm = LLMService.create(
        provider="openai",
        model=settings.FORUM_EMBED_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    return CachedEmbeddingTransformer(CoreEmbeddingTransformer(llm))


class TopicSource(ModelSource):
    """Vectorize a topic's title + opening-post plaintext.

    Overrides ``get_content`` because ``Post.body`` is a Wagtail StreamField —
    the default ``str()`` extraction would embed block-HTML junk. ``plain_text_excerpt``
    pulls clean text via ``raw_data`` (no per-post image bulk-fetch).
    """

    def get_content(self, obj) -> str:
        parts = [obj.title]
        opening = obj.posts.filter(live=True, is_opening_post=True).first()
        if opening is not None:
            parts.append(
                plain_text_excerpt(opening.body, constants.SIMILAR_CONTENT_MAX_CHARS)
            )
        return "\n".join(p for p in parts if p)


@registry.register()
class SimilarTopics(VectorIndex):
    storage_provider = PgVectorProvider()
    sources = []  # set lazily in __init__ (see module docstring)
    embedding_transformer = None  # set lazily in __init__

    def __init__(self):
        # Both deferred to instantiation, never class-def/import:
        #  - source queryset filtered through _visible_boards() so restricted-
        #    board content is NEVER embedded (defense in depth).
        #  - transformer built here so LLMService's empty-key error can't fire
        #    at import (dev/CI have no key).
        self.sources = [
            TopicSource(
                queryset=Topic.objects.filter(live=True, board__in=_visible_boards())
            )
        ]
        self.embedding_transformer = _build_embedding_transformer()
        super().__init__()


def _search_cache_key(query: str, limit: int) -> str:
    """Cache key for one vector query. Hashed, so an arbitrary user query can never
    produce an oversized or control-character-bearing memcached key.

    Keyed on exactly what reaches the vector store: the query text and ``limit``
    (which sizes the overfetch slice). ``board_slug`` is deliberately NOT part of
    the key — it never reaches ``search_documents``, it only filters the
    visibility refetch afterwards, so the cached pk list is identical across board
    slugs. Including it would fragment the cache and make a board-scoped search
    re-embed a query the unscoped one already paid for, defeating the purpose of
    caching here.
    """
    raw = f"{query}\x1f{limit}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{constants.SIMILAR_CACHE_PREFIX}:pks:{digest}"


def find_similar_topics(
    query: str, board_slug: str | None = None, limit: int | None = None, user=None
):
    """Return live, visible topics semantically similar to ``query``.

    Returns ``[]`` when the feature is disabled, the query is blank, the
    dedicated embedding budget is exhausted, the index is empty, or the provider
    errors — never raises to the caller. Results are refetched through
    ``_visible_boards()`` (board privacy) in vector-score order.

    This is the ONLY embedding entry point for the forum: the compose-time
    similar-topics endpoint, the premium semantic-search section (M12) and any
    future RAG retrieval (M13) all route through here, so every caller inherits
    the flag, the query length cap, the embedding budget, the embedding cache and
    the visibility refetch by construction. Callers must not reach
    ``SimilarTopics().search_documents()`` directly, and must not re-implement the
    length cap — it lives here precisely so a new caller cannot forget it and
    silently invalidate ``EMBED_BUDGET_LIMIT``'s cost math.

    ``user`` (todo 284/M9): when given, blocked-author topics are excluded in
    the same refetch that already re-runs per-request for board privacy — so
    this is safe cache-wise too, since only the pk list (query+limit-keyed,
    author-independent) is cached; the block filter is applied fresh every
    call, never baked into a shared cache entry. **Pass this only from a
    caller whose OWN response is never cross-user cached** — semantic_search.py
    qualifies (always ``private, no-store`` for the authenticated premium
    caller). ``similar.py``'s ``SimilarTopicsView`` deliberately does NOT pass
    it: that endpoint is ``AllowAny`` and caches its serialized `results` by
    (query, board_slug) alone with no user in the key — filtering there would
    leak one user's blocklist into another user's cached response.
    """
    if not getattr(settings, "FORUM_VECTOR_SEARCH_ENABLED", False):
        return []
    query = (query or "").strip()
    if not query:
        return []
    # Bound the embedded text here, not at each call site: embedding cost scales
    # with input length and EMBED_BUDGET_LIMIT is sized against this cap.
    query = query[: constants.SIMILAR_QUERY_MAX_CHARS]
    limit = limit or constants.SIMILAR_TOPICS_LIMIT

    # Deliberately imported at call time, not module scope — see this module's
    # import-safety contract.
    from apps.blog.services.ai_rate_limiter import AIRateLimiter

    # Embedding-result cache. Keyed on exactly what reaches the vector store (see
    # _search_cache_key — NOT board_slug), storing ordered PKs only: the visibility
    # refetch below always re-runs, so a board restricted after the cache write
    # still cannot leak, and a board-scoped call reuses the unscoped call's
    # embedding instead of paying for it twice. This is what makes
    # EMBED_BUDGET_LIMIT's "the result cache bounds normal traffic" sizing true for
    # EVERY caller, not just the compose-time endpoint that has its own outer
    # response cache: a premium client paging `/search/?semantic=1` re-issues the
    # identical query per page and must not re-embed it each time.
    cache_key = _search_cache_key(query, limit)
    ordered_pks = cache.get(cache_key)

    if ordered_pks is None:
        # Dedicated query-embedding budget (todo 275 / AC4). Peek, never
        # check-and-increment: budget is consumed only after a call that actually
        # reached the provider, so a sustained provider outage cannot drain the
        # cap via failed attempts.
        if not AIRateLimiter.peek_budget(
            constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT
        ):
            logger.warning(
                "[PERF] Forum semantic search skipped: query-embedding budget "
                "exhausted; degrading to no semantic results"
            )
            return []

        try:
            docs = list(
                SimilarTopics().search_documents(query)[
                    : limit * constants.SIMILAR_OVERFETCH
                ]
            )
        except Exception:
            logger.exception("[ERROR] similar-topics vector search failed")
            return []

        # Charged only on a call that returned — including an empty result set,
        # which still embedded the query. A CachedEmbeddingTransformer hit may not
        # have hit the provider; charging it anyway over-counts spend, which is
        # the safe direction for a cost cap.
        AIRateLimiter.consume_budget(
            constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT
        )

        # pks in vector-score order (search_documents returns ordered by distance).
        ordered_pks = []
        for doc in docs:
            pk = (doc.metadata or {}).get("pk")
            if pk is not None and pk not in ordered_pks:
                ordered_pks.append(pk)
        try:
            # An empty list is cached too — a query with no semantic match is the
            # cheapest thing to re-answer and the most wasteful to re-embed.
            cache.set(cache_key, ordered_pks, constants.SIMILAR_CACHE_TTL_SECONDS)
        except Exception:
            logger.warning("[ERROR] similar-topics pk-cache write failed")

    if not ordered_pks:
        return []

    # Refetch through the visibility predicate — the index may contain a topic
    # whose board was restricted AFTER indexing; never leak it.
    qs = Topic.objects.filter(
        pk__in=ordered_pks, live=True, board__in=_visible_boards()
    ).select_related("board")
    qs = _exclude_blocked_authors(qs, user)
    if board_slug:
        # Resolve the slug to visible board ids (Wagtail slugs are unique only
        # among siblings, so two boards can share one) and filter on board_id —
        # mirrors SearchView, avoiding a cross-board over-match.
        board_ids = list(
            _visible_boards().filter(slug=board_slug).values_list("id", flat=True)
        )
        qs = qs.filter(board_id__in=board_ids)
    by_pk = {t.pk: t for t in qs}
    ranked = [by_pk[pk] for pk in ordered_pks if pk in by_pk]
    return ranked[:limit]
