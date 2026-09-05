"""
Serializers for blog API endpoints.

Provides JSON serialization for blog models following the existing patterns
from plant identification and forum APIs.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from taggit.serializers import TaggitSerializer, TagListSerializerField

from .models import (
    BlogAuthorPage,
    BlogCategory,
    BlogComment,
    BlogNewsletter,
    BlogPostPage,
    BlogSeries,
)

User = get_user_model()


def _absolute_page_url(request, page):
    """A page's absolute URL, derived from the request's own host (todo 326).

    Mirrors `apps/blog/api/serializers.py`'s helper of the same name: this
    legacy module's `get_url` methods used to call
    `request.build_absolute_uri(obj.get_url())` directly, which is exactly
    the todo-308 landmine — `Page.get_url()` returns an already-absolute,
    Site-rooted URL once more than one Wagtail `Site` row exists, and
    `build_absolute_uri()` passes an already-absolute string through
    unchanged. `get_url_parts()` instead always returns the page's path
    relative to its own site root, so building the absolute URL from
    `request` here reflects the actual incoming host regardless of `Site`
    row count. Returns None if the page isn't routable, or the bare
    relative path if called with no request.
    """
    url_parts = page.get_url_parts(request=request)
    page_path = url_parts[2] if url_parts else None
    if not page_path:
        return None
    return request.build_absolute_uri(page_path) if request else page_path


class BlogCategorySerializer(serializers.ModelSerializer):
    """Serializer for blog categories."""

    post_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "color",
            "is_featured",
            "post_count",
            "created_at",
        ]

    def get_post_count(self, obj):
        """Get the number of published posts in this category."""
        if hasattr(obj, "_post_count"):
            return obj._post_count
        return obj.blogpostpage_set.live().public().count()


class BlogSeriesSerializer(serializers.ModelSerializer):
    """Serializer for blog series."""

    post_count = serializers.SerializerMethodField()
    posts_url = serializers.SerializerMethodField()

    class Meta:
        model = BlogSeries
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "image",
            "is_completed",
            "post_count",
            "posts_url",
            "created_at",
        ]

    def get_post_count(self, obj):
        """Get the number of posts in this series."""
        if hasattr(obj, "_post_count"):
            return obj._post_count
        return obj.blogpostpage_set.live().public().count()

    def get_posts_url(self, obj):
        """Get URL to fetch posts in this series."""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/api/blog/series/{obj.slug}/posts/")
        return None


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for blog authors."""

    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "display_name",
            "avatar_url",
        ]

    def get_avatar_url(self, obj):
        """Get avatar URL if available."""
        if hasattr(obj, "avatar") and obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class BlogAuthorSerializer(serializers.ModelSerializer):
    """Serializer for blog author pages."""

    author = UserSerializer(read_only=True)
    expertise_areas = TagListSerializerField(read_only=True)
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogAuthorPage
        fields = [
            "id",
            "title",
            "author",
            "bio",
            "expertise_areas",
            "social_links",
            "post_count",
        ]

    def get_post_count(self, obj):
        """Get the number of published posts by this author."""
        if hasattr(obj, "_post_count"):
            return obj._post_count
        return BlogPostPage.objects.live().public().filter(author=obj.author).count()


class BlogCommentSerializer(serializers.ModelSerializer):
    """Serializer for blog comments."""

    author = UserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    is_reply = serializers.ReadOnlyField()

    class Meta:
        model = BlogComment
        fields = [
            "id",
            "post",
            "author",
            "content",
            "parent",
            "is_approved",
            "is_reply",
            "replies",
            "created_at",
            "updated_at",
        ]
        # `post` is read-only since todo 352: the view binds the post from the
        # URL, so a client can no longer target another post through the body.
        # `post` and `parent` are read-only since todo 352: the view binds the
        # post from the URL and resolves `parent` scoped to what the caller can
        # see on that post, so the body can target neither another post nor an
        # arbitrary comment id.
        read_only_fields = [
            "post",
            "parent",
            "author",
            "is_approved",
            "created_at",
            "updated_at",
        ]

    def get_replies(self, obj):
        """Replies to this comment — approved ones, plus the caller's own
        pending ones when the view prefetched `visible_replies` (todo 352).
        Thread depth is ONE level: a reply never nests replies."""
        if obj.is_reply:  # Don't nest replies of replies
            return []

        replies = getattr(obj, "visible_replies", None)
        if replies is None:
            replies = obj.get_replies()
        return BlogCommentSerializer(replies, many=True, context=self.context).data


