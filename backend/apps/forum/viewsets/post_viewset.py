"""
Post viewset for forum API.

Provides CRUD operations for forum posts with full reaction and attachment support.
"""

import logging
from typing import Dict, Any, Type
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.serializers import Serializer
from django.db.models import QuerySet

from ..models import Post
from ..serializers import (
    PostSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
)

logger = logging.getLogger(__name__)


class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for forum posts.

    Provides:
    - List: Posts in a thread (filter by thread slug required)
    - Retrieve: Single post detail with reactions and attachments
    - Create: New post in thread (PostCreateSerializer)
    - Update: Edit post (PostUpdateSerializer) - auto-marks as edited
    - Delete: Soft delete (sets is_active=False)

    Query Parameters:
        - thread (slug): Filter by thread slug (required for list)
        - author (username): Filter by author username
        - ordering (str): Sort order (e.g., created_at, -created_at)

    Performance:
        - select_related('author', 'thread', 'edited_by')
        - prefetch_related('reactions', 'attachments')
        - Pagination enabled (default 20 per page)
    """

    queryset = Post.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['created_at']  # Chronological order (oldest first)

    def get_queryset(self) -> QuerySet[Post]:
        """
        Get posts queryset with optimized prefetching.

        Performance optimization:
        - select_related('author', 'thread', 'edited_by')
        - prefetch_related('reactions', 'attachments')

        Returns:
            QuerySet with active posts, optimized for serialization
        """
        qs = super().get_queryset()

        # Filter active posts only
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            qs = qs.filter(is_active=True)

        # Always select related for performance
        qs = qs.select_related('author', 'thread', 'edited_by')

        # Prefetch reactions and attachments to avoid N+1
        qs = qs.prefetch_related('reactions', 'attachments')

        # Filter by thread slug (required for list view)
        thread_slug = self.request.query_params.get('thread')
        if thread_slug:
            qs = qs.filter(thread__slug=thread_slug)

        # Filter by author username
        author_username = self.request.query_params.get('author')
        if author_username:
            qs = qs.filter(author__username=author_username)

        return qs

    def get_serializer_class(self) -> Type[Serializer]:
        """
        Use different serializers for different actions.

        Returns:
            - PostCreateSerializer for create action
            - PostUpdateSerializer for update/partial_update actions
            - PostSerializer for list/retrieve (read-only with full nested data)
        """
        if self.action == 'create':
            return PostCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PostUpdateSerializer
        return PostSerializer

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add request to serializer context for absolute URLs.

        Returns:
            Dict with request object
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        List posts in a thread.

        Requires thread query parameter.

        Returns:
            List of posts in chronological order
        """
        thread_slug = request.query_params.get('thread')

        if not thread_slug:
            return Response(
                {
                    'error': 'thread parameter is required',
                    'detail': 'Please provide a thread slug to filter posts'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer) -> None:
        """
        Create post with author set from request user.

        Note:
            Author is set in serializer's create() method from request.user.
        """
        serializer.save()
        logger.info(f"[FORUM] Post created in thread {serializer.instance.thread.slug} by {self.request.user.username}")

    def perform_update(self, serializer) -> None:
        """
        Update post and mark as edited.

        Note:
            PostUpdateSerializer handles setting edited_at and edited_by automatically.
        """
        serializer.save()
        logger.info(f"[FORUM] Post {serializer.instance.id} edited by {self.request.user.username}")

    def perform_destroy(self, instance) -> None:
        """
        Soft delete post by setting is_active=False.

        Note:
            We don't actually delete posts to preserve thread integrity.
            Soft deletion allows restoration if needed.
        """
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        logger.info(f"[FORUM] Post {instance.id} soft deleted by {self.request.user.username}")

    @action(detail=False, methods=['GET'])
    def first_posts(self, request: Request) -> Response:
        """
        Get all first posts (thread starters) with optional filtering.

        GET /api/v1/forum/posts/first_posts/?category=plant-care

        Query Parameters:
            - category (slug): Filter by thread category
            - author (username): Filter by author

        Returns:
            List of first posts (thread starters)
        """
        first_posts = self.get_queryset().filter(is_first_post=True)

        # Additional filtering for first posts
        category_slug = request.query_params.get('category')
        if category_slug:
            first_posts = first_posts.filter(thread__category__slug=category_slug)

        page = self.paginate_queryset(first_posts)

        if page is not None:
            serializer = PostSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = PostSerializer(first_posts, many=True, context=self.get_serializer_context())
        return Response(serializer.data)
