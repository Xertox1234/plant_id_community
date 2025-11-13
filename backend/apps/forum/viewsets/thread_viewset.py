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
from django.db.models import QuerySet, Prefetch, Q, F
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

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Create new thread with trust level rate limiting and spam detection.

        Phase 4.3: Trust Level Integration
        Checks daily thread creation limit based on user's trust level.

        Phase 4.4: Spam Detection
        Runs spam detection on thread title and first post content.

        Returns:
            201 Created: Thread created successfully
            400 Bad Request: Spam detected (auto-flagged for moderation)
            429 Too Many Requests: Daily thread limit exceeded for trust level
                Headers:
                    Retry-After: Seconds until limit resets (midnight UTC)
                    X-RateLimit-Limit: Maximum requests allowed
                    X-RateLimit-Remaining: Requests remaining (0 when hit)
                    X-RateLimit-Reset: Seconds until reset
        """
        from ..services.trust_level_service import TrustLevelService
        from ..services.spam_detection_service import SpamDetectionService
        from django.utils import timezone
        from datetime import timedelta

        # Check daily thread creation limit based on trust level
        if not TrustLevelService.check_daily_limit(request.user, 'threads'):
            trust_info = TrustLevelService.get_trust_level_info(request.user)
            limit = trust_info['limits']['threads_per_day']

            # Calculate seconds until midnight (when limit resets)
            now = timezone.now()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            retry_after_seconds = int((midnight - now).total_seconds())

            # Log rate limit hit for monitoring
            logger.warning(
                f"[RATE_LIMIT] User {request.user.username} (trust={trust_info['current_level']}) "
                f"exceeded thread limit: {limit}/day"
            )

            response = Response(
                {
                    "error": "Daily thread limit exceeded",
                    "detail": f"Your trust level ({trust_info['current_level']}) allows {limit} threads per day",
                    "trust_level": trust_info['current_level'],
                    "daily_limit": limit
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

            # Add RFC 6585 standard headers
            response['Retry-After'] = str(retry_after_seconds)
            response['X-RateLimit-Limit'] = str(limit)
            response['X-RateLimit-Remaining'] = '0'
            response['X-RateLimit-Reset'] = str(retry_after_seconds)

            return response

        # Phase 4.4: Run spam detection on thread content (title + first post)
        title = request.data.get('title', '')
        first_post_content = request.data.get('first_post_content', '')
        combined_content = f"{title}\n{first_post_content}"

        spam_result = SpamDetectionService.is_spam(request.user, combined_content, content_type='thread')

        if spam_result['is_spam']:
            # Log spam detection for monitoring
            logger.warning(
                f"[SPAM] Thread blocked for {request.user.username}: "
                f"score={spam_result['spam_score']}, reasons={spam_result['reasons']}"
            )

            # Build error response
            from django.conf import settings
            from ..constants import SPAM_SCORE_THRESHOLD

            error_response = {
                "error": "Content flagged as spam",
                "detail": f"Your thread was flagged by our spam detection system. Reasons: {', '.join(spam_result['reasons'])}",
                "spam_score": spam_result['spam_score'],
                "reasons": spam_result['reasons']
            }

            # Add detailed breakdown in DEBUG mode for troubleshooting
            if settings.DEBUG:
                error_response['debug'] = {
                    'threshold': SPAM_SCORE_THRESHOLD,
                    'score_breakdown': spam_result['details'],
                    'help': 'This debug information is only shown in DEBUG mode'
                }

            # Return 400 with spam details
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

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

        Security (Issue #154 - Race Condition Fix):
            Uses atomic database update to prevent lost view count increments
            when multiple users view the same thread simultaneously.
        """
        instance = self.get_object()

        # Atomic view count increment (Issue #154 fix)
        # Use F() expression with update() to prevent race conditions
        # This ensures thread-safe increment without SELECT-then-UPDATE pattern
        Thread.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)

        # Refresh instance to get updated view_count for serializer
        instance.refresh_from_db()

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
        Search forum threads and posts using PostgreSQL full-text search.

        GET /api/v1/forum/threads/search/?q=watering&category=plant-care

        Query Parameters:
            - q (required): Search query string
            - category (optional): Filter by category slug
            - author (optional): Filter by author username
            - date_from (optional): Filter posts after this date (ISO format)
            - date_to (optional): Filter posts before this date (ISO format)
            - page (optional): Page number for pagination
            - page_size (optional): Results per page (default: 20, max: 50)

        Returns:
            {
                "query": "watering",
                "threads": [...],
                "posts": [...],
                "total_threads": 15,
                "total_posts": 42,
                "page": 1,
                "page_size": 20,
                "has_next_threads": true,
                "has_next_posts": false
            }

        Performance:
            - Uses PostgreSQL SearchVector + SearchQuery + SearchRank
            - GIN indexes on thread.title, thread.excerpt, post.content_raw
            - Target response time: <200ms
        """
        from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
        from django.db.models import Q, F
        from datetime import datetime
        from ..serializers.post_serializer import PostSerializer

        # Validate query parameter
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {
                    'error': 'Search query required',
                    'detail': 'Please provide a search query using the "q" parameter'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get filter parameters
        category_slug = request.query_params.get('category')
        author_username = request.query_params.get('author')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        page_num = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 50)

        # Search threads
        thread_search_vector = SearchVector('title', weight='A') + SearchVector('excerpt', weight='B')
        thread_search_query = SearchQuery(query)

        thread_qs = Thread.objects.filter(is_active=True)

        # Apply filters to threads
        if category_slug:
            thread_qs = thread_qs.filter(category__slug=category_slug)
        if author_username:
            thread_qs = thread_qs.filter(author__username=author_username)
        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                thread_qs = thread_qs.filter(created_at__gte=date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                thread_qs = thread_qs.filter(created_at__lte=date_to_obj)
            except ValueError:
                pass

        # Apply search with ranking
        thread_results = thread_qs.annotate(
            search=thread_search_vector,
            rank=SearchRank(thread_search_vector, thread_search_query)
        ).filter(
            search=thread_search_query
        ).select_related(
            'author', 'category'
        ).order_by('-rank', '-last_activity_at')

        total_threads = thread_results.count()

        # Search posts
        post_search_vector = SearchVector('content_raw', weight='A')
        post_search_query = SearchQuery(query)

        post_qs = Post.objects.filter(is_active=True)

        # Apply filters to posts
        if category_slug:
            post_qs = post_qs.filter(thread__category__slug=category_slug)
        if author_username:
            post_qs = post_qs.filter(author__username=author_username)
        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                post_qs = post_qs.filter(created_at__gte=date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                post_qs = post_qs.filter(created_at__lte=date_to_obj)
            except ValueError:
                pass

        # Apply search with ranking
        post_results = post_qs.annotate(
            search=post_search_vector,
            rank=SearchRank(post_search_vector, post_search_query)
        ).filter(
            search=post_search_query
        ).select_related(
            'author', 'thread', 'thread__category', 'edited_by'
        ).prefetch_related(
            'reactions', 'attachments'
        ).order_by('-rank', '-created_at')

        total_posts = post_results.count()

        # Paginate combined results
        # For simplicity, we'll return top threads and top posts separately
        # Pagination applies to both independently
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size

        thread_page = thread_results[start_idx:end_idx]
        post_page = post_results[start_idx:end_idx]

        # Serialize results
        thread_serializer = ThreadListSerializer(
            thread_page,
            many=True,
            context=self.get_serializer_context()
        )
        post_serializer = PostSerializer(
            post_page,
            many=True,
            context=self.get_serializer_context()
        )

        # Calculate if there are more results
        has_next_threads = total_threads > end_idx
        has_next_posts = total_posts > end_idx

        logger.info(
            f"[FORUM] Search query='{query}' found {total_threads} threads, "
            f"{total_posts} posts (page {page_num})"
        )

        return Response({
            'query': query,
            'threads': thread_serializer.data,
            'posts': post_serializer.data,
            'total_threads': total_threads,
            'total_posts': total_posts,
            'page': page_num,
            'page_size': page_size,
            'has_next_threads': has_next_threads,
            'has_next_posts': has_next_posts,
            'filters': {
                'category': category_slug,
                'author': author_username,
                'date_from': date_from,
                'date_to': date_to,
            }
        })

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticatedOrReadOnly], url_path='flag')
    def flag_thread(self, request: Request, pk=None) -> Response:
        """
        Flag a thread for moderation review.

        POST /api/v1/forum/threads/{thread_id}/flag/

        Phase 4.2: Content Moderation Queue

        Request body:
        {
            "flag_reason": "spam|offensive|off_topic|misinformation|duplicate|low_quality|other",
            "explanation": "Optional detailed explanation (required if reason is 'other')"
        }

        Permissions:
            - Authenticated users only
            - Rate limit: 10 flags per day per user

        Returns:
            201 Created: Flag submitted successfully
            400 Bad Request: Invalid flag data or already flagged
            429 Too Many Requests: Rate limit exceeded
        """
        from ..models import FlaggedContent
        from ..serializers import FlagSubmissionSerializer
        from ..constants import MAX_FLAGS_PER_USER_PER_DAY, FLAGGABLE_CONTENT_TYPE_THREAD
        from django.utils import timezone
        from datetime import timedelta

        thread = self.get_object()

        # Check if user already flagged this thread
        existing_flag = FlaggedContent.objects.filter(
            thread=thread,
            reporter=request.user,
            status='pending'
        ).first()

        if existing_flag:
            return Response(
                {
                    "error": "Already flagged",
                    "detail": "You have already flagged this thread"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check daily flag limit
        today_start = timezone.now() - timedelta(days=1)
        flags_today = FlaggedContent.objects.filter(
            reporter=request.user,
            created_at__gte=today_start
        ).count()

        if flags_today >= MAX_FLAGS_PER_USER_PER_DAY:
            return Response(
                {
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {MAX_FLAGS_PER_USER_PER_DAY} flags per day"
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Validate request data
        serializer = FlagSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Create flag
        flag = FlaggedContent.objects.create(
            content_type=FLAGGABLE_CONTENT_TYPE_THREAD,
            thread=thread,
            reporter=request.user,
            flag_reason=serializer.validated_data['flag_reason'],
            explanation=serializer.validated_data.get('explanation', ''),
            status='pending'
        )

        logger.info(
            f"[MODERATION] Thread {thread.id} flagged by {request.user.username} "
            f"(reason: {flag.flag_reason})"
        )

        return Response(
            {
                "success": True,
                "flag_id": str(flag.id),
                "message": "Thread flagged for moderation review"
            },
            status=status.HTTP_201_CREATED
        )
