"""
Post serializer for forum API.

Provides nested author/thread data and handles multi-format content.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Dict, Any, Optional

from ..models import Post

User = get_user_model()


class PostAuthorSerializer(serializers.ModelSerializer):
    """Minimal user serializer for post authors."""

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

    def get_avatar_url(self, obj: User) -> Optional[str]:
        """Get avatar URL if available."""
        if hasattr(obj, 'avatar') and obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class PostThreadSerializer(serializers.Serializer):
    """Minimal thread data for posts."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)


class PostSerializer(serializers.ModelSerializer):
    """
    Serializer for forum posts.

    Includes nested author data, thread info, and reaction counts.
    Handles multi-format content (plain, markdown, rich/Draft.js).
    """

    author = PostAuthorSerializer(read_only=True)
    thread_info = serializers.SerializerMethodField()
    edited_by_info = serializers.SerializerMethodField()

    # Reaction counts
    reaction_counts = serializers.SerializerMethodField()

    # Attachments
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id',
            'thread',  # UUID only
            'thread_info',  # Nested thread data
            'author',
            'content_raw',
            'content_rich',  # Draft.js JSON (optional)
            'content_format',
            'is_first_post',
            'is_active',
            'edited_at',
            'edited_by',  # UUID only
            'edited_by_info',  # Nested editor data
            'reaction_counts',
            'attachments',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_first_post',  # Set on creation only
            'edited_at',  # System-managed
            'created_at',
            'updated_at',
        ]

    def get_thread_info(self, obj: Post) -> Dict[str, Any]:
        """Get minimal thread information."""
        return {
            'id': str(obj.thread.id),
            'title': obj.thread.title,
            'slug': obj.thread.slug,
        }

    def get_edited_by_info(self, obj: Post) -> Optional[Dict[str, Any]]:
        """Get editor info if post was edited."""
        if not obj.edited_by:
            return None

        return PostAuthorSerializer(obj.edited_by, context=self.context).data

    def get_reaction_counts(self, obj: Post) -> Dict[str, int]:
        """
        Get aggregated reaction counts.

        Returns:
            Dict mapping reaction types to counts, e.g.:
            {
                'like': 5,
                'love': 2,
                'helpful': 10,
                'thanks': 3
            }

        Performance:
            - List view: Uses pre-annotated counts (instant, no query)
            - Detail view: Falls back to prefetched reactions
            - Counts only active reactions (is_active=True)

        See: Issue #96 - perf: Optimize reaction counts with database annotations
        """
        # Check if counts were annotated by viewset (list view)
        if hasattr(obj, 'like_count'):
            # Use pre-computed annotations (O(1), no query)
            return {
                'like': obj.like_count,
                'love': obj.love_count,
                'helpful': obj.helpful_count,
                'thanks': obj.thanks_count,
            }

        # Fallback for detail view (uses filtered prefetch from viewset)
        from ..models import Reaction

        # Get active reactions for this post (already filtered by Prefetch in viewset)
        reactions = obj.reactions.all()

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

        return counts

    def get_attachments(self, obj: Post) -> Dict[str, Any]:
        """
        Get post attachments.

        Returns:
            List of attachment dicts with image URLs

        Performance:
            - Viewset should prefetch attachments to avoid N+1
            - Uses prefetched attachments with ordering from viewset (no additional query)
        """
        from .attachment_serializer import AttachmentSerializer

        # Use prefetched attachments (ordered by display_order in viewset)
        attachments = obj.attachments.all()
        return AttachmentSerializer(attachments, many=True, context=self.context).data


class PostCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new posts.

    Simpler than full PostSerializer, only includes writable fields.
    """

    class Meta:
        model = Post
        fields = [
            'thread',
            'content_raw',
            'content_rich',
            'content_format',
        ]

    def create(self, validated_data: Dict[str, Any]) -> Post:
        """
        Create post.

        Author is set in viewset's perform_create method.
        """
        author = self.context['request'].user
        return Post.objects.create(author=author, **validated_data)


class PostUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating posts.

    Only allows editing content, not thread or author.
    """

    class Meta:
        model = Post
        fields = [
            'content_raw',
            'content_rich',
            'content_format',
        ]

    def update(self, instance: Post, validated_data: Dict[str, Any]) -> Post:
        """
        Update post and mark as edited.

        Sets edited_at and edited_by automatically.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Mark as edited by current user
        editor = self.context['request'].user
        instance.mark_edited(editor)

        return instance
