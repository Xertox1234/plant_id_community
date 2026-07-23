from rest_framework.pagination import CursorPagination


class ForumCursorPagination(CursorPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
    ordering = "-id"  # stable, unique cursor ordering


class TopicCursorPagination(ForumCursorPagination):
    # Pinned-first, then activity; -id is the unique tiebreak that keeps the
    # cursor deterministic when last_post_at ties. The list filters live=True,
    # and live topics always have a non-null last_post_at, so the cursor never
    # orders on NULL. DRF tracks the cursor position by the FIRST field, so
    # paging inside the (large) unpinned group falls back to DRF's
    # offset-from-position mechanism — fine at forum scale; revisit if a board
    # reaches tens of thousands of topics.
    ordering = ("-is_pinned", "-last_post_at", "-id")

    # Board-list sort options exposed to the web ThreadListPage <select>. Keys
    # are the exact values the select sends as ?sort=; each ordering keeps
    # -is_pinned first (pinned topics stay on top) and ends in a unique id
    # tiebreak so the cursor stays deterministic. "-post_count" is the UI label
    # for the model's reply_count field.
    # Scale note: only (board, -last_post_at) is indexed (Topic.Meta); the
    # created_at/view_count/reply_count sorts fall back to a sequential sort as a
    # board grows — the same accepted tradeoff as the default ordering's "revisit
    # if a board reaches tens of thousands of topics" note. Add composite indexes
    # then, not speculatively now.
    SORT_ORDERINGS = {
        "-last_activity_at": ("-is_pinned", "-last_post_at", "-id"),
        "-created_at": ("-is_pinned", "-created_at", "-id"),
        "created_at": ("-is_pinned", "created_at", "id"),
        "-view_count": ("-is_pinned", "-view_count", "-id"),
        "-post_count": ("-is_pinned", "-reply_count", "-id"),
    }

    def get_ordering(self, request, queryset, view):
        # An unknown or blank ?sort= falls back to the default ordering — a bad
        # value is ignored, never a 500. The chosen ordering is baked into the
        # cursor's base_url, so `next`/`previous` links preserve the sort.
        return self.SORT_ORDERINGS.get(
            request.query_params.get("sort", ""), self.ordering
        )


class PostCursorPagination(ForumCursorPagination):
    # Posts read oldest-first (Post.Meta.ordering = ["created_at"]); id is the
    # unique tiebreak that keeps the cursor deterministic when created_at ties.
    ordering = ("created_at", "id")
