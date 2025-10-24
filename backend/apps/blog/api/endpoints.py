"""
Wagtail API endpoints registration for blog snippets and additional functionality.
"""

from wagtail.api.v2.views import BaseAPIViewSet
from wagtail.api.v2.filters import FieldsFilter, OrderingFilter, SearchFilter

from ..models import BlogCategory, BlogSeries
from .serializers import BlogCategorySerializer, BlogSeriesSerializer


class BlogCategoryAPIViewSet(BaseAPIViewSet):
    """API ViewSet for BlogCategory snippets."""

    versioning_class = None  # Disable DRF versioning for Wagtail API
    base_serializer_class = BlogCategorySerializer
    filter_backends = [FieldsFilter, OrderingFilter, SearchFilter]
    body_fields = ['id', 'name', 'slug', 'description', 'icon', 'color', 'is_featured']
    listing_default_fields = ['id', 'name', 'slug', 'description', 'icon', 'color', 'is_featured', 'post_count']
    nested_default_fields = ['id', 'name', 'slug', 'color']
    name = 'blog_categories'
    model = BlogCategory


class BlogSeriesAPIViewSet(BaseAPIViewSet):
    """API ViewSet for BlogSeries snippets."""

    versioning_class = None  # Disable DRF versioning for Wagtail API
    base_serializer_class = BlogSeriesSerializer
    filter_backends = [FieldsFilter, OrderingFilter, SearchFilter]
    body_fields = ['id', 'title', 'slug', 'description', 'cover_image', 'is_completed']
    listing_default_fields = ['id', 'title', 'slug', 'description', 'cover_image', 'is_completed', 'post_count']
    nested_default_fields = ['id', 'title', 'slug']
    name = 'blog_series'
    model = BlogSeries