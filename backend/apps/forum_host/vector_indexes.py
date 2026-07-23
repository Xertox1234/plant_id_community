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

import logging

from django.conf import settings
from django_ai_core.contrib.index import (
    CoreEmbeddingTransformer,
    ModelSource,
    VectorIndex,
    registry,
)
from django_ai_core.contrib.index.embedding_cache import CachedEmbeddingTransformer
from django_ai_core.contrib.index.storage.pgvector.provider import PgVectorProvider
from django_ai_core.llm import LLMService
from wagtail_forum.api.views import _visible_boards, plain_text_excerpt
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


def find_similar_topics(
    query: str, board_slug: str | None = None, limit: int | None = None
):
    """Return live, visible topics semantically similar to ``query``.

    Returns ``[]`` when the feature is disabled, the query is blank, the index is
    empty, or the provider errors — never raises to the caller. Results are
    refetched through ``_visible_boards()`` (board privacy) in vector-score order.
    """
    if not getattr(settings, "FORUM_VECTOR_SEARCH_ENABLED", False):
        return []
    query = (query or "").strip()
    if not query:
        return []
    limit = limit or constants.SIMILAR_TOPICS_LIMIT

    try:
        docs = list(
            SimilarTopics().search_documents(query)[
                : limit * constants.SIMILAR_OVERFETCH
            ]
        )
    except Exception:
        logger.exception("[ERROR] similar-topics vector search failed")
        return []

    # pks in vector-score order (search_documents returns ordered by distance).
    ordered_pks: list = []
    for doc in docs:
        pk = (doc.metadata or {}).get("pk")
        if pk is not None and pk not in ordered_pks:
            ordered_pks.append(pk)
    if not ordered_pks:
        return []

    # Refetch through the visibility predicate — the index may contain a topic
    # whose board was restricted AFTER indexing; never leak it.
    qs = Topic.objects.filter(
        pk__in=ordered_pks, live=True, board__in=_visible_boards()
    ).select_related("board")
    if board_slug:
        qs = qs.filter(board__slug=board_slug)
    by_pk = {t.pk: t for t in qs}
    ranked = [by_pk[pk] for pk in ordered_pks if pk in by_pk]
    return ranked[:limit]
