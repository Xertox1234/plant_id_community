"""
Custom Wagtail API ViewSets for blog functionality.

Extends Wagtail's PageViewSet with blog-specific filtering,
search, and content delivery features for headless CMS.

Performance Optimizations (Phase 2):
- Redis caching for instant responses (<50ms cached, 24h TTL)
- Query optimization with select_related/prefetch_related
- Cache invalidation via signals (page_published, page_unpublished, post_delete)
"""

import logging
import time
from django.db.models import Q, Prefetch
from django.utils import timezone
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.api.v2.filters import (
    FieldsFilter,
    OrderingFilter,
    SearchFilter
)
from wagtail.images.models import Image

try:
    from wagtail.search.models import Query
except ImportError:
    # For Wagtail versions where Query might be located elsewhere
    Query = None

from ..models import (
    BlogPostPage,
    BlogIndexPage,
    BlogCategoryPage,
    BlogAuthorPage,
    BlogCategory,
    BlogSeries
)
from .serializers import (
    BlogPostPageSerializer,
    BlogPostPageListSerializer,
    BlogIndexPageSerializer,
    BlogCategoryPageSerializer,
    BlogAuthorPageSerializer
)
from ..services.blog_cache_service import BlogCacheService

logger = logging.getLogger(__name__)


class BlogPostPageViewSet(PagesAPIViewSet):
    """
    Custom ViewSet for blog posts with enhanced filtering and search.
    """
    
    # Override serializer classes
    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if getattr(self, 'action', None) == 'list':
            return BlogPostPageListSerializer
        return BlogPostPageSerializer
    
    # Custom filtering
    filter_backends = [
        FieldsFilter,
        OrderingFilter,
        SearchFilter,
    ]
    
    # Allowed fields for filtering
    known_query_parameters = PagesAPIViewSet.known_query_parameters.union([
        'category',
        'category_slug',
        'author',
        'author_username',
        'series',
        'series_slug',
        'tag',
        'difficulty',
        'featured',
        'date_from',
        'date_to',
        'plant_species',
        'format'  # For RSS/Atom feeds
    ])
    
    def get_queryset(self):
        """Enhanced queryset with blog-specific filtering."""
        queryset = BlogPostPage.objects.live().public().specific()
        
        # Category filtering
        category_id = self.request.GET.get('category')
        category_slug = self.request.GET.get('category_slug')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        elif category_slug:
            queryset = queryset.filter(categories__slug=category_slug)
        
        # Author filtering
        author_id = self.request.GET.get('author')
        author_username = self.request.GET.get('author_username')
        if author_id:
            queryset = queryset.filter(author__id=author_id)
        elif author_username:
            queryset = queryset.filter(author__username=author_username)
        
        # Series filtering
        series_id = self.request.GET.get('series')
        series_slug = self.request.GET.get('series_slug')
        if series_id:
            queryset = queryset.filter(series__id=series_id)
        elif series_slug:
            queryset = queryset.filter(series__slug=series_slug)
        
        # Tag filtering
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__name__iexact=tag)
        
        # Difficulty filtering
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        # Featured posts
        featured = self.request.GET.get('featured')
        if featured and featured.lower() in ['true', '1']:
            queryset = queryset.filter(is_featured=True)
        
        # Date range filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(publish_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(publish_date__lte=date_to)
        
        # Plant species filtering
        plant_species = self.request.GET.get('plant_species')
        if plant_species:
            queryset = queryset.filter(related_plant_species__id=plant_species)
        
        # Conditional prefetching based on action type (list vs retrieve)
        # This prevents memory issues from aggressive prefetching
        action = getattr(self, 'action', None)

        if action == 'list':
            # List view: Optimized for multiple posts with limited related data
            from ..constants import MAX_RELATED_PLANT_SPECIES

            queryset = queryset.select_related(
                'author',  # ForeignKey - reduces queries for author info
                'series',  # ForeignKey - reduces queries for series info
            ).prefetch_related(
                'categories',  # ManyToMany - fetch all categories (usually <5 per post)
                'tags',  # ManyToMany - tags prefetched but limited in serializer
                Prefetch(
                    'related_plant_species',  # Limit to most relevant
                    queryset=BlogPostPage.related_plant_species.through.objects.select_related(
                        'plantspecies'
                    )[:MAX_RELATED_PLANT_SPECIES]
                ),
            )

            # List view: Only prefetch thumbnail renditions
            try:
                queryset = queryset.prefetch_related(
                    Prefetch(
                        'featured_image',
                        queryset=Image.objects.prefetch_renditions(
                            'fill-400x300',  # List page thumbnail only
                        )
                    )
                )
                logger.debug("[PERF] Image rendition prefetching enabled (list view)")
            except (AttributeError, TypeError) as e:
                logger.warning(f"[PERF] Image rendition prefetching not available: {e}")

        elif action == 'retrieve':
            # Detail view: Prefetch full data and larger renditions
            queryset = queryset.select_related(
                'author',
                'series',
            ).prefetch_related(
                'categories',
                'tags',
                'related_plant_species',  # All related species for detail view
            )

            # Detail view: Prefetch full-size renditions
            try:
                queryset = queryset.prefetch_related(
                    Prefetch(
                        'featured_image',
                        queryset=Image.objects.prefetch_renditions(
                            'fill-800x600',  # Detail page hero
                            'width-1200',    # Full width images
                        )
                    )
                )
                logger.debug("[PERF] Image rendition prefetching enabled (detail view)")
            except (AttributeError, TypeError) as e:
                logger.warning(f"[PERF] Image rendition prefetching not available: {e}")

        else:
            # Other actions (featured, recent, etc.): Basic prefetching
            queryset = queryset.select_related('author', 'series')

        return queryset.distinct()
    
    def get_ordering(self):
        """Default ordering for blog posts."""
        ordering = self.request.GET.get('order', '-first_published_at')
        
        # Map friendly ordering names
        ordering_map = {
            'newest': '-first_published_at',
            'oldest': 'first_published_at',
            'title': 'title',
            'title_desc': '-title',
            'popular': '-views_count',  # If you add view tracking
        }
        
        return ordering_map.get(ordering, ordering)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured blog posts."""
        featured_posts = self.get_queryset().filter(is_featured=True)[:6]
        
        serializer = BlogPostPageListSerializer(
            featured_posts, many=True, context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent blog posts."""
        limit = int(request.GET.get('limit', 10))
        recent_posts = self.get_queryset()[:limit]
        
        serializer = BlogPostPageListSerializer(
            recent_posts, many=True, context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get posts grouped by category."""
        categories = BlogCategory.objects.filter(is_featured=True)
        
        result = []
        for category in categories:
            posts = self.get_queryset().filter(categories=category)[:5]
            result.append({
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'color': category.color,
                    'icon': category.icon,
                },
                'posts': BlogPostPageListSerializer(
                    posts, many=True, context={'request': request}
                ).data
            })
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def search_suggestions(self, request):
        """Get search suggestions based on query."""
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return Response([])
        
        # Search in titles and tags
        suggestions = []
        
        # Title matches
        title_matches = BlogPostPage.objects.live().public().filter(
            title__icontains=query
        ).values_list('title', flat=True)[:5]
        suggestions.extend([{'type': 'title', 'text': title} for title in title_matches])
        
        # Tag matches
        from taggit.models import Tag
        tag_matches = Tag.objects.filter(
            name__icontains=query,
            taggit_taggeditem_items__content_type__model='blogpostpage'
        ).distinct().values_list('name', flat=True)[:5]
        suggestions.extend([{'type': 'tag', 'text': tag} for tag in tag_matches])
        
        return Response(suggestions[:10])
    
    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        """Get posts related to a specific post."""
        post = self.get_object()
        
        # Find related posts based on categories and tags
        related_posts = BlogPostPage.objects.live().public().exclude(
            id=post.id
        ).filter(
            Q(categories__in=post.categories.all()) |
            Q(tags__in=post.tags.all())
        ).distinct().order_by('-first_published_at')[:6]
        
        serializer = BlogPostPageListSerializer(
            related_posts, many=True, context={'request': request}
        )
        return Response(serializer.data)
    
    def list(self, request, *args, **kwargs):
        """
        Enhanced list view with caching and search tracking.

        Performance (Phase 2.2):
        - Cache check before database queries
        - Instant response (<50ms) on cache hit
        - 24-hour TTL for blog lists
        - Automatic invalidation via signals

        Cache Key: blog:list:{page}:{limit}:{filters_hash}
        """
        start_time = time.time()

        # Extract pagination and filter parameters for cache key
        # Calculate page number consistently (page numbers start at 1)
        offset = int(request.GET.get('offset', 0))
        limit = int(request.GET.get('limit', 10))
        page = (offset // limit) + 1  # Page 1 = offset 0-9, Page 2 = offset 10-19, etc.

        # Extract filters (everything except pagination params)
        filters = {k: v for k, v in request.GET.items()
                   if k not in ['offset', 'limit', 'page']}

        # Check cache first (Phase 2.2)
        cached_response = BlogCacheService.get_blog_list(page, limit, filters)
        if cached_response:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[PERF] Blog list cached response in {elapsed:.2f}ms")
            return Response(cached_response)

        # Track search queries for analytics
        search_query = request.GET.get('search')
        if search_query and Query:
            try:
                Query.get(search_query).add_hit()
            except Exception:
                # Ignore query tracking errors
                pass

        # Cache miss - query database
        response = super().list(request, *args, **kwargs)

        # Cache the response for future requests (Phase 2.2)
        if response.status_code == 200:
            BlogCacheService.set_blog_list(page, limit, filters, response.data)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[PERF] Blog list cold response in {elapsed:.2f}ms")

        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve single blog post with caching.

        Performance (Phase 2.2):
        - Cache check before database queries
        - Instant response (<30ms) on cache hit
        - 24-hour TTL for blog posts
        - Automatic invalidation on publish/unpublish/delete

        Cache Key: blog:post:{slug}
        """
        start_time = time.time()

        # Get the blog post to extract slug
        instance = self.get_object()
        slug = instance.slug

        # Check cache first (Phase 2.2)
        cached_response = BlogCacheService.get_blog_post(slug)
        if cached_response:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[PERF] Blog post '{slug}' cached response in {elapsed:.2f}ms")
            return Response(cached_response)

        # Cache miss - serialize from database
        serializer = self.get_serializer(instance)
        data = serializer.data

        # Cache the response for future requests (Phase 2.2)
        BlogCacheService.set_blog_post(slug, data)

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"[PERF] Blog post '{slug}' cold response in {elapsed:.2f}ms")

        return Response(data)


