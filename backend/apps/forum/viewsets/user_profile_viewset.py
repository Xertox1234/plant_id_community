"""
User profile viewset for forum API.

Provides read-only access to forum user statistics and trust levels.
"""

import logging
from typing import Dict, Any
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny
from django.db.models import QuerySet

from ..models import UserProfile
from ..serializers import UserProfileSerializer

logger = logging.getLogger(__name__)


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for forum user profiles (read-only).

    Provides:
    - List: All user profiles (leaderboard)
    - Retrieve: Single user profile by user ID
    - top_contributors (custom): Top users by post count
    - most_helpful (custom): Top users by helpful count
    - veterans (custom): Users with veteran or expert trust level

    Query Parameters:
        - trust_level (str): Filter by trust level (new, basic, trusted, veteran, expert)
        - ordering (str): Sort order (e.g., -helpful_count, -post_count)

    Note:
        Read-only viewset (no create/update/delete).
        Profiles are created automatically via Django signals when users are created.
    """

    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [AllowAny]  # Public leaderboard data
    lookup_field = 'user_id'  # Lookup by user ID instead of profile ID
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['post_count', 'thread_count', 'helpful_count', 'created_at']
    ordering = ['-helpful_count', '-post_count']  # Default: most helpful, then most posts

    def get_queryset(self) -> QuerySet[UserProfile]:
        """
        Get user profiles queryset with filtering.

        Returns:
            QuerySet with user profiles, optimized with select_related
        """
        qs = super().get_queryset()

        # Always select related user for performance
        qs = qs.select_related('user')

        # Filter by trust level
        trust_level = self.request.query_params.get('trust_level')
        if trust_level:
            qs = qs.filter(trust_level=trust_level)

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

    @action(detail=False, methods=['GET'])
    def top_contributors(self, request: Request) -> Response:
        """
        Get top contributors by post count.

        GET /api/v1/forum/profiles/top_contributors/?limit=10

        Query Parameters:
            - limit (int): Number of profiles to return (default: 10, max: 100)

        Returns:
            List of user profiles ordered by post count
        """
        limit = int(request.query_params.get('limit', 10))
        limit = min(limit, 100)  # Cap at 100

        top_profiles = self.get_queryset().order_by('-post_count', '-helpful_count')[:limit]
        serializer = UserProfileSerializer(top_profiles, many=True, context=self.get_serializer_context())

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'])
    def most_helpful(self, request: Request) -> Response:
        """
        Get most helpful users by helpful reaction count.

        GET /api/v1/forum/profiles/most_helpful/?limit=10

        Query Parameters:
            - limit (int): Number of profiles to return (default: 10, max: 100)

        Returns:
            List of user profiles ordered by helpful count
        """
        limit = int(request.query_params.get('limit', 10))
        limit = min(limit, 100)  # Cap at 100

        helpful_profiles = self.get_queryset().order_by('-helpful_count', '-post_count')[:limit]
        serializer = UserProfileSerializer(helpful_profiles, many=True, context=self.get_serializer_context())

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'])
    def veterans(self, request: Request) -> Response:
        """
        Get veteran and expert users.

        GET /api/v1/forum/profiles/veterans/

        Returns:
            List of user profiles with veteran or expert trust level
        """
        veteran_profiles = self.get_queryset().filter(
            trust_level__in=['veteran', 'expert']
        ).order_by('-helpful_count', '-post_count')

        page = self.paginate_queryset(veteran_profiles)

        if page is not None:
            serializer = UserProfileSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = UserProfileSerializer(veteran_profiles, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def new_members(self, request: Request) -> Response:
        """
        Get recently joined members.

        GET /api/v1/forum/profiles/new_members/?limit=10

        Query Parameters:
            - limit (int): Number of profiles to return (default: 10, max: 100)

        Returns:
            List of user profiles ordered by creation date (newest first)
        """
        limit = int(request.query_params.get('limit', 10))
        limit = min(limit, 100)  # Cap at 100

        new_profiles = self.get_queryset().order_by('-created_at')[:limit]
        serializer = UserProfileSerializer(new_profiles, many=True, context=self.get_serializer_context())

        return Response(serializer.data, status=status.HTTP_200_OK)
