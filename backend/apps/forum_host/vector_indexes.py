"""Forum vector indexes: "similar topics" (todo 255 slice 4 / H15) and the
chunked blog index for RAG plant-care answers (todo 289 / M13).

Host-side (not the wagtail_forum package) so it may reach the forum models and
the visibility predicate. Registers two django-ai-core ``VectorIndex``es —
``SimilarTopics`` over live, publicly-visible forum topics and ``BlogChunks``
over live, public blog articles — backed by pgvector storage + OpenAI
embeddings. Both share one embedding table (``PgVectorEmbedding``,
discriminated by ``index_name``; ``document_key`` is its primary key).

Import-safety contract (this module is imported at ``AppConfig.ready()``):
- NOTHING at module/class-definition scope may need ``OPENAI_API_KEY`` or hit the
  DB. ``LLMService.create`` raises ``MissingApiKeyError`` with an empty key, so
  the embedding transformer AND the source queryset are built lazily in each
  index's ``__init__`` (instance attrs, read by the base ``__init__``).
- ``storage_provider = PgVectorProvider()`` is safe at class-def (no key/DB).

The features gate on ``settings.FORUM_VECTOR_SEARCH_ENABLED`` (default False):
``_scored_search`` short-circuits when off, so no embedding API call ever fires
in dev/CI. Populate the indexes with
``python manage.py rebuild_indexes SimilarTopics BlogChunks`` (a bare
``rebuild_indexes`` builds both).

See docs/superpowers/specs/2026-07-22-forum-similar-topics-pgvector-design.md
and docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md.
"""

import hashlib
import logging

from apps.blog.models import BlogPostPage
from django.conf import settings
from django.core.cache import cache
from django.utils.text import slugify
from django_ai_core.contrib.index import (
    CoreEmbeddingTransformer,
    ModelSource,
    VectorIndex,
    registry,
)
from django_ai_core.contrib.index.embedding_cache import CachedEmbeddingTransformer
from django_ai_core.contrib.index.schema import Document
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding
from django_ai_core.contrib.index.storage.pgvector.provider import PgVectorProvider
from django_ai_core.llm import LLMService
from wagtail_forum.api.views import (
    _exclude_blocked_authors,
    _visible_boards,
    plain_text_excerpt,
)
from wagtail_forum.models import Topic

from . import constants
from .rag_chunking import chunk_blocks

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


class BlogChunkSource(ModelSource):
    """Vectorize a blog article as block-boundary chunks (todo 289 / M13).

    One ``Document`` per ``rag_chunking.BlogChunk`` with PER-CHUNK metadata
    (``block_index``, ``heading_path``, ``slug``, ``title``): the base class's
    ``get_metadata`` is called once per object and the same dict is reused for
    every chunk, so the anchor a citation needs can only come from overriding
    ``_object_to_documents``. Keys are ``blog.BlogPostPage:<pk>:<i>`` — the
    ``document_key`` column is the PRIMARY KEY of the table every index shares,
    so the ``source_id`` prefix is what keeps them from colliding with
    ``SimilarTopics``' ``wagtail_forum.Topic:<pk>:<i>`` rows.
    """

    def __init__(self, queryset):
        super().__init__(queryset=queryset)
        # The base __init__ only sets chunk_transformer when NONE is passed and
        # silently leaves the attribute unset otherwise (django-ai-core 0.1.5).
        # Unused here — chunking is rag_chunking.chunk_blocks — but pinned so a
        # future base-class change cannot resurrect blind character windows.
        self.chunk_transformer = None

    def _object_to_documents(self, obj):
        if not self.provides_object(obj):
            raise ValueError("Object does not belong to this source")
        base = self.get_metadata(obj)
        chunks = chunk_blocks(obj.content_blocks.raw_data, title=obj.title)
        for i, chunk in enumerate(chunks):
            yield Document(
                document_key=self.get_document_key(obj, i),
                content=chunk.text,
                metadata={
                    **base,
                    "block_index": chunk.block_index,
                    "heading_path": chunk.heading_path,
                    "slug": obj.slug,
                    "title": obj.title,
                },
            )


@registry.register()
class BlogChunks(VectorIndex):
    """Chunked index over live, public blog articles (todo 289 / M13).

    Same lazy-construction contract as ``SimilarTopics``. ``storage_provider``
    is its OWN ``PgVectorProvider`` instance: ``VectorIndex.__init__`` stamps
    ``index_name`` onto the provider instance, so sharing ``SimilarTopics``'
    would clobber one index's name with the other's.
    """

    storage_provider = PgVectorProvider()
    sources = []  # set lazily in __init__ (see module docstring)
    embedding_transformer = None  # set lazily in __init__

    def __init__(self):
        self.sources = [BlogChunkSource(BlogPostPage.objects.live().public())]
        self.embedding_transformer = _build_embedding_transformer()
        super().__init__()

    def build(self):
        """Rebuild from scratch: purge THIS index's rows, then re-add.

        ``PgVectorProvider.add()`` only upserts the keys it is handed, so
        without the purge a page that shrank from 9 chunks to 6 would keep
        serving ``:6``–``:8`` forever and an unpublished page would stay in the
        store until the visibility refetch dropped it on every query. Filtered
        on ``index_name`` — never ``storage_provider.clear()``, which deletes
        EVERY index's rows from the shared table. Not transactional on purpose:
        the rebuild embeds over the network and must not hold a DB transaction
        open across it; ``rebuild_indexes`` is an operator action (todo 330).
        """
        PgVectorEmbedding.objects.filter(
            index_name=self.storage_provider.index_name
        ).delete()
        return super().build()


def rag_enabled() -> bool:
    """The RAG plant-care feature's TWO-flag gate (todo 289 / M13).

    M13 is a strict superset of H15: with vector search off every question
    would silently come back "no information" forever, so ``FORUM_RAG_ENABLED``
    alone is not enough. Shared by the ask view (503 ``disabled`` when off),
    the blog page-lifecycle receivers (no index maintenance for a dark feature)
    and the sync task (purge only — deleting is free, embedding is not).
    """
    return bool(
        getattr(settings, "FORUM_RAG_ENABLED", False)
        and getattr(settings, "FORUM_VECTOR_SEARCH_ENABLED", False)
    )


def _index_name(index_cls: type[VectorIndex]) -> str:
    """The ``PgVectorEmbedding.index_name`` an index class stores under.

    Mirrors ``VectorIndex.__init__`` (``f"{slugify(class name)}_index"``) so
    purge/maintenance queries can target one index's rows WITHOUT
    instantiating it — instantiation builds the OpenAI transformer and needs a
    key.
    """
    return f"{slugify(index_cls.__name__)}_index"


def _scored_search(index_cls: type[VectorIndex], query: str, limit: int):
    """Embed ``query`` once and return up to ``limit`` scored documents.

    The ONLY place ``search_documents()`` is called in the forum. Every
    embedding caller routes through here — via ``find_similar_topics`` (topic
    pks + visibility refetch) or ``rag_retrieval.retrieve_grounding_passages``
    (similarity floor + per-corpus refetch) — so the flag, the query-length cap
    and the ``EMBED_BUDGET`` peek-then-consume hold for all of them by
    construction. Callers must not re-implement the cap: it is here precisely
    so a new caller cannot forget it and silently invalidate
    ``EMBED_BUDGET_LIMIT``'s cost math.

    TRI-STATE return, deliberately: ``None`` means no search happened (feature
    off, blank query, budget exhausted, provider error — nothing was charged);
    a ``list`` (possibly empty) means the search ran and one unit WAS charged.
    A wrapper that caches results must only cache the ``list`` case, or a
    budget outage would be remembered as "no results" for the cache TTL.

    Never raises. Results keep ``doc.score`` (``1 - cosine_distance`` from the
    pgvector provider) and ``doc.metadata``; the slice matters because an
    unsliced django-ai-core queryset silently caps at 20.
    """
    if not getattr(settings, "FORUM_VECTOR_SEARCH_ENABLED", False):
        return None
    query = (query or "").strip()
    if not query:
        return None
    # Bound the embedded text here, not at each call site: embedding cost scales
    # with input length and EMBED_BUDGET_LIMIT is sized against this cap.
    query = query[: constants.SIMILAR_QUERY_MAX_CHARS]
    # Log label only. getattr, not `.__name__`: tests patch the index class
    # with a MagicMock (to keep them key-free), which has no __name__.
    label = getattr(index_cls, "__name__", "vector index")

    # Deliberately imported at call time, not module scope — see this module's
    # import-safety contract.
    from apps.blog.services.ai_rate_limiter import AIRateLimiter

    # Dedicated query-embedding budget (todo 275 / AC4). Peek, never
    # check-and-increment: budget is consumed only after a call that actually
    # reached the provider, so a sustained provider outage cannot drain the cap
    # via failed attempts. Checked BEFORE the index is instantiated — its
    # __init__ builds the OpenAI-backed transformer.
    if not AIRateLimiter.peek_budget(
        constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT
    ):
        logger.warning(
            "[PERF] %s vector search skipped: query-embedding budget exhausted",
            label,
        )
        return None

    try:
        docs = list(index_cls().search_documents(query)[:limit])
    except Exception:
        logger.exception("[ERROR] %s vector search failed", label)
        return None

    # Charged only on a call that returned — including an empty result set,
    # which still embedded the query. A CachedEmbeddingTransformer hit may not
    # have hit the provider; charging it anyway over-counts spend, which is the
    # safe direction for a cost cap.
    AIRateLimiter.consume_budget(
        constants.EMBED_BUDGET_CACHE_KEY, constants.EMBED_BUDGET_LIMIT
    )
    return docs


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

    The TOPIC wrapper over ``_scored_search`` (the single embedding entry
    point): the compose-time similar-topics endpoint and the premium
    semantic-search section (M12) route through here and inherit the flag, the
    query length cap, the embedding budget and the embedding cache from the
    core, plus the pk cache and the visibility refetch from this function. RAG
    retrieval (M13) is the core's other wrapper — it needs the scores this one
    discards — see ``rag_retrieval.retrieve_grounding_passages``. Callers must
    not reach ``search_documents()`` directly.

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
        docs = _scored_search(SimilarTopics, query, limit * constants.SIMILAR_OVERFETCH)
        if docs is None:
            # No search ran (budget exhausted / provider error): degrade to no
            # semantic results and, crucially, cache NOTHING — see the core's
            # tri-state contract.
            return []

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
