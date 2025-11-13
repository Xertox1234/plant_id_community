"""
Thread serializers for forum API.

Provides list and detail representations with different levels of nesting.
List view is optimized for performance, detail view includes full related data.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from typing import Dict, Any, Optional

from ..models import Thread, Category

User = get_user_model()


class ThreadAuthorSerializer(serializers.ModelSerializer):
    """Minimal user serializer for thread authors."""

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


class ThreadCategorySerializer(serializers.ModelSerializer):
    """Minimal category serializer for thread's category."""

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon']


class ThreadListSerializer(serializers.ModelSerializer):
    """
    Lightweight thread serializer for list views.

    Optimized for performance with minimal nesting.
    Use with prefetch_related('author', 'category') in viewset.
    """

    author = ThreadAuthorSerializer(read_only=True)
    category = ThreadCategorySerializer(read_only=True)

    class Meta:
        model = Thread
        fields = [
            'id',
            'title',
            'slug',
            'author',
            'category',
            'excerpt',
            'is_pinned',
            'is_locked',
            'is_active',
            'view_count',
            'post_count',
            'last_activity_at',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'slug',  # Auto-generated
            'view_count',  # System-managed
            'post_count',  # System-managed
            'last_activity_at',  # System-managed
            'created_at',
        ]


class ThreadDetailSerializer(serializers.ModelSerializer):
    """
    Full thread serializer for detail views.

    Includes all thread data plus nested author and category.
    Use with select_related('author', 'category') in viewset.
    """

    author = ThreadAuthorSerializer(read_only=True)
    category = ThreadCategorySerializer(read_only=True)

    # First post data (optional, fetched in viewset if needed)
    first_post = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = [
            'id',
            'title',
            'slug',
            'author',
            'category',
            'excerpt',
            'is_pinned',
            'is_locked',
            'is_active',
            'view_count',
            'post_count',
            'last_activity_at',
            'first_post',  # Includes first post content
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'slug',
            'view_count',
            'post_count',
            'last_activity_at',
            'created_at',
            'updated_at',
        ]

    def get_first_post(self, obj: Thread) -> Optional[Dict[str, Any]]:
        """
        Get first post in thread if available.

        Returns:
            Dict with first post data or None if not found.

        Performance:
            - Viewset prefetches first posts to avoid N+1 (retrieve action only)
            - Uses prefetched data if available, falls back to query
            - Returns None if first post doesn't exist (shouldn't happen)
        """
        # Import here to avoid circular import
        from .post_serializer import PostSerializer

        # Check if posts were prefetched by viewset (retrieve action)
        # ThreadViewSet.get_queryset() sets up prefetch_related with 'posts' queryset
        try:
            # Try to access prefetched posts (no query if prefetched)
            prefetched_posts = obj.posts.all()

            # If prefetched, this won't trigger a query
            # The prefetch filter ensures only is_first_post=True and is_active=True are loaded
            first_post = prefetched_posts[0] if prefetched_posts else None
        except (IndexError, AttributeError):
            # Fallback: query directly if not prefetched (list action or cache miss)
            first_post = obj.posts.filter(is_first_post=True, is_active=True).first()

        if first_post:
            return PostSerializer(first_post, context=self.context).data

        return None


class ThreadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new threads.

    Validates input and creates thread with first post.
    """

    # First post content (required when creating thread)
    first_post_content = serializers.CharField(
        max_length=50000,
        write_only=True,
        help_text="Content for the first post in the thread"
    )
    first_post_format = serializers.ChoiceField(
        choices=['plain', 'markdown', 'rich'],
        default='plain',
        write_only=True,
        help_text="Content format (plain, markdown, or rich)"
    )

    class Meta:
        model = Thread
        fields = [
            'title',
            'category',
            'excerpt',
            'first_post_content',
            'first_post_format',
        ]

    def create(self, validated_data: Dict[str, Any]) -> Thread:
        """
        Create thread and first post atomically.

        Args:
            validated_data: Validated thread data including first_post_content

        Returns:
            Created Thread instance

        Note:
            Author is set in the viewset's perform_create method.
        """
        # Extract first post data
        first_post_content = validated_data.pop('first_post_content')
        first_post_format = validated_data.pop('first_post_format', 'plain')

        # Get author from context (set by viewset)
        author = self.context['request'].user

        # Create thread
        thread = Thread.objects.create(author=author, **validated_data)

        # Create first post
        from ..models import Post
        Post.objects.create(
            thread=thread,
            author=author,
            content_raw=first_post_content,
            content_format=first_post_format,
            is_first_post=True
        )

        return thread
