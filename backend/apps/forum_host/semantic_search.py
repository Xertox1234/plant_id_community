"""Premium semantic section on the forum search endpoint (todo 275 / M12).

Host-side (not the ``wagtail_forum`` package) so it may reach the pgvector index
in ``vector_indexes.py`` and this host's premium entitlement; the package forbids
``apps.*`` imports (``test_reusability.py``).

Design notes a reviewer will want:

**Why a separate ``semantic`` array rather than interleaving into ``topics``.**
The audit (M12) says "blend semantic hits into the existing forum SearchView".
The response is offset-paged over relevance-ranked FTS hits (``?page=`` +
``*_has_more``, package ``SearchView``), and vector hits carry a distance score
that is not commensurable with the FTS rank. Merging the two lists would make
``offset``/``has_more`` describe a window that no longer exists — the client
would silently skip or repeat rows while paging. So the blend happens in the same
*response*, in its own key, leaving FTS paging arithmetic untouched.

**Why the entitlement check is inline rather than a ``permission_classes`` gate.**
Search itself is public (anonymous FTS must keep working); only the extra
semantic key is a premium perk. A permission class would 403 the whole endpoint.

**Cache-header safety.** The package ``SearchView`` mixes in
``PublicForumReadCacheMixin``, which marks *anonymous* successful GETs
``public, s-maxage=...`` for the CDN and everything else ``private, no-store``
(``_apply_forum_read_cache_headers``). The semantic key is only ever added for an
*authenticated* premium user, so a semantic-bearing response is always
``private, no-store`` and can never be stored by the shared cache or served to
another user. ``Vary`` already covers ``Cookie`` + ``Authorization``. Pinned by
``test_semantic_search.py::test_semantic_response_is_never_shared_cacheable``.
"""

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema

from .vector_indexes import find_similar_topics

logger = logging.getLogger(__name__)

# Query-param opt-in. Absent → the response shape is byte-identical to before,
# so no existing client or CDN entry is affected by this feature shipping.
SEMANTIC_PARAM = "semantic"

# ``semantic_status`` values. Deliberately does NOT distinguish "budget
# exhausted" from "ran and found nothing": an exhausted embedding budget is a
# silent quality degrade by design (see EMBED_BUDGET_LIMIT), and surfacing
# operational cost state to clients invites probing.
STATUS_OK = "ok"
STATUS_PREMIUM_REQUIRED = "premium_required"
STATUS_UNAVAILABLE = "unavailable"


def _wants_semantic(request) -> bool:
    """True when the client opted in via ``?semantic=1`` (or ``true``/``yes``)."""
    raw = request.query_params.get(SEMANTIC_PARAM, "").strip().lower()
    return raw in {"1", "true", "yes"}


def _is_premium(request) -> bool:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return False
    # has_premium_access() grants staff/superusers premium-equivalent access.
    return bool(user.has_premium_access())


def _serialize(topic) -> dict:
    """Serialize a semantic hit in the SAME shape as a ``topics`` search hit.

    Identical keys mean the web/mobile clients reuse their existing search-result
    renderer for this section instead of needing a second one. ``board`` is
    already ``select_related`` by ``find_similar_topics``, so this adds no
    queries.
    """
    return {
        "id": topic.id,
        "slug": topic.slug,
        "title": topic.title,
        "reply_count": topic.reply_count,
        "view_count": topic.view_count,
        "last_post_at": (
            topic.last_post_at.isoformat() if topic.last_post_at else None
        ),
        "is_pinned": topic.is_pinned,
        # Audit H6. Kept in lockstep with the FTS hit shape by
        # test_premium_semantic_hits_use_the_same_shape_as_fts_topic_hits —
        # that test is what caught this field being added to one builder and
        # not the other.
        "is_solved": topic.solved_post_id is not None,
        "board_id": topic.board_id,
        "board_slug": topic.board.slug,
    }


class SemanticSearchMixin:
    """Adds an opt-in, premium-gated ``semantic`` section to forum search.

    Mixed in ahead of the package ``SearchView`` so ``super().get()`` produces
    the untouched FTS payload, which this then augments in place.
    """

    @extend_schema(
        responses={200: dict},
        description=(
            "Search live topic titles and post bodies. Query params: q "
            "(required, truncated to SEARCH_MAX_QUERY_CHARS chars and "
            "SEARCH_MAX_TERMS whitespace-separated terms), board (optional "
            "board slug filter), page (optional, 1-based, capped at "
            "MAX_PAGE), semantic (optional; '1' opts into the premium "
            "semantic section). Each section returns up to PAGE_SIZE results "
            "plus a *_has_more flag — no silent cap on RESULTS; page through "
            "with ?page=. Offset-paged over relevance-ranked results, so a "
            "concurrent topic/post write can shift the window; clients "
            "should dedup by id when appending pages.\n\n"
            "With semantic=1 the response additionally carries 'semantic' (a "
            "list of topic hits in the same shape as 'topics', ordered by "
            "meaning similarity rather than keyword rank, un-paged and capped "
            "at SIMILAR_TOPICS_LIMIT) and 'semantic_status': 'ok', "
            "'premium_required' (non-premium caller) or 'unavailable' "
            "(semantic search disabled for this deployment). Without "
            "semantic=1 neither key is present."
        ),
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        if not _wants_semantic(request):
            return response
        # Only augment a successful, dict-shaped body (a throttled 429 or an
        # error response must pass through untouched).
        if response.status_code != 200 or not isinstance(response.data, dict):
            return response

        if not _is_premium(request):
            response.data["semantic"] = []
            response.data["semantic_status"] = STATUS_PREMIUM_REQUIRED
            return response

        if not getattr(settings, "FORUM_VECTOR_SEARCH_ENABLED", False):
            response.data["semantic"] = []
            response.data["semantic_status"] = STATUS_UNAVAILABLE
            return response

        query = request.query_params.get("q", "").strip()
        board_slug = request.query_params.get("board", "").strip() or None

        # find_similar_topics owns the feature flag, the query length cap (search's
        # own `q` is uncapped), the query-embedding budget, the result cache
        # and the board-visibility refetch, and is contractually non-raising — so
        # a vector/provider failure already degrades to an empty section while
        # FTS results still render. The belt-and-braces catch is here because
        # search is a core public endpoint and this section is an optional perk:
        # if that contract is ever broken upstream, keyword search must not start
        # 500ing for premium users only.
        try:
            topics = find_similar_topics(query, board_slug=board_slug)
            results = [_serialize(t) for t in topics]
        except Exception:
            logger.exception("[ERROR] semantic search section failed; degrading")
            results = []
        response.data["semantic"] = results
        response.data["semantic_status"] = STATUS_OK
        return response
