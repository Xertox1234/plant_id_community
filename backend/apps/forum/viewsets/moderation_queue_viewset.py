"""
Moderation Queue ViewSet for content moderation system.

Phase 4.2: Content Moderation Queue
Provides endpoints for moderators to review and act on flagged content.
"""

import logging
from typing import Any, Dict
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from django.db import transaction
from django.db.models import QuerySet, Count, Q
from django.utils import timezone

from ..models import FlaggedContent, ModerationAction, Post, Thread, UserProfile
from ..serializers import (
    FlaggedContentSerializer,
    ModerationActionSerializer,
    ModerationReviewSerializer,
)
from ..permissions import IsModeratorOrStaff
from ..constants import (
    MODERATION_STATUS_PENDING,
    MODERATION_STATUS_APPROVED,
    MODERATION_STATUS_REJECTED,
    MODERATION_STATUS_REMOVED,
    MODERATION_ACTION_APPROVE,
    MODERATION_ACTION_REJECT,
    MODERATION_ACTION_REMOVE_POST,
    MODERATION_ACTION_REMOVE_THREAD,
    MODERATION_ACTION_LOCK_THREAD,
    MODERATION_ACTION_WARNING,
    CACHE_KEY_MOD_DASHBOARD,
    CACHE_TIMEOUT_MOD_DASHBOARD,
)

logger = logging.getLogger(__name__)


class ModerationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for moderation queue management.

    Phase 4.2: Content Moderation Queue
    Provides endpoints for moderators to:
    - View pending flags
    - Review flagged content
    - Take moderation actions
    - View moderation history

    Permissions:
    - IsModeratorOrStaff: Only staff/moderators can access

    Endpoints:
    - GET /api/v1/forum/moderation-queue/ - List pending flags
    - GET /api/v1/forum/moderation-queue/{id}/ - Get flag details
    - POST /api/v1/forum/moderation-queue/{id}/review/ - Review flag
    - GET /api/v1/forum/moderation-queue/stats/ - Get moderation stats
    - GET /api/v1/forum/moderation-queue/history/ - Get moderation history
    """

    queryset = FlaggedContent.objects.all()
    serializer_class = FlaggedContentSerializer
    permission_classes = [IsModeratorOrStaff]
    lookup_field = 'id'

    def get_queryset(self) -> QuerySet[FlaggedContent]:
        """
        Get queryset with optimizations and filters.

        Filters:
        - status: Filter by moderation status (pending, approved, rejected, removed)
        - content_type: Filter by content type (post, thread)
        - reporter: Filter by reporter username
        - ordering: Sort by created_at (default: -created_at)
        """
        queryset = FlaggedContent.objects.select_related(
            'reporter',
            'reviewed_by',
            'post__author',
            'post__thread',
            'thread__author',
            'thread__category',
        ).prefetch_related(
            'actions__moderator',
        )

        # Filter by status (default to pending)
        status_filter = self.request.query_params.get('status', MODERATION_STATUS_PENDING)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type in ['post', 'thread']:
            queryset = queryset.filter(content_type=content_type)

        # Filter by reporter
        reporter_username = self.request.query_params.get('reporter')
        if reporter_username:
            queryset = queryset.filter(reporter__username=reporter_username)

        # Ordering (default: newest first)
        ordering = self.request.query_params.get('ordering', '-created_at')
        queryset = queryset.order_by(ordering)

        return queryset

    @action(detail=True, methods=['post'], url_path='review')
    def review_flag(self, request: Request, id: str = None) -> Response:
        """
        Review a flagged content item and take action.

        POST /api/v1/forum/moderation-queue/{id}/review/

        Request body:
        {
            "action_type": "approve|reject|remove_post|remove_thread|lock_thread|warning",
            "reason": "Detailed reason for this action",
            "moderator_notes": "Internal notes (optional)"
        }

        Actions:
        - approve: Mark flag as approved (no violation)
        - reject: Reject flag as invalid
        - remove_post: Remove the flagged post
        - remove_thread: Remove the flagged thread
        - lock_thread: Lock the thread (if flagged content is a thread)
        - warning: Issue warning to content author

        Returns:
        - 200: Action completed successfully
        - 400: Invalid action or missing fields
        - 404: Flag not found
        """
        flag = self.get_object()

        # Validate that flag is pending
        if flag.status != MODERATION_STATUS_PENDING:
            return Response(
                {'error': f'Flag has already been reviewed (status: {flag.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate request data
        serializer = ModerationReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action_type = serializer.validated_data['action_type']
        reason = serializer.validated_data['reason']
        moderator_notes = serializer.validated_data.get('moderator_notes', '')

        # Execute moderation action in transaction
        try:
            with transaction.atomic():
                result = self._execute_moderation_action(
                    flag=flag,
                    moderator=request.user,
                    action_type=action_type,
                    reason=reason,
                    moderator_notes=moderator_notes
                )

                logger.info(
                    f"[MODERATION] Action '{action_type}' taken by {request.user.username} "
                    f"on {flag.content_type} {flag.get_flagged_object().id} "
                    f"(flag: {flag.id})"
                )

                # Invalidate dashboard cache after moderation action (standardized key)
                from django.core.cache import cache
                cache.delete(CACHE_KEY_MOD_DASHBOARD)
                logger.debug("[MODERATION] Dashboard cache invalidated after action")

                return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"[MODERATION] Error executing action '{action_type}': {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': f'Failed to execute moderation action: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _execute_moderation_action(
        self,
        flag: FlaggedContent,
        moderator: Any,
        action_type: str,
        reason: str,
        moderator_notes: str
    ) -> Dict[str, Any]:
        """
        Execute moderation action and update flag status.

        Args:
            flag: FlaggedContent instance
            moderator: User performing the action
            action_type: Type of action to take
            reason: Reason for the action
            moderator_notes: Internal notes

        Returns:
            dict: Result of the action
        """
        flagged_obj = flag.get_flagged_object()
        affected_user = flagged_obj.author

        # Map action types to flag statuses
        action_to_status = {
            MODERATION_ACTION_APPROVE: MODERATION_STATUS_APPROVED,
            MODERATION_ACTION_REJECT: MODERATION_STATUS_REJECTED,
            MODERATION_ACTION_REMOVE_POST: MODERATION_STATUS_REMOVED,
            MODERATION_ACTION_REMOVE_THREAD: MODERATION_STATUS_REMOVED,
            MODERATION_ACTION_LOCK_THREAD: MODERATION_STATUS_APPROVED,
            MODERATION_ACTION_WARNING: MODERATION_STATUS_APPROVED,
        }

        # Execute action-specific logic
        if action_type == MODERATION_ACTION_REMOVE_POST:
            if flag.content_type != 'post':
                raise ValueError("Cannot remove post - flagged content is not a post")
            flag.post.is_active = False
            flag.post.save(update_fields=['is_active'])

        elif action_type == MODERATION_ACTION_REMOVE_THREAD:
            if flag.content_type != 'thread':
                raise ValueError("Cannot remove thread - flagged content is not a thread")
            flag.thread.is_active = False
            flag.thread.save(update_fields=['is_active'])

        elif action_type == MODERATION_ACTION_LOCK_THREAD:
            if flag.content_type == 'thread':
                flag.thread.is_locked = True
                flag.thread.save(update_fields=['is_locked'])
            elif flag.content_type == 'post':
                # Lock the thread that the post belongs to
                flag.post.thread.is_locked = True
                flag.post.thread.save(update_fields=['is_locked'])

        # Update flag status
        new_status = action_to_status.get(action_type, MODERATION_STATUS_APPROVED)
        flag.mark_reviewed(
            moderator=moderator,
            status=new_status,
            notes=moderator_notes
        )

        # Create moderation action record
        moderation_action = ModerationAction.objects.create(
            flag=flag,
            moderator=moderator,
            action_type=action_type,
            reason=reason,
            affected_user=affected_user
        )

        return {
            'success': True,
            'action': action_type,
            'flag_status': new_status,
            'moderation_action_id': str(moderation_action.id),
            'message': f'Moderation action "{action_type}" completed successfully'
        }

    @action(detail=False, methods=['get'], url_path='stats')
    def moderation_stats(self, request: Request) -> Response:
        """
        Get moderation queue statistics.

        GET /api/v1/forum/moderation-queue/stats/

        Returns:
        {
            "pending_count": 42,
            "pending_posts": 30,
            "pending_threads": 12,
            "reviewed_today": 15,
            "total_flags": 157,
            "flags_by_reason": {
                "spam": 25,
                "offensive": 10,
                "off_topic": 7
            }
        }
        """
        # Pending flags by content type
        pending_flags = FlaggedContent.objects.filter(status=MODERATION_STATUS_PENDING)
        pending_count = pending_flags.count()
        pending_posts = pending_flags.filter(content_type='post').count()
        pending_threads = pending_flags.filter(content_type='thread').count()

        # Reviewed today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        reviewed_today = FlaggedContent.objects.filter(
            reviewed_at__gte=today_start
        ).count()

        # Total flags
        total_flags = FlaggedContent.objects.count()

        # Flags by reason (pending only)
        flags_by_reason = dict(
            pending_flags.values_list('flag_reason').annotate(count=Count('id'))
        )

        return Response({
            'pending_count': pending_count,
            'pending_posts': pending_posts,
            'pending_threads': pending_threads,
            'reviewed_today': reviewed_today,
            'total_flags': total_flags,
            'flags_by_reason': flags_by_reason,
        })

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request: Request) -> Response:
        """
        Get comprehensive moderation dashboard overview.

        GET /api/v1/forum/moderation-queue/dashboard/

        Returns comprehensive dashboard data including:
        - Overview metrics (pending, flags today/week, approval rate, resolution time)
        - Flag breakdown by type
        - Recent flags preview
        - Moderator statistics

        Performance:
            Dashboard metrics cached for 5 minutes to reduce load
            during frequent moderator checks. Cache automatically
            invalidated on flag creation/review actions.

        Example response:
        {
            "overview": {
                "pending_flags": 12,
                "flags_today": 28,
                "flags_this_week": 156,
                "approval_rate": 0.68,
                "average_resolution_time_hours": 2.3
            },
            "flag_breakdown": {
                "spam": 8,
                "abuse": 2,
                "suspicious": 1,
                "duplicate": 1
            },
            "recent_flags": [...],
            "moderator_stats": {
                "total_moderators": 5,
                "active_moderators_today": 3,
                "avg_flags_resolved_per_moderator": 8.2
            }
        }
        """
        from django.contrib.auth import get_user_model
        from django.db.models import Avg, F
        from django.core.cache import cache
        from datetime import timedelta

        User = get_user_model()

        # Check cache first (standardized cache key format)
        cached_data = cache.get(CACHE_KEY_MOD_DASHBOARD)
        if cached_data:
            logger.debug("[MODERATION] Dashboard cache hit")
            return Response(cached_data)

        # Time boundaries
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Overview metrics
        pending_flags = FlaggedContent.objects.filter(status=MODERATION_STATUS_PENDING).count()
        flags_today = FlaggedContent.objects.filter(created_at__gte=today_start).count()
        flags_this_week = FlaggedContent.objects.filter(created_at__gte=week_start).count()

        # Approval rate (approved / total reviewed)
        reviewed_flags = FlaggedContent.objects.exclude(status=MODERATION_STATUS_PENDING)
        total_reviewed = reviewed_flags.count()
        approved_count = reviewed_flags.filter(status=MODERATION_STATUS_APPROVED).count()
        approval_rate = (approved_count / total_reviewed) if total_reviewed > 0 else 0.0

        # Average resolution time (hours between created_at and reviewed_at)
        avg_resolution = reviewed_flags.filter(
            reviewed_at__isnull=False
        ).annotate(
            resolution_time=F('reviewed_at') - F('created_at')
        ).aggregate(
            avg_seconds=Avg('resolution_time')
        )['avg_seconds']

        avg_resolution_hours = 0.0
        if avg_resolution:
            avg_resolution_hours = avg_resolution.total_seconds() / 3600

        # Flag breakdown by reason (pending only)
        pending_flags_qs = FlaggedContent.objects.filter(status=MODERATION_STATUS_PENDING)
        flag_breakdown = dict(
            pending_flags_qs.values_list('flag_reason').annotate(count=Count('id'))
        )

        # Recent flags preview (last 5 pending flags)
        recent_flags = FlaggedContent.objects.filter(
            status=MODERATION_STATUS_PENDING
        ).select_related(
            'reporter',
            'post__author',
            'thread__author'
        ).order_by('-created_at')[:5]

        recent_flags_data = []
        for flag in recent_flags:
            flagged_obj = flag.get_flagged_object()
            content_preview = ""
            if hasattr(flagged_obj, 'content_raw'):
                content_preview = flagged_obj.content_raw[:100]
            elif hasattr(flagged_obj, 'title'):
                content_preview = flagged_obj.title[:100]

            recent_flags_data.append({
                'id': str(flag.id),
                'flag_reason': flag.flag_reason,
                'content_type': flag.content_type,
                'content_preview': content_preview,
                'reporter': flag.reporter.username if flag.reporter else 'System',
                'created_at': flag.created_at.isoformat(),
            })

        # Moderator statistics
        # Count users who have reviewed flags (staff/expert users)
        from django.db.models import Exists, OuterRef

        # Create subquery to check if user has expert profile
        expert_profiles = UserProfile.objects.filter(
            user=OuterRef('pk'),
            trust_level='expert'
        )

        moderators = User.objects.filter(
            Q(is_staff=True) | Q(Exists(expert_profiles))
        ).distinct()
        total_moderators = moderators.count()

        # Active moderators today (reviewed at least one flag today)
        active_moderators_today = FlaggedContent.objects.filter(
            reviewed_at__gte=today_start,
            reviewed_by__isnull=False
        ).values('reviewed_by').distinct().count()

        # Average flags resolved per moderator (all time)
        flags_resolved_by_moderators = FlaggedContent.objects.filter(
            reviewed_by__isnull=False
        ).count()
        avg_flags_per_moderator = (
            flags_resolved_by_moderators / total_moderators
        ) if total_moderators > 0 else 0.0

        dashboard_data = {
            'overview': {
                'pending_flags': pending_flags,
                'flags_today': flags_today,
                'flags_this_week': flags_this_week,
                'approval_rate': round(approval_rate, 2),
                'average_resolution_time_hours': round(avg_resolution_hours, 1),
            },
            'flag_breakdown': flag_breakdown,
            'recent_flags': recent_flags_data,
            'moderator_stats': {
                'total_moderators': total_moderators,
                'active_moderators_today': active_moderators_today,
                'avg_flags_resolved_per_moderator': round(avg_flags_per_moderator, 1),
            },
        }

        # Cache for 5 minutes (standardized cache timeout)
        cache.set(CACHE_KEY_MOD_DASHBOARD, dashboard_data, CACHE_TIMEOUT_MOD_DASHBOARD)
        logger.debug("[MODERATION] Dashboard cache set (TTL: 5 minutes)")

        return Response(dashboard_data)

    @action(detail=False, methods=['get'], url_path='history')
    def moderation_history(self, request: Request) -> Response:
        """
        Get moderation action history.

        GET /api/v1/forum/moderation-queue/history/

        Query params:
        - moderator: Filter by moderator username
        - action_type: Filter by action type
        - limit: Number of actions to return (default: 50)

        Returns list of recent moderation actions.
        """
        actions = ModerationAction.objects.select_related(
            'moderator',
            'affected_user',
            'flag',
        ).order_by('-created_at')

        # Filter by moderator
        moderator_username = request.query_params.get('moderator')
        if moderator_username:
            actions = actions.filter(moderator__username=moderator_username)

        # Filter by action type
        action_type = request.query_params.get('action_type')
        if action_type:
            actions = actions.filter(action_type=action_type)

        # Limit results
        limit = int(request.query_params.get('limit', 50))
        actions = actions[:limit]

        serializer = ModerationActionSerializer(actions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='user-history/(?P<user_id>[^/.]+)')
    def user_moderation_history(self, request: Request, user_id=None) -> Response:
        """
        Get moderation history for a specific user.

        GET /api/v1/forum/moderation-queue/user-history/{user_id}/

        Query params:
        - limit: Max flags to return (default: 50, max: 200)
        - offset: Skip first N flags for pagination (default: 0)

        Returns all flags and actions related to a specific user (as the author of flagged content).
        Useful for moderators to see a user's full moderation history.

        Returns:
        {
            "user_id": 123,
            "username": "johndoe",
            "flags_received": [...],
            "actions_taken": [...],
            "summary": {
                "total_flags": 5,
                "pending_flags": 1,
                "approved_flags": 3,
                "removed_content_count": 1,
                "warnings_count": 2
            },
            "pagination": {
                "total": 5,
                "limit": 50,
                "offset": 0,
                "has_more": false
            }
        }
        """
        from django.contrib.auth import get_user_model
        from django.shortcuts import get_object_or_404

        User = get_user_model()

        # Get the user
        user = get_object_or_404(User, id=user_id)

        # Parse pagination params
        try:
            limit = min(int(request.query_params.get('limit', 50)), 200)
            offset = int(request.query_params.get('offset', 0))
        except ValueError:
            return Response(
                {'error': 'Invalid pagination parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get flags queryset
        flags_qs = FlaggedContent.objects.filter(
            Q(post__author=user) | Q(thread__author=user)
        ).select_related(
            'reporter',
            'reviewed_by',
            'post',
            'thread'
        ).order_by('-created_at')

        # Get total count and paginated flags
        total_flags_count = flags_qs.count()
        flags = flags_qs[offset:offset+limit]

        flags_data = []
        for flag in flags:
            flagged_obj = flag.get_flagged_object()
            content_preview = ""
            if hasattr(flagged_obj, 'content_raw'):
                content_preview = flagged_obj.content_raw[:100]
            elif hasattr(flagged_obj, 'title'):
                content_preview = flagged_obj.title[:100]

            flags_data.append({
                'id': str(flag.id),
                'flag_reason': flag.flag_reason,
                'status': flag.status,
                'created_at': flag.created_at.isoformat(),
                'reviewed_at': flag.reviewed_at.isoformat() if flag.reviewed_at else None,
                'content_type': flag.content_type,
                'content_preview': content_preview,
                'reporter': flag.reporter.username if flag.reporter else 'System',
                'reviewed_by': flag.reviewed_by.username if flag.reviewed_by else None,
            })

        # Get all moderation actions targeting this user
        actions = ModerationAction.objects.filter(
            affected_user=user
        ).select_related(
            'moderator',
            'flag'
        ).order_by('-created_at')

        actions_data = []
        for action in actions:
            actions_data.append({
                'id': str(action.id),
                'action_type': action.action_type,
                'reason': action.reason,
                'created_at': action.created_at.isoformat(),
                'moderator': action.moderator.username if action.moderator else 'System',
                'flag_id': str(action.flag.id) if action.flag else None,
            })

        # Summary statistics (use full queryset, not paginated)
        total_flags = flags_qs.count()
        pending_flags = flags_qs.filter(status=MODERATION_STATUS_PENDING).count()
        approved_flags = flags_qs.filter(status=MODERATION_STATUS_APPROVED).count()
        removed_content_count = flags_qs.filter(status=MODERATION_STATUS_REMOVED).count()
        warnings_count = actions.filter(action_type='warning').count()

        return Response({
            'user_id': user.id,
            'username': user.username,
            'flags_received': flags_data,
            'actions_taken': actions_data,
            'summary': {
                'total_flags': total_flags,
                'pending_flags': pending_flags,
                'approved_flags': approved_flags,
                'removed_content_count': removed_content_count,
                'warnings_count': warnings_count,
            },
            'pagination': {
                'total': total_flags_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_flags_count
            }
        })
