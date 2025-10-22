"""
Serializers for blog API endpoints.

Provides JSON serialization for blog models following the existing patterns
from plant identification and forum APIs.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from taggit.serializers import TagListSerializerField, TaggitSerializer

from .models import (
    BlogPostPage,
    BlogCategory,
    BlogComment,
    BlogSeries,
    BlogAuthorPage,
    BlogNewsletter
)

User = get_user_model()


class BlogCategorySerializer(serializers.ModelSerializer):
    """Serializer for blog categories."""
    
    post_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'color', 
            'is_featured', 'post_count', 'created_at'
        ]
    
    def get_post_count(self, obj):
        """Get the number of published posts in this category."""
        return obj.blogpostpage_set.live().public().count()


class BlogSeriesSerializer(serializers.ModelSerializer):
    """Serializer for blog series."""
    
    post_count = serializers.SerializerMethodField()
    posts_url = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogSeries
        fields = [
            'id', 'title', 'slug', 'description', 'image', 
            'is_completed', 'post_count', 'posts_url', 'created_at'
        ]
    
    def get_post_count(self, obj):
        """Get the number of posts in this series."""
        return obj.blogpostpage_set.live().public().count()
    
    def get_posts_url(self, obj):
        """Get URL to fetch posts in this series."""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/blog/series/{obj.slug}/posts/')
        return None


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for blog authors."""
    
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 
            'display_name', 'avatar_url'
        ]
    
    def get_avatar_url(self, obj):
        """Get avatar URL if available."""
        if hasattr(obj, 'avatar') and obj.avatar:
            request = self.context.get('request')
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
            'id', 'title', 'author', 'bio', 'expertise_areas', 
            'social_links', 'post_count'
        ]
    
    def get_post_count(self, obj):
        """Get the number of published posts by this author."""
        return BlogPostPage.objects.live().public().filter(author=obj.author).count()


class BlogCommentSerializer(serializers.ModelSerializer):
    """Serializer for blog comments."""
    
    author = UserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    is_reply = serializers.ReadOnlyField()
    
    class Meta:
        model = BlogComment
        fields = [
            'id', 'post', 'author', 'content', 'parent', 'is_approved',
            'is_reply', 'replies', 'created_at', 'updated_at'
        ]
        read_only_fields = ['author', 'is_approved', 'created_at', 'updated_at']
    
    def get_replies(self, obj):
        """Get approved replies to this comment."""
        if obj.is_reply:  # Don't nest replies of replies
            return []
        
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
            'id', 'title', 'slug', 'author', 'publish_date', 'first_published_at',
            'introduction', 'content_blocks', 'categories', 'tags', 'series', 
            'series_order', 'featured_image', 'is_featured', 'reading_time',
            'related_plant_species', 'difficulty_level', 'allow_comments',
            'url', 'excerpt', 'comment_count', 'meta_description'
        ]
    
    def get_url(self, obj):
        """Get the full URL to the blog post."""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.get_url())
        return obj.get_url()
    
    def get_excerpt(self, obj):
        """Get excerpt from introduction or content."""
        if obj.introduction:
            # Strip HTML and truncate
            import re
            text = re.sub('<[^<]+?>', '', str(obj.introduction))
            return text[:200] + '...' if len(text) > 200 else text
        return ''
    
    def get_comment_count(self, obj):
        """Get the number of approved comments."""
        if obj.allow_comments:
            return obj.comments.filter(is_approved=True).count()
        return 0


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
            'id', 'title', 'slug', 'author', 'publish_date', 'first_published_at',
            'introduction', 'categories', 'tags', 'featured_image', 
            'is_featured', 'reading_time', 'difficulty_level',
            'url', 'excerpt', 'comment_count'
        ]
    
    def get_url(self, obj):
        """Get the full URL to the blog post."""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.get_url())
        return obj.get_url()
    
    def get_excerpt(self, obj):
        """Get excerpt from introduction."""
        if obj.introduction:
            # Strip HTML and truncate
            import re
            text = re.sub('<[^<]+?>', '', str(obj.introduction))
            return text[:150] + '...' if len(text) > 150 else text
        return ''
    
    def get_comment_count(self, obj):
        """Get the number of approved comments."""
        if obj.allow_comments:
            return obj.comments.filter(is_approved=True).count()
        return 0


class BlogNewsletterSerializer(serializers.ModelSerializer):
    """Serializer for newsletter subscriptions."""
    
    class Meta:
        model = BlogNewsletter
        fields = [
            'email', 'first_name', 'frequency', 'categories',
            'plant_types_interest', 'experience_level', 'source'
        ]
        extra_kwargs = {
            'email': {'write_only': False},
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