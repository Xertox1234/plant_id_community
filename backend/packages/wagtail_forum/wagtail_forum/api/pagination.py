from rest_framework.pagination import CursorPagination


class ForumCursorPagination(CursorPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
    ordering = "-id"  # stable, unique cursor ordering