class BlogPostPageSerializer(TaggitSerializer, serializers.ModelSerializer):
    """Serializer for blog posts."""

    author = UserSerializer(read_only=True)
    categories = BlogCategorySerializer(many=True, read_only=True)
    tags = TagListSerializerField(read_only=True)
    series = BlogSeriesSerializer(read_only=True)
    reading_time = serializers.ReadOnlyField()
    url = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    # Plant-specific fields
    related_plant_species = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = BlogPostPage
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "publish_date",
            "first_published_at",
            "introduction",
            "content_blocks",
            "categories",
            "tags",
            "series",
            "series_order",
            "featured_image",
            "is_featured",
            "reading_time",
            "related_plant_species",
            "difficulty_level",
            "allow_comments",
            "url",
            "excerpt",
            "comment_count",
            "meta_description",
        ]

    def get_url(self, obj):
        """Get the full URL to the blog post (todo 326)."""
        return _absolute_page_url(self.context.get("request"), obj)

    def get_excerpt(self, obj):
        """Get excerpt from introduction or content."""
        if obj.introduction:
            # Strip HTML and truncate
            import re

            text = re.sub("<[^<]+?>", "", str(obj.introduction))
            return text[:200] + "..." if len(text) > 200 else text
        return ""

    def get_comment_count(self, obj):
        """Get the number of approved comments."""
        if not obj.allow_comments:
            return 0
        if hasattr(obj, "_comment_count"):
            return obj._comment_count
        return obj.comments.filter(is_approved=True).count()


class BlogPostListSerializer(serializers.ModelSerializer):
    """Lighter serializer for blog post lists."""

    author = UserSerializer(read_only=True)
    categories = BlogCategorySerializer(many=True, read_only=True)
    tags = TagListSerializerField(read_only=True)
    reading_time = serializers.ReadOnlyField()
    url = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogPostPage
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "publish_date",
            "first_published_at",
            "introduction",
            "categories",
            "tags",
            "featured_image",
            "is_featured",
            "reading_time",
            "difficulty_level",
            "url",
            "excerpt",
            "comment_count",
        ]

    def get_url(self, obj):
        """Get the full URL to the blog post (todo 326)."""
        return _absolute_page_url(self.context.get("request"), obj)

    def get_excerpt(self, obj):
        """Get excerpt from introduction."""
        if obj.introduction:
            # Strip HTML and truncate
            import re

            text = re.sub("<[^<]+?>", "", str(obj.introduction))
            return text[:150] + "..." if len(text) > 150 else text
        return ""

    def get_comment_count(self, obj):
        """Get the number of approved comments."""
        if not obj.allow_comments:
            return 0
        if hasattr(obj, "_comment_count"):
            return obj._comment_count
        return obj.comments.filter(is_approved=True).count()


class BlogNewsletterSerializer(serializers.ModelSerializer):
    """Serializer for newsletter subscriptions."""

    class Meta:
        model = BlogNewsletter
        fields = [
            "email",
            "first_name",
            "frequency",
            "categories",
            "plant_types_interest",
            "experience_level",
            "source",
        ]
        extra_kwargs = {
            "email": {"write_only": False},
        }

    def validate_email(self, value):
        """Validate email format."""
        if not value:
            raise serializers.ValidationError("Email is required.")
        return value.lower()


# Serializer for blog statistics
class BlogStatsSerializer(serializers.Serializer):
    """Serializer for blog statistics."""

    total_posts = serializers.IntegerField()
    total_categories = serializers.IntegerField()
    total_authors = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    featured_posts = serializers.IntegerField()
    recent_posts = BlogPostListSerializer(many=True)
    popular_categories = BlogCategorySerializer(many=True)