class BlogIndexPageViewSet(PagesAPIViewSet):
    """ViewSet for blog index pages."""
    
    serializer_class = BlogIndexPageSerializer
    
    def get_queryset(self):
        return BlogIndexPage.objects.live().public().specific()


class BlogCategoryPageViewSet(PagesAPIViewSet):
    """ViewSet for blog category pages."""
    
    serializer_class = BlogCategoryPageSerializer
    
    def get_queryset(self):
        return BlogCategoryPage.objects.live().public().specific()


class BlogAuthorPageViewSet(PagesAPIViewSet):
    """ViewSet for blog author pages."""
    
    serializer_class = BlogAuthorPageSerializer
    
    def get_queryset(self):
        return BlogAuthorPage.objects.live().public().specific()
    
    known_query_parameters = PagesAPIViewSet.known_query_parameters.union([
        'username',
        'expertise'
    ])
    
    def get_queryset_filters(self):
        """Add custom filtering for authors."""
        filters = super().get_queryset_filters()
        
        # Filter by username
        username = self.request.GET.get('username')
        if username:
            filters['author__username'] = username
        
        # Filter by expertise
        expertise = self.request.GET.get('expertise')
        if expertise:
            filters['expertise_areas__name__icontains'] = expertise
        
        return filters


# Additional ViewSet for RSS/Atom feed functionality
class BlogFeedViewSet(BlogPostPageViewSet):
    """
    Special ViewSet for RSS/Atom feeds.
    Returns blog posts in feed-friendly format.
    """
    
    def get_serializer_class(self):
        """Always use list serializer for feeds."""
        return BlogPostPageListSerializer
    
    @action(detail=False, methods=['get'])
    def rss(self, request):
        """RSS feed endpoint."""
        posts = self.get_queryset()[:20]
        
        # You would implement RSS XML generation here
        # For now, return JSON that can be converted to RSS
        serializer = self.get_serializer(posts, many=True)
        
        return Response({
            'format': 'rss',
            'title': 'Plant Community Blog',
            'description': 'Latest posts from the Plant Community',
            'posts': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def atom(self, request):
        """Atom feed endpoint."""
        posts = self.get_queryset()[:20]
        
        serializer = self.get_serializer(posts, many=True)
        
        return Response({
            'format': 'atom',
            'title': 'Plant Community Blog',
            'description': 'Latest posts from the Plant Community',
            'updated': timezone.now().isoformat(),
            'posts': serializer.data
        })