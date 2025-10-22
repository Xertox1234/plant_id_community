"""
URL configuration for blog API endpoints.

Following the existing pattern from plant identification and forum APIs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'posts', views.BlogPostPageViewSet, basename='blog-posts')
router.register(r'categories', views.BlogCategoryViewSet, basename='blog-categories')
router.register(r'series', views.BlogSeriesViewSet, basename='blog-series')
router.register(r'authors', views.BlogAuthorViewSet, basename='blog-authors')
router.register(r'comments', views.BlogCommentViewSet, basename='blog-comments')
router.register(r'newsletter', views.BlogNewsletterViewSet, basename='blog-newsletter')

app_name = 'blog'

urlpatterns = [
    # Admin interface
    path('admin/', include('apps.blog.admin_urls')),
    
    # API endpoints via router
    path('', include(router.urls)),
    
    # Additional API endpoints
    path('stats/', views.blog_stats, name='blog-stats'),
    path('search/', views.blog_search, name='blog-search'),
]