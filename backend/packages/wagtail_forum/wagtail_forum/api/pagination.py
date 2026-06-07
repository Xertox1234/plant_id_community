from rest_framework.pagination import CursorPagination


class ForumCursorPagination(CursorPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
    ordering = "-id"  # stable, unique cursor ordering


class TopicCursorPagination(ForumCursorPagination):
    # Activity-first; -id is the unique tiebreak that keeps the cursor
    # deterministic when last_post_at ties. The list filters live=True, and live
    # topics always have a non-null last_post_at, so the cursor never orders on NULL.
    ordering = ("-last_post_at", "-id")
