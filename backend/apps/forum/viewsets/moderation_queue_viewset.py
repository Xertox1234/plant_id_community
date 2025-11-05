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

from ..models import FlaggedContent, ModerationAction, Post, Thread
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
