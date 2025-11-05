"""
Serializers for content moderation system.

Phase 4.2: Content Moderation Queue
Handles flagging content and moderation actions with full audit trail.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Dict, Any, Optional

from ..models import FlaggedContent, ModerationAction, Post, Thread
from ..constants import (
    FLAG_REASONS,
    MODERATION_STATUSES,
    MODERATION_ACTIONS,
    MAX_EXPLANATION_LENGTH,
)

User = get_user_model()


class FlagReporterSerializer(serializers.ModelSerializer):
    """Minimal user serializer for flag reporters."""

    class Meta:
        model = User
        fields = ['id', 'username']
        read_only_fields = ['id', 'username']


class FlaggedContentDetailSerializer(serializers.Serializer):
    """Serializer for flagged content details (post or thread)."""

    id = serializers.UUIDField(read_only=True)
    content_type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True, required=False)
    content_raw = serializers.CharField(read_only=True, required=False)
    author_username = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class FlaggedContentSerializer(serializers.ModelSerializer):
    """
    Serializer for flagged content.

    Used for listing and retrieving flagged posts/threads in moderation queue.
    Includes nested reporter data and flagged content preview.
    """

    reporter = FlagReporterSerializer(read_only=True)
    reviewed_by_info = serializers.SerializerMethodField()
    flagged_content = serializers.SerializerMethodField()
    flag_count = serializers.SerializerMethodField()

    class Meta:
        model = FlaggedContent
        fields = [
            'id',
            'content_type',
            'post',
            'thread',
            'reporter',
            'flag_reason',
            'explanation',
            'status',
            'reviewed_by',
            'reviewed_by_info',
            'reviewed_at',
            'moderator_notes',
            'flagged_content',
            'flag_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'reporter',
            'reviewed_by',
            'reviewed_by_info',
            'reviewed_at',
            'created_at',
            'updated_at',
            'flag_count',
        ]

    def get_reviewed_by_info(self, obj: FlaggedContent) -> Optional[Dict[str, Any]]:
        """Get moderator info who reviewed the flag."""
        if obj.reviewed_by:
            return {
                'id': obj.reviewed_by.id,
                'username': obj.reviewed_by.username,
            }
        return None

    def get_flagged_content(self, obj: FlaggedContent) -> Dict[str, Any]:
        """Get preview of the flagged content."""
        content_obj = obj.get_flagged_object()

        if obj.content_type == 'post':
            return {
                'id': str(content_obj.id),
                'content_type': 'post',
                'content_raw': content_obj.content_raw[:500],  # Preview only
                'author_username': content_obj.author.username,
                'thread_title': content_obj.thread.title,
                'created_at': content_obj.created_at.isoformat(),
            }
        else:  # thread
            return {
                'id': str(content_obj.id),
                'content_type': 'thread',
                'title': content_obj.title,
                'excerpt': content_obj.excerpt,
                'author_username': content_obj.author.username,
                'created_at': content_obj.created_at.isoformat(),
            }

    def get_flag_count(self, obj: FlaggedContent) -> int:
        """Get total number of flags for this content."""
        if obj.content_type == 'post':
            return FlaggedContent.objects.filter(
                post=obj.post,
                status='pending'
            ).count()
        else:
            return FlaggedContent.objects.filter(
                thread=obj.thread,
                status='pending'
            ).count()


class FlagSubmissionSerializer(serializers.Serializer):
    """
    Serializer for submitting flags on content.

    Used by regular users to report inappropriate content.
    """

    flag_reason = serializers.ChoiceField(
        choices=[reason[0] for reason in FLAG_REASONS],
        required=True,
        help_text="Reason for flagging"
    )
    explanation = serializers.CharField(
        max_length=MAX_EXPLANATION_LENGTH,
        required=False,
        allow_blank=True,
        help_text="Optional detailed explanation"
    )

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate flag submission."""
        # If reason is "other", explanation should be provided
        if data['flag_reason'] == 'other' and not data.get('explanation'):
            raise serializers.ValidationError({
                'explanation': 'Explanation is required when flag reason is "other"'
            })
        return data


class ModerationActionSerializer(serializers.ModelSerializer):
    """
    Serializer for moderation actions.

    Tracks all actions taken by moderators for accountability.
    """

    moderator_info = serializers.SerializerMethodField()
    affected_user_info = serializers.SerializerMethodField()

    class Meta:
        model = ModerationAction
        fields = [
            'id',
            'flag',
            'moderator',
            'moderator_info',
            'action_type',
            'reason',
            'affected_user',
            'affected_user_info',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'flag',
            'moderator',
            'moderator_info',
            'affected_user',
            'affected_user_info',
            'created_at',
        ]

    def get_moderator_info(self, obj: ModerationAction) -> Dict[str, Any]:
        """Get moderator info."""
        return {
            'id': obj.moderator.id,
            'username': obj.moderator.username,
        }

    def get_affected_user_info(self, obj: ModerationAction) -> Optional[Dict[str, Any]]:
        """Get affected user info."""
        if obj.affected_user:
            return {
                'id': obj.affected_user.id,
                'username': obj.affected_user.username,
            }
        return None


class ModerationReviewSerializer(serializers.Serializer):
    """
    Serializer for reviewing flagged content.

    Used by moderators to approve, reject, or take action on flags.
    """

    action_type = serializers.ChoiceField(
        choices=[action[0] for action in MODERATION_ACTIONS],
        required=True,
        help_text="Action to take"
    )
    reason = serializers.CharField(
        max_length=MAX_EXPLANATION_LENGTH,
        required=True,
        help_text="Reason for this action"
    )
    moderator_notes = serializers.CharField(
        max_length=MAX_EXPLANATION_LENGTH,
        required=False,
        allow_blank=True,
        help_text="Internal notes (not visible to users)"
    )

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate moderation review."""
        # Reason is required for all actions
        if not data.get('reason'):
            raise serializers.ValidationError({
                'reason': 'Reason is required for all moderation actions'
            })
        return data
