"""Compose-time semantic "similar topics" endpoint (todo 255 slice 4 / H15).

GET /api/v1/forum/topics/similar/?q=<text>&board=<slug> — public read (the audit
called this dedupe-for-community-health, not premium-gated), per-IP throttled
like search. Returns 503 while FORUM_VECTOR_SEARCH_ENABLED is off so no embedding
spend happens over an empty forum.

See docs/superpowers/specs/2026-07-22-forum-similar-topics-pgvector-design.md.
"""

import hashlib
import logging

from apps.core.ratelimit import client_ip_key
from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import constants
from .api import _throttled
from .vector_indexes import find_similar_topics

logger = logging.getLogger(__name__)


def _cache_key(query: str, board_slug: str | None) -> str:
    raw = f"{query}\x1f{board_slug or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{constants.SIMILAR_CACHE_PREFIX}:{digest}"


def _serialize(topic) -> dict:
    return {
        "id": topic.id,
        "slug": topic.slug,
        "title": topic.title,
        "board_slug": topic.board.slug,
        "reply_count": topic.reply_count,
    }


@_throttled("similar_topics", "GET", key=client_ip_key)
class SimilarTopicsView(APIView):
    """Semantic similar-topics search over live, visible forum topics."""

    permission_classes = [AllowAny]
    versioning_class = None  # opt out of NamespaceVersioning, like package views

    @extend_schema(
        responses={200: dict, 400: dict, 503: dict},
        description=(
            "Compose-time semantic 'similar topics'. Query params: q (required), "
            "board (optional board-slug filter). 503 when the feature is "
            "disabled; 400 for a blank q; 200 {results: [...]} otherwise."
        ),
    )
    def get(self, request):
        if not settings.FORUM_VECTOR_SEARCH_ENABLED:
            return Response(
                {"detail": "Similar-topics search is not enabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {"detail": "Query parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        query = query[: constants.SIMILAR_QUERY_MAX_CHARS]
        board_slug = request.query_params.get("board", "").strip() or None

        # Cache the (query, board) result set briefly so debounced compose-time
        # typing doesn't re-embed the same near-identical query repeatedly.
        cache_key = _cache_key(query, board_slug)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({"results": cached})

        topics = find_similar_topics(query, board_slug=board_slug)
        results = [_serialize(t) for t in topics]
        try:
            cache.set(cache_key, results, constants.SIMILAR_CACHE_TTL_SECONDS)
        except Exception:
            logger.warning("[ERROR] similar-topics result-cache write failed")
        return Response({"results": results})
