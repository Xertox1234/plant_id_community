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


class PostCursorPagination(ForumCursorPagination):
    # Posts read oldest-first (Post.Meta.ordering = ["created_at"]); id is the
    # unique tiebreak that keeps the cursor deterministic when created_at ties.
    ordering = ("created_at", "id")
