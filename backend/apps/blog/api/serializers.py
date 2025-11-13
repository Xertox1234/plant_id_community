"""
Custom Wagtail API serializers for blog models.

Provides headless CMS functionality with StreamField rendering,
filtering capabilities, and plant-specific content integration.
"""

from rest_framework import serializers
from wagtail.api.v2.serializers import PageSerializer, BaseSerializer
from wagtail.api.v2.utils import get_full_url
from wagtail.images.api.fields import ImageRenditionField
from wagtail.rich_text import get_text_for_indexing
from django.utils.text import Truncator

from ..models import (
    BlogPostPage,
    BlogIndexPage,
    BlogCategoryPage,
    BlogAuthorPage,
    BlogCategory,
    BlogSeries,
    BlogComment
)


class BlogCategorySerializer(BaseSerializer):
    """Serializer for blog categories as snippets."""

    post_count = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    # Wagtail API expects meta_fields attribute (fields shown in 'meta' section)
    meta_fields = ['type', 'detail_url']

    class Meta:
        model = BlogCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'color',
            'is_featured', 'post_count', 'url', 'created_at'
        ]
    
    def get_post_count(self, obj):
        """Get number of live published posts in this category."""
        return obj.blogpostpage_set.live().public().count()
    
    def get_url(self, obj):
        """Get category page URL if it exists."""
        request = self.context.get('request')
        category_page = BlogCategoryPage.objects.filter(category=obj).live().first()
        if category_page and request:
            return get_full_url(request, category_page.get_url())
        return None


class BlogSeriesSerializer(BaseSerializer):
    """Serializer for blog series as snippets."""

    post_count = serializers.SerializerMethodField()
    cover_image = ImageRenditionField('fill-300x200', source='image', read_only=True)
    posts_url = serializers.SerializerMethodField()

    # Wagtail API expects meta_fields attribute (fields shown in 'meta' section)
    meta_fields = ['type', 'detail_url']

    class Meta:
        model = BlogSeries
        fields = [
            'id', 'title', 'slug', 'description', 'cover_image',
            'is_completed', 'post_count', 'posts_url', 'created_at'
        ]
    
    def get_post_count(self, obj):
        """Get number of posts in this series."""
        return obj.blogpostpage_set.live().public().count()
    
    def get_posts_url(self, obj):
        """Get URL to fetch posts in this series."""
        request = self.context.get('request')
        if request:
            return get_full_url(request, f'/api/v2/pages/?type=blog.BlogPostPage&series={obj.id}')
        return None


class BlogAuthorPageSerializer(PageSerializer):
    """Serializer for blog author pages."""
    
    author = serializers.SerializerMethodField()
    expertise_areas = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogAuthorPage
        fields = ['id', 'title', 'slug', 'url'] + [
            'author', 'bio', 'expertise_areas', 'social_links',
            'post_count', 'recent_posts'
        ]
    
    def get_author(self, obj):
        """Get author user data."""
        if obj.author:
            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'first_name': obj.author.first_name,
                'last_name': obj.author.last_name,
                'display_name': obj.author.get_full_name() or obj.author.username
            }
        return None
    
    def get_expertise_areas(self, obj):
        """Get expertise area tags."""
        return [tag.name for tag in obj.expertise_areas.all()]
    
    def get_post_count(self, obj):
        """Get number of published posts by this author."""
        if obj.author:
            return BlogPostPage.objects.live().public().filter(author=obj.author).count()
        return 0
    
    def get_recent_posts(self, obj):
        """Get recent posts by this author."""
        if not obj.author:
            return []
        
        recent_posts = BlogPostPage.objects.live().public().filter(
            author=obj.author
        ).order_by('-first_published_at')[:3]
        
        return [{
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'url': get_full_url(self.context.get('request'), post.get_url()),
            'published_date': post.first_published_at,
            'excerpt': self._get_excerpt(post)
        } for post in recent_posts]
    
    def _get_excerpt(self, post):
        """Extract excerpt from post introduction."""
        if post.introduction:
            text = get_text_for_indexing(post.introduction)
            return Truncator(text).words(30)
        return ''


class BlogPostPageSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for blog posts with full content."""

    author = serializers.SerializerMethodField()
    categories = BlogCategorySerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()
    series = BlogSeriesSerializer(read_only=True)
    featured_image = ImageRenditionField('fill-800x400', read_only=True)
    featured_image_thumb = ImageRenditionField('fill-300x200', source='featured_image', read_only=True)
    reading_time = serializers.ReadOnlyField()
    excerpt = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    related_posts = serializers.SerializerMethodField()
    related_plant_species = serializers.SerializerMethodField()
    social_image = ImageRenditionField('fill-1200x630', read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = BlogPostPage
        fields = [
            'id', 'title', 'slug', 'url',
            'author', 'publish_date', 'introduction', 'content_blocks',
            'categories', 'tags', 'series', 'series_order',
            'featured_image', 'featured_image_thumb', 'is_featured',
            'reading_time', 'difficulty_level', 'allow_comments',
            'excerpt', 'comment_count', 'related_posts',
            'related_plant_species', 'social_image'
        ]

    def get_url(self, obj):
        """Get page URL."""
        try:
            url = obj.get_url()
            if not url:
                # In test context or when no site configured, return None
                return None
            request = self.context.get('request')
            if request:
                from wagtail.api.v2.utils import get_full_url
                return get_full_url(request, url)
            return url
        except Exception:
            # Handle cases where get_url() fails (e.g., no site root)
            return None
    
    def get_author(self, obj):
        """Get author information."""
        if obj.author:
            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'first_name': obj.author.first_name,
                'last_name': obj.author.last_name,
                'display_name': obj.author.get_full_name() or obj.author.username,
                'author_page_url': self._get_author_page_url(obj.author)
            }
        return None
    
    def get_tags(self, obj):
        """Get tag names."""
        return [tag.name for tag in obj.tags.all()]
    
    def get_excerpt(self, obj):
        """Get excerpt from introduction."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(50)
        return ''
    
    def get_comment_count(self, obj):
        """
        Get approved comment count.

        Performance (Issue #182):
        - Uses annotated _comment_count from viewset if available
        - Falls back to query if annotation not present (e.g., in tests)
        """
        if not obj.allow_comments:
            return 0

        # Check if viewset added annotation (list/retrieve actions)
        if hasattr(obj, '_comment_count'):
            return obj._comment_count

        # Fallback: direct query (only in edge cases without optimization)
        return obj.comments.filter(is_approved=True).count()
    
    def get_related_posts(self, obj):
        """
        Get related posts based on categories and tags.

        Performance (Issue #182):
        - Uses prefetched categories with related posts from viewset if available
        - Falls back to query if prefetch not present (e.g., in tests or list view)
        """
        request = self.context.get('request')

        # Check if viewset prefetched related posts through categories
        if hasattr(obj, '_prefetched_categories_with_posts'):
            # Use prefetched data (retrieve action)
            related_posts_set = set()
            for category in obj._prefetched_categories_with_posts:
                if hasattr(category, '_prefetched_related_posts'):
                    for post in category._prefetched_related_posts:
                        if post.id != obj.id:  # Exclude current post
                            related_posts_set.add(post)
                            if len(related_posts_set) >= 3:
                                break
                if len(related_posts_set) >= 3:
                    break

            related_posts = sorted(
                list(related_posts_set),
                key=lambda p: p.first_published_at,
                reverse=True
            )[:3]
        else:
            # Fallback: direct query (list action or tests)
            related_posts = BlogPostPage.objects.live().public().exclude(
                id=obj.id
            ).filter(
                categories__in=obj.categories.all()
            ).distinct().order_by('-first_published_at')[:3]

        return [{
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'url': get_full_url(request, post.get_url()),
            'published_date': post.first_published_at,
            'excerpt': self._get_post_excerpt(post),
            'featured_image': self._get_post_image(post, request)
        } for post in related_posts]
    
    def get_related_plant_species(self, obj):
        """Get related plant species."""
        return [{
            'id': species.id,
            'common_name': species.common_name,
            'scientific_name': species.scientific_name,
        } for species in obj.related_plant_species.all()]
    
    def _get_author_page_url(self, author):
        """Get author page URL if exists."""
        request = self.context.get('request')
        author_page = BlogAuthorPage.objects.filter(author=author).live().first()
        if author_page and request:
            return get_full_url(request, author_page.get_url())
        return None
    
    def _get_post_excerpt(self, post):
        """Get excerpt from post."""
        if post.introduction:
            text = get_text_for_indexing(post.introduction)
            return Truncator(text).words(20)
        return ''
    
    def _get_post_image(self, post, request):
        """Get post featured image URL."""
        if post.featured_image:
            rendition = post.featured_image.get_rendition('fill-300x200')
            if request:
                return get_full_url(request, rendition.url)
            return rendition.url
        return None


