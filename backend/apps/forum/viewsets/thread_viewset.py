"""
Thread viewset for forum API.

Provides CRUD operations for forum threads with optimized prefetching.
"""

import logging
from typing import Dict, Any, Type, List
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission
from rest_framework.serializers import Serializer
from django.db.models import QuerySet, Prefetch, Q
from django.utils import timezone

from ..models import Thread, Post
from ..serializers import (
    ThreadListSerializer,
    ThreadDetailSerializer,
    ThreadCreateSerializer,
)
from ..permissions import IsAuthorOrReadOnly, IsModerator, CanCreateThread, IsAuthorOrModerator

logger = logging.getLogger(__name__)


class ThreadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for forum threads.

    Provides:
    - List: All active threads with lightweight serialization
    - Retrieve: Single thread with first post content
    - Create: New thread with first post (atomic transaction)
    - Update/Delete: Thread management (permissions TBD in Phase 2c)

    Query Parameters:
        - category (slug): Filter by category slug
        - author (username): Filter by author username
        - is_pinned (bool): Filter pinned threads
        - is_locked (bool): Filter locked threads
        - search (str): Search in thread title
        - ordering (str): Sort order (e.g., -created_at, -last_activity_at)

    Performance:
        - List: select_related('author', 'category') - minimal prefetch
        - Retrieve: + prefetch first post for detail view
        - Pagination enabled (default 20 per page)
    """

    queryset = Thread.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'excerpt']
    ordering_fields = ['created_at', 'last_activity_at', 'view_count', 'post_count']
    ordering = ['-is_pinned', '-last_activity_at']  # Pinned first, then recent activity

    def get_queryset(self) -> QuerySet[Thread]:
        """
        Get threads queryset with conditional prefetching.

        Performance optimization:
        - List view: select_related('author', 'category') only
        - Detail view: + prefetch first post

        Returns:
            QuerySet with active threads, optimized per action
        """
        qs = super().get_queryset()

        # Filter active threads only
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            qs = qs.filter(is_active=True)

        # Always select related author and category (needed for both list and detail)
        qs = qs.select_related('author', 'category')

        # Conditional prefetch for detail view
        if self.action == 'retrieve':
            # Prefetch first post for detail serializer
            first_post_prefetch = Prefetch(
                'posts',
                queryset=Post.objects.filter(
                    is_first_post=True,
                    is_active=True
                ).select_related('author', 'edited_by')
            )
            qs = qs.prefetch_related(first_post_prefetch)

        # Filter by category slug
        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        # Filter by author username
        author_username = self.request.query_params.get('author')
        if author_username:
            qs = qs.filter(author__username=author_username)

        # Filter by pinned status
        is_pinned = self.request.query_params.get('is_pinned')
        if is_pinned is not None:
            qs = qs.filter(is_pinned=is_pinned.lower() == 'true')

        # Filter by locked status
        is_locked = self.request.query_params.get('is_locked')
        if is_locked is not None:
            qs = qs.filter(is_locked=is_locked.lower() == 'true')

        return qs

    def get_serializer_class(self) -> Type[Serializer]:
        """
        Use different serializers for different actions.

        Returns:
            - ThreadListSerializer for list view (lightweight)
            - ThreadCreateSerializer for create action (with first_post_content)
            - ThreadDetailSerializer for retrieve/update/partial_update (full data)
        """
        if self.action == 'list':
            return ThreadListSerializer
        elif self.action == 'create':
            return ThreadCreateSerializer
        return ThreadDetailSerializer

    def get_permissions(self) -> List[BasePermission]:
        """
        Dynamic permissions based on action.

        Returns:
            - CanCreateThread for create (requires trust level)
            - IsAuthorOrReadOnly | IsModerator for update/delete
            - IsAuthenticatedOrReadOnly for list/retrieve
        """
        if self.action == 'create':
            # Creating threads requires minimum trust level
            return [CanCreateThread()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Editing requires being author OR moderator
            # Use combined permission class for proper OR logic
            return [IsAuthorOrModerator()]
        return [IsAuthenticatedOrReadOnly()]

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add request to serializer context for absolute URLs.

        Returns:
            Dict with request object
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer) -> None:
        """
        Create thread with author set from request user.

        Note:
            ThreadCreateSerializer handles atomic creation of thread + first post.
            Author is set in serializer's create() method.
        """
        serializer.save()
        logger.info(f"[FORUM] Thread created: {serializer.instance.slug} by {self.request.user.username}")

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """
        Retrieve thread detail and increment view count.

        Returns:
            Thread detail with first post content
        """
        instance = self.get_object()

        # Increment view count
        instance.view_count += 1
        instance.save(update_fields=['view_count'])

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def pinned(self, request: Request) -> Response:
        """
        Get all pinned threads.

        GET /api/v1/forum/threads/pinned/

        Returns:
            List of pinned threads ordered by last_activity_at
        """
        pinned_threads = self.get_queryset().filter(is_pinned=True).order_by('-last_activity_at')
        page = self.paginate_queryset(pinned_threads)

        if page is not None:
            serializer = ThreadListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = ThreadListSerializer(pinned_threads, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def recent(self, request: Request) -> Response:
        """
        Get recently active threads.

        GET /api/v1/forum/threads/recent/?days=7

        Query Parameters:
            - days (int): Number of days to look back (default: 7)

        Returns:
            List of threads with recent activity
        """
        days = int(request.query_params.get('days', 7))
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        recent_threads = self.get_queryset().filter(
            last_activity_at__gte=cutoff_date
        ).order_by('-last_activity_at')

        page = self.paginate_queryset(recent_threads)

        if page is not None:
            serializer = ThreadListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = ThreadListSerializer(recent_threads, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def search(self, request: Request) -> Response:
        """
        Full-text search across threads and posts.

        GET /api/v1/forum/threads/search/?q=watering&category=plant-care&author=john&page=1

        Query Parameters:
            - q (str): Search query (required)
            - category (str): Filter by category slug
            - author (str): Filter by author username
            - page (int): Page number (default: 1)
            - page_size (int): Results per page (default: 20)

        Returns:
            {
                "query": "watering",
                "threads": [...],
                "posts": [...],
                "thread_count": 5,
                "post_count": 12,
                "has_next_threads": true,
                "has_next_posts": false,
                "page": 1
            }
        """
        from ..serializers import PostSerializer

        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {
                    "error": "Search query parameter 'q' is required",
                    "query": "",
                    "threads": [],
                    "posts": [],
                    "thread_count": 0,
                    "post_count": 0,
                    "has_next_threads": False,
                    "has_next_posts": False,
                    "page": 1
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get filter parameters
        category_slug = request.query_params.get('category', '').strip()
        author_username = request.query_params.get('author', '').strip()
        page_num = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))

        # Search threads
        thread_qs = Thread.objects.filter(
            is_active=True
        ).select_related('author', 'category')

        # Apply search to thread title and excerpt
        thread_qs = thread_qs.filter(
            Q(title__icontains=query) | Q(excerpt__icontains=query)
        )

        # Apply filters
        if category_slug:
            thread_qs = thread_qs.filter(category__slug=category_slug)
        if author_username:
            thread_qs = thread_qs.filter(author__username__icontains=author_username)

        # Order by relevance (pinned first, then recent activity)
        thread_qs = thread_qs.order_by('-is_pinned', '-last_activity_at')

        # Search posts
        post_qs = Post.objects.filter(
            is_active=True
        ).select_related('author', 'thread', 'thread__category')

        # Apply search to post content (raw content only, not HTML)
        post_qs = post_qs.filter(
            Q(content_raw__icontains=query)
        )

        # Apply filters
        if category_slug:
            post_qs = post_qs.filter(thread__category__slug=category_slug)
        if author_username:
            post_qs = post_qs.filter(author__username__icontains=author_username)

        # Order by recent activity
        post_qs = post_qs.order_by('-created_at')

        # Get total counts
        thread_count = thread_qs.count()
        post_count = post_qs.count()

        # Paginate results
        start = (page_num - 1) * page_size
        end = start + page_size

        threads = thread_qs[start:end]
        posts = post_qs[start:end]

        # Check if there are more results
        has_next_threads = thread_count > end
        has_next_posts = post_count > end

        # Serialize results
        thread_serializer = ThreadListSerializer(
            threads,
            many=True,
            context=self.get_serializer_context()
        )
        post_serializer = PostSerializer(
            posts,
            many=True,
            context={'request': request}
        )

        return Response({
            "query": query,
            "threads": thread_serializer.data,
            "posts": post_serializer.data,
            "thread_count": thread_count,
            "post_count": post_count,
            "has_next_threads": has_next_threads,
            "has_next_posts": has_next_posts,
            "page": page_num
        })
