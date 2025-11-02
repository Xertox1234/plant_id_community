"""
Custom pagination classes for forum endpoints.

Uses constants from forum.constants for consistency across the forum app.
"""

from rest_framework.pagination import PageNumberPagination
from .constants import (
    DEFAULT_THREADS_PER_PAGE,
    DEFAULT_POSTS_PER_PAGE,
    MAX_THREADS_PER_PAGE,
    MAX_POSTS_PER_PAGE,
)


class ForumPagination(PageNumberPagination):
    """
    Standard pagination for forum endpoints (threads, categories).

    Configuration:
    - Default page size: 25 threads/categories
    - Client can request custom page size via ?page_size=X
    - Maximum page size: 100 (prevents excessive load)

    Usage:
        Apply to ThreadViewSet and CategoryViewSet:
        >>> class ThreadViewSet(viewsets.ModelViewSet):
        >>>     pagination_class = ForumPagination

    Query Parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 25, max: 100)

    Example Requests:
        - /api/v1/forum/threads/ - First 25 threads
        - /api/v1/forum/threads/?page=2 - Next 25 threads
        - /api/v1/forum/threads/?page_size=50 - 50 threads per page
        - /api/v1/forum/threads/?page=3&page_size=10 - Page 3 with 10 per page

    Response Format:
        {
            "count": 150,
            "next": "http://api.example.com/api/v1/forum/threads/?page=2",
            "previous": null,
            "results": [...]
        }
    """
    page_size = DEFAULT_THREADS_PER_PAGE  # 25 threads/categories per page
    page_size_query_param = 'page_size'  # Allow client to override
    max_page_size = MAX_THREADS_PER_PAGE  # Maximum 100 to prevent abuse


class PostPagination(PageNumberPagination):
    """
    Pagination for forum posts.

    Configuration:
    - Default page size: 20 posts (smaller than threads for better UX)
    - Client can request custom page size via ?page_size=X
    - Maximum page size: 50 (posts have more content than threads)

    Usage:
        Apply to PostViewSet:
        >>> class PostViewSet(viewsets.ModelViewSet):
        >>>     pagination_class = PostPagination

    Query Parameters:
        - page: Page number (default: 1)
        - page_size: Posts per page (default: 20, max: 50)

    Example Requests:
        - /api/v1/forum/posts/?thread=my-thread-slug - First 20 posts
        - /api/v1/forum/posts/?thread=my-thread-slug&page=2 - Next 20 posts
        - /api/v1/forum/posts/?thread=my-thread-slug&page_size=10 - 10 posts per page

    Response Format:
        {
            "count": 47,
            "next": "http://api.example.com/api/v1/forum/posts/?thread=slug&page=2",
            "previous": null,
            "results": [...]
        }

    Notes:
        - Posts require thread parameter in request
        - Smaller page size improves initial load time
        - Lower max prevents memory issues with large rich content
    """
    page_size = DEFAULT_POSTS_PER_PAGE  # 20 posts per page
    page_size_query_param = 'page_size'  # Allow client to override
    max_page_size = MAX_POSTS_PER_PAGE  # Maximum 50 for performance
