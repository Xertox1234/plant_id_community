"""
Django REST API views for blog functionality.

Provides API endpoints for blog posts, categories, comments, and other blog-related data.
Following the existing pattern from plant identification and forum APIs.
"""

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import (
    BlogPostPage,
    BlogIndexPage, 
    BlogCategoryPage,
    BlogAuthorPage,
    BlogCategory,
    BlogComment,
    BlogSeries,
    BlogNewsletter
)
from .serializers import (
    BlogPostPageSerializer,
    BlogPostListSerializer,
    BlogCategorySerializer,
    BlogCommentSerializer,
    BlogSeriesSerializer,
    BlogAuthorSerializer,
    BlogNewsletterSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


class BlogPagination(PageNumberPagination):
    """Custom pagination for blog endpoints."""
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100


class BlogPostPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog posts with search, filtering, and categories.
    """
    serializer_class = BlogPostPageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = BlogPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['categories', 'author', 'is_featured', 'difficulty_level']
    search_fields = ['title', 'introduction', 'content_blocks']
    ordering_fields = ['first_published_at', 'title', 'reading_time']
    ordering = ['-first_published_at']
    
    def get_queryset(self):
        """Get published blog posts with related data."""
        queryset = BlogPostPage.objects.live().public().select_related(
            'author'
        ).prefetch_related(
            'categories',
            'tags',
            'series',
            'related_plant_species'
        )
        
        # Filter by category slug if provided
        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(categories__slug=category_slug)
        
        # Filter by tag if provided
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__name__icontains=tag)
        
        # Filter by author username if provided
        author_username = self.request.query_params.get('author')
        if author_username:
            queryset = queryset.filter(author__username=author_username)
        
        # Filter by series slug if provided
        series_slug = self.request.query_params.get('series')
        if series_slug:
            queryset = queryset.filter(series__slug=series_slug)
        
        return queryset.distinct()
    
    def get_serializer_class(self):
        """Use lighter serializer for list view."""
        if self.action == 'list':
            return BlogPostListSerializer
        return BlogPostPageSerializer
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured blog posts."""
        featured_posts = self.get_queryset().filter(is_featured=True)[:6]
        serializer = BlogPostListSerializer(featured_posts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent blog posts."""
        recent_posts = self.get_queryset()[:6]
        serializer = BlogPostListSerializer(recent_posts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        """Get posts related to the current post."""
        post = self.get_object()
        
        # Find posts with similar categories or tags
        related_posts = self.get_queryset().exclude(
            id=post.id
        ).filter(
            Q(categories__in=post.categories.all()) |
            Q(tags__in=post.tags.all())
        ).distinct()[:3]
        
        serializer = BlogPostListSerializer(related_posts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Get approved comments for a blog post."""
        post = self.get_object()
        
        if not post.allow_comments:
            return Response({'detail': 'Comments are disabled for this post.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        comments = BlogComment.objects.filter(
            post=post,
            is_approved=True,
            parent=None  # Only top-level comments
        ).select_related('author').prefetch_related('replies').order_by('created_at')
        
        serializer = BlogCommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_comment(self, request, pk=None):
        """Add a new comment to a blog post."""
        post = self.get_object()
        
        if not post.allow_comments:
            return Response({'detail': 'Comments are disabled for this post.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Create comment
        comment_data = request.data.copy()
        comment_data['post'] = post.id
        comment_data['author'] = request.user.id
        
        serializer = BlogCommentSerializer(data=comment_data, context={'request': request})
        if serializer.is_valid():
            comment = serializer.save(author=request.user)
            return Response(BlogCommentSerializer(comment, context={'request': request}).data, 
                          status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BlogCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog categories.
    """
    queryset = BlogCategory.objects.all()
    serializer_class = BlogCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured categories."""
        featured_categories = self.queryset.filter(is_featured=True)
        serializer = self.get_serializer(featured_categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def posts(self, request, slug=None):
        """Get posts in a specific category."""
        category = self.get_object()
        
        posts = BlogPostPage.objects.live().public().filter(
            categories=category
        ).select_related('author').order_by('-first_published_at')
        
        # Apply pagination
        paginator = BlogPagination()
        page = paginator.paginate_queryset(posts, request)
        
        if page is not None:
            serializer = BlogPostListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = BlogPostListSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)


class BlogSeriesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog series.
    """
    queryset = BlogSeries.objects.all()
    serializer_class = BlogSeriesSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    
    @action(detail=True, methods=['get'])
    def posts(self, request, slug=None):
        """Get posts in a specific series."""
        series = self.get_object()
        
        posts = BlogPostPage.objects.live().public().filter(
            series=series
        ).select_related('author').order_by('series_order', 'first_published_at')
        
        serializer = BlogPostListSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)


class BlogAuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog authors.
    """
    serializer_class = BlogAuthorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'author__username'
    
    def get_queryset(self):
        """Get authors who have published posts."""
        return BlogAuthorPage.objects.filter(
            author__blogpostpage__live=True
        ).select_related('author').distinct()
    
    @action(detail=True, methods=['get'])
    def posts(self, request, author__username=None):
        """Get posts by a specific author."""
        author_page = self.get_object()
        
        posts = BlogPostPage.objects.live().public().filter(
            author=author_page.author
        ).select_related('author').prefetch_related('categories').order_by('-first_published_at')
        
        # Apply pagination
        paginator = BlogPagination()
        page = paginator.paginate_queryset(posts, request)
        
        if page is not None:
            serializer = BlogPostListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = BlogPostListSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)


class BlogCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for blog comments with moderation.
    """
    serializer_class = BlogCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Get comments visible to the current user."""
        if self.request.user.is_staff:
            # Staff can see all comments
            return BlogComment.objects.all().select_related('author', 'post')
        else:
            # Regular users see only approved comments
            return BlogComment.objects.filter(
                is_approved=True
            ).select_related('author', 'post')
    
    def perform_create(self, serializer):
        """Set the author to the current user when creating a comment."""
        serializer.save(author=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def flag(self, request, pk=None):
        """Flag a comment for moderation."""
        comment = self.get_object()
        
        # Increment flag count
        comment.flag_count += 1
        if comment.flag_count >= 5:  # Auto-hide after 5 flags
            comment.is_flagged = True
        comment.save()
        
        return Response({'detail': 'Comment has been flagged for review.'})


class BlogNewsletterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for newsletter subscriptions.
    """
    queryset = BlogNewsletter.objects.all()
    serializer_class = BlogNewsletterSerializer
    permission_classes = [permissions.AllowAny]  # Allow anonymous subscriptions
    http_method_names = ['get', 'post', 'delete']  # No PUT/PATCH
    
    def get_queryset(self):
        """Staff can see all subscriptions, users see only their own."""
        if self.request.user.is_staff:
            return self.queryset
        elif self.request.user.is_authenticated:
            return self.queryset.filter(email=self.request.user.email)
        else:
            return self.queryset.none()
    
    def create(self, request):
        """Subscribe to newsletter."""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Check if already subscribed
            email = serializer.validated_data['email']
            if BlogNewsletter.objects.filter(email=email).exists():
                return Response(
                    {'detail': 'This email is already subscribed.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get IP address for tracking
            ip_address = request.META.get('REMOTE_ADDR')
            serializer.save(ip_address=ip_address)
            
            return Response(
                {'detail': 'Successfully subscribed to newsletter.'}, 
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def unsubscribe(self, request):
        """Unsubscribe from newsletter."""
        email = request.data.get('email')
        
        if not email:
            return Response(
                {'detail': 'Email address is required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            subscription = BlogNewsletter.objects.get(email=email)
            subscription.unsubscribe()
            return Response({'detail': 'Successfully unsubscribed.'})
        except BlogNewsletter.DoesNotExist:
            return Response(
                {'detail': 'Email address not found.'}, 
                status=status.HTTP_404_NOT_FOUND
            )


# Additional API views for blog statistics and search
from rest_framework.decorators import api_view


@api_view(['GET'])
def blog_stats(request):
    """Get blog statistics."""
    stats = {
        'total_posts': BlogPostPage.objects.live().public().count(),
        'total_categories': BlogCategory.objects.count(),
        'total_authors': User.objects.filter(blogpostpage__live=True).distinct().count(),
        'total_comments': BlogComment.objects.filter(is_approved=True).count(),
        'featured_posts': BlogPostPage.objects.live().public().filter(is_featured=True).count(),
    }
    
    # Recent activity
    recent_posts = BlogPostPage.objects.live().public().order_by('-first_published_at')[:5]
    stats['recent_posts'] = BlogPostListSerializer(recent_posts, many=True, context={'request': request}).data
    
    # Popular categories (by post count)
    popular_categories = BlogCategory.objects.annotate(
        post_count=Count('blogpostpage')
    ).filter(post_count__gt=0).order_by('-post_count')[:5]
    stats['popular_categories'] = BlogCategorySerializer(popular_categories, many=True, context={'request': request}).data
    
    return Response(stats)


@api_view(['GET'])
def blog_search(request):
    """Search blog content."""
    query = request.GET.get('q', '')
    
    if not query:
        return Response({'detail': 'Search query is required.'}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    # Search blog posts
    posts = BlogPostPage.objects.live().public().filter(
        Q(title__icontains=query) |
        Q(introduction__icontains=query) |
        Q(content_blocks__icontains=query) |
        Q(tags__name__icontains=query)
    ).distinct().select_related('author').prefetch_related('categories')[:20]
    
    # Search categories
    categories = BlogCategory.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query)
    )[:10]
    
    results = {
        'posts': BlogPostListSerializer(posts, many=True, context={'request': request}).data,
        'categories': BlogCategorySerializer(categories, many=True, context={'request': request}).data,
        'query': query,
        'total_results': len(posts) + len(categories)
    }
    
    return Response(results)