class BlogPostPageListSerializer(serializers.ModelSerializer):
    """Lighter serializer for blog post lists and feeds."""

    author = serializers.SerializerMethodField()
    categories = BlogCategorySerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()
    featured_image_thumb = ImageRenditionField('fill-300x200', source='featured_image', read_only=True)
    reading_time = serializers.ReadOnlyField()
    excerpt = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = BlogPostPage
        fields = [
            'id', 'title', 'slug', 'url',
            'author', 'publish_date', 'categories', 'tags',
            'featured_image_thumb', 'is_featured', 'reading_time',
            'difficulty_level', 'excerpt', 'comment_count'
        ]

    def get_url(self, obj):
        """Get page URL."""
        try:
            url = obj.get_url()
            if not url:
                # In test context or when no site configured, return None
                return None
            request = self.context.get('request')
            if request:
                from wagtail.api.v2.utils import get_full_url
                return get_full_url(request, url)
            return url
        except Exception:
            # Handle cases where get_url() fails (e.g., no site root)
            return None
    
    def get_author(self, obj):
        """Get basic author information."""
        if obj.author:
            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'display_name': obj.author.get_full_name() or obj.author.username
            }
        return None
    
    def get_tags(self, obj):
        """Get tag names."""
        return [tag.name for tag in obj.tags.all()]
    
    def get_excerpt(self, obj):
        """Get short excerpt."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(30)
        return ''
    
    def get_comment_count(self, obj):
        """
        Get approved comment count.

        Performance (Issue #182):
        - Uses annotated _comment_count from viewset if available
        - Falls back to query if annotation not present (e.g., in tests)
        """
        if not obj.allow_comments:
            return 0

        # Check if viewset added annotation (list/retrieve actions)
        if hasattr(obj, '_comment_count'):
            return obj._comment_count

        # Fallback: direct query (only in edge cases without optimization)
        return obj.comments.filter(is_approved=True).count()


class BlogIndexPageSerializer(PageSerializer):
    """Serializer for blog index pages."""
    
    featured_posts = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogIndexPage
        fields = ['id', 'title', 'slug', 'url'] + [
            'introduction', 'posts_per_page', 'show_featured_posts',
            'show_categories', 'featured_posts_title', 'featured_posts',
            'categories', 'recent_posts'
        ]
    
    def get_featured_posts(self, obj):
        """Get featured posts if enabled."""
        if not obj.show_featured_posts:
            return []
        
        featured_posts = BlogPostPage.objects.live().public().filter(
            is_featured=True
        ).order_by('-first_published_at')[:3]
        
        return BlogPostPageListSerializer(
            featured_posts, many=True, context=self.context
        ).data
    
    def get_categories(self, obj):
        """Get featured categories if enabled."""
        if not obj.show_categories:
            return []
        
        featured_categories = BlogCategory.objects.filter(is_featured=True)
        return BlogCategorySerializer(
            featured_categories, many=True, context=self.context
        ).data
    
    def get_recent_posts(self, obj):
        """Get recent posts for the index."""
        recent_posts = BlogPostPage.objects.live().public().order_by(
            '-first_published_at'
        )[:obj.posts_per_page]
        
        return BlogPostPageListSerializer(
            recent_posts, many=True, context=self.context
        ).data


class BlogCategoryPageSerializer(PageSerializer):
    """Serializer for blog category pages."""
    
    category = BlogCategorySerializer(read_only=True)
    posts = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogCategoryPage
        fields = ['id', 'title', 'slug', 'url'] + [
            'category', 'posts_per_page', 'posts'
        ]
    
    def get_posts(self, obj):
        """Get posts in this category."""
        posts = BlogPostPage.objects.live().public().filter(
            categories=obj.category
        ).order_by('-first_published_at')[:obj.posts_per_page]
        
        return BlogPostPageListSerializer(
            posts, many=True, context=self.context
        ).data