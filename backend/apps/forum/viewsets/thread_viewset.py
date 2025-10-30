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
from ..permissions import IsAuthorOrReadOnly, IsModerator, CanCreateThread

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
            # Note: DRF evaluates permissions with OR logic when multiple are provided
            return [IsAuthorOrReadOnly(), IsModerator()]
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
