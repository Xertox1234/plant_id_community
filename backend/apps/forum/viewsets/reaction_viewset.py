"""
Reaction viewset for forum API.

Provides reaction management with toggle pattern for easy add/remove.
"""

import logging
from typing import Dict, Any, List
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated, BasePermission
from django.db.models import QuerySet

from ..models import Reaction
from ..serializers import (
    ReactionSerializer,
    ReactionToggleSerializer,
    ReactionAggregateSerializer,
)

logger = logging.getLogger(__name__)


class ReactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for forum post reactions.

    Provides:
    - List: Reactions on a post (filter by post required)
    - Retrieve: Single reaction detail
    - Create: Add reaction (but prefer toggle action)
    - Delete: Remove reaction (but prefer toggle action)
    - toggle (custom): Toggle reaction on/off (recommended pattern)
    - aggregate (custom): Get reaction counts and user's active reactions

    Query Parameters:
        - post (uuid): Filter by post UUID (required for list)
        - reaction_type (str): Filter by type (like, love, helpful, thanks)
        - is_active (bool): Filter active reactions (default: true)

    Recommended Usage:
        Use POST /toggle/ endpoint for adding/removing reactions.
        This provides better UX (single endpoint, idempotent).
    """

    queryset = Reaction.objects.all()
    serializer_class = ReactionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self) -> QuerySet[Reaction]:
        """
        Get reactions queryset with filtering.

        Returns:
            QuerySet with reactions, filtered by query parameters
        """
        qs = super().get_queryset()

        # Always select related user for performance
        qs = qs.select_related('user')

        # Filter active reactions by default
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            qs = qs.filter(is_active=True)

        # Filter by post UUID (required for list view)
        post_id = self.request.query_params.get('post')
        if post_id:
            qs = qs.filter(post_id=post_id)

        # Filter by reaction type
        reaction_type = self.request.query_params.get('reaction_type')
        if reaction_type:
            qs = qs.filter(reaction_type=reaction_type)

        # Filter by user (for checking user's own reactions)
        user_id = self.request.query_params.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)

        return qs

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add request to serializer context.

        Returns:
            Dict with request object
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_permissions(self) -> List[BasePermission]:
        """
        Require authentication for create/update/delete and toggle.

        Returns:
            List of permission instances
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle']:
            return [IsAuthenticated()]
        return [IsAuthenticatedOrReadOnly()]

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        List reactions on a post.

        Requires post query parameter.

        Returns:
            List of reactions
        """
        post_id = request.query_params.get('post')

        if not post_id:
            return Response(
                {
                    'error': 'post parameter is required',
                    'detail': 'Please provide a post UUID to filter reactions'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated])
    def toggle(self, request: Request) -> Response:
        """
        Toggle reaction on a post (add if not exists, remove if exists).

        POST /api/v1/forum/reactions/toggle/

        Request body:
        {
            "post": "uuid",
            "reaction_type": "like"  # or love, helpful, thanks
        }

        Response:
        {
            "reaction": {
                "id": "uuid",
                "post": "uuid",
                "user": "uuid",
                "user_info": {...},
                "reaction_type": "like",
                "is_active": true,
                "created_at": "...",
                "updated_at": "..."
            },
            "created": false,  # true if newly created, false if toggled
            "is_active": true  # current active status after toggle
        }

        Returns:
            Reaction object with toggle status
        """
        serializer = ReactionToggleSerializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        # Log the toggle action
        action_str = "created" if result['created'] else "toggled"
        active_str = "active" if result['is_active'] else "inactive"
        logger.info(
            f"[FORUM] Reaction {action_str} by {request.user.username}: "
            f"{result['reaction'].reaction_type} on post {result['reaction'].post_id} "
            f"(now {active_str})"
        )

        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'])
    def aggregate(self, request: Request) -> Response:
        """
        Get aggregated reaction counts for a post.

        GET /api/v1/forum/reactions/aggregate/?post=uuid

        Query Parameters:
            - post (uuid): Post UUID (required)

        Response:
        {
            "counts": {
                "like": 5,
                "love": 2,
                "helpful": 10,
                "thanks": 3
            },
            "user_reactions": ["like", "helpful"]  # Types current user has active
        }

        Returns:
            Aggregated reaction counts and user's active reactions
        """
        post_id = request.query_params.get('post')

        if not post_id:
            return Response(
                {
                    'error': 'post parameter is required',
                    'detail': 'Please provide a post UUID'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get post object
        from ..models import Post
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {'error': 'Post not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get aggregated data
        user = request.user if request.user.is_authenticated else None
        aggregate_data = ReactionAggregateSerializer.get_aggregate_data(post, user)

        serializer = ReactionAggregateSerializer(data=aggregate_data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
