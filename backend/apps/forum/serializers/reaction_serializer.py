"""
Reaction serializer for forum API.

Handles reaction toggle logic and aggregation.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Dict, Any

from ..models import Reaction

User = get_user_model()


class ReactionUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer for reaction authors."""

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'display_name']

    def get_display_name(self, obj: User) -> str:
        """Get display name (first_name last_name or username)."""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        elif obj.first_name:
            return obj.first_name
        return obj.username


class ReactionSerializer(serializers.ModelSerializer):
    """
    Serializer for forum post reactions.

    Includes user info and active status (for toggle pattern).
    """

    user_info = ReactionUserSerializer(source='user', read_only=True)

    class Meta:
        model = Reaction
        fields = [
            'id',
            'post',
            'user',  # UUID only
            'user_info',  # Nested user data
            'reaction_type',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]


class ReactionToggleSerializer(serializers.Serializer):
    """
    Serializer for toggling reactions (custom action).

    Input:
        - post: UUID of post to react to
        - reaction_type: one of (like, love, helpful, thanks)

    Output:
        - reaction: Full reaction data
        - created: Whether reaction was newly created (vs toggled)
        - is_active: Current active status after toggle
    """

    # Input fields
    post = serializers.UUIDField(write_only=True)
    reaction_type = serializers.ChoiceField(
        choices=['like', 'love', 'helpful', 'thanks'],
        write_only=True
    )

    # Output fields
    reaction = ReactionSerializer(read_only=True)
    created = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Toggle reaction using model's toggle_reaction class method.

        Returns:
            Dict with reaction, created, and is_active status
        """
        post_id = validated_data['post']
        reaction_type = validated_data['reaction_type']
        user_id = self.context['request'].user.id

        # Use model's toggle method
        reaction, created = Reaction.toggle_reaction(
            post_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type
        )

        # Serialize the reaction instance (not return raw model)
        reaction_serializer = ReactionSerializer(reaction, context=self.context)

        return {
            'reaction': reaction_serializer.data,
            'created': created,
            'is_active': reaction.is_active
        }


class ReactionAggregateSerializer(serializers.Serializer):
    """
    Serializer for aggregated reaction data on a post.

    Returns counts by type and whether current user has reacted.

    Example output:
    {
        "counts": {
            "like": 5,
            "love": 2,
            "helpful": 10,
            "thanks": 3
        },
        "user_reactions": ["like", "helpful"]  # Types current user has active
    }
    """

    counts = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Reaction counts by type"
    )
    user_reactions = serializers.ListField(
        child=serializers.CharField(),
        help_text="Reaction types the current user has active"
    )

    @staticmethod
    def get_aggregate_data(post, user=None) -> Dict[str, Any]:
        """
        Get aggregated reaction data for a post.

        Args:
            post: Post instance
            user: Optional User instance (to get user_reactions)

        Returns:
            Dict with counts and user_reactions
        """
        # Get all active reactions for post
        reactions = post.reactions.filter(is_active=True)

        # Count by type
        counts = {
            'like': 0,
            'love': 0,
            'helpful': 0,
            'thanks': 0,
        }

        for reaction in reactions:
            if reaction.reaction_type in counts:
                counts[reaction.reaction_type] += 1

        # Get user's active reactions if user provided
        user_reactions = []
        if user and user.is_authenticated:
            user_reactions = list(
                reactions.filter(user=user)
                .values_list('reaction_type', flat=True)
            )

        return {
            'counts': counts,
            'user_reactions': user_reactions
        }
