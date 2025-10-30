"""
User profile serializer for forum API.

Provides user forum statistics and trust level information.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Dict, Any

from ..models import UserProfile

User = get_user_model()


class ProfileUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer for profile's user field."""

    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'avatar_url']

    def get_display_name(self, obj: User) -> str:
        """Get display name (first_name last_name or username)."""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        elif obj.first_name:
            return obj.first_name
        return obj.username

    def get_avatar_url(self, obj: User) -> str:
        """Get avatar URL if available."""
        if hasattr(obj, 'avatar') and obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for forum user profiles.

    Includes nested user data, trust level information, and forum statistics.
    """

    user_info = ProfileUserSerializer(source='user', read_only=True)
    trust_level_display = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'user',  # UUID only
            'user_info',  # Nested user data
            'trust_level',
            'trust_level_display',  # Human-readable (e.g., "Trusted Member")
            'post_count',
            'thread_count',
            'helpful_count',
            'last_seen_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'post_count',  # System-managed (cached)
            'thread_count',  # System-managed (cached)
            'helpful_count',  # System-managed (cached)
            'created_at',
            'updated_at',
        ]

    def get_trust_level_display(self, obj: UserProfile) -> str:
        """
        Get human-readable trust level display.

        Returns:
            Human-readable trust level (e.g., "Trusted Member" instead of "trusted")

        Uses Django's get_FOO_display() pattern for choice fields.
        """
        return obj.get_trust_level_display()


class UserProfileStatsSerializer(serializers.Serializer):
    """
    Simplified serializer for user profile statistics.

    Use this for embedded stats in other serializers (e.g., post author info)
    when full profile data is not needed.
    """

    trust_level = serializers.CharField()
    trust_level_display = serializers.CharField()
    post_count = serializers.IntegerField()
    thread_count = serializers.IntegerField()
    helpful_count = serializers.IntegerField()

    @staticmethod
    def from_profile(profile: UserProfile) -> Dict[str, Any]:
        """
        Extract stats data from UserProfile instance.

        Args:
            profile: UserProfile instance

        Returns:
            Dict with stats fields ready for serialization

        Example:
            >>> profile = UserProfile.objects.get(user=request.user)
            >>> stats_data = UserProfileStatsSerializer.from_profile(profile)
            >>> serializer = UserProfileStatsSerializer(data=stats_data)
        """
        return {
            'trust_level': profile.trust_level,
            'trust_level_display': profile.get_trust_level_display(),
            'post_count': profile.post_count,
            'thread_count': profile.thread_count,
            'helpful_count': profile.helpful_count,
        }
