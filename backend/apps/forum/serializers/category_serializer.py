"""
Category serializer for forum API.

Provides both nested and flat representations of categories with computed statistics.
"""

from rest_framework import serializers
from typing import Dict, Any, Optional

from ..models import Category


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for forum categories.

    Supports nested representation (with children) and flat representation.
    Includes computed fields for thread and post counts.

    Usage:
        # Flat representation (default)
        CategorySerializer(category)

        # Nested with children
        CategorySerializer(category, context={'include_children': True})
    """

    # Computed fields
    thread_count = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    # Parent category (nested or just ID)
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'parent',
            'parent_name',
            'icon',
            'display_order',
            'is_active',
            'thread_count',
            'post_count',
            'children',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'slug',  # Auto-generated
            'created_at',
            'updated_at',
        ]

    def get_thread_count(self, obj: Category) -> int:
        """
        Get number of active threads in this category.

        Uses model method to leverage database caching/indexes.
        """
        return obj.get_thread_count()

    def get_post_count(self, obj: Category) -> int:
        """
        Get total number of posts in all threads in this category.

        Uses model method which uses aggregate query (not N+1).
        """
        return obj.get_post_count()

    def get_children(self, obj: Category) -> Optional[Dict[str, Any]]:
        """
        Get child categories if requested in context.

        Returns:
            List of child category dicts if include_children=True in context,
            otherwise None to avoid deep nesting.

        Performance:
            - Only fetches children when explicitly requested
            - Avoids N+1 by using prefetch_related in viewset
        """
        include_children = self.context.get('include_children', False)

        if not include_children:
            return None

        # Get active children only
        children = obj.children.filter(is_active=True).order_by('display_order', 'name')

        # Recursively serialize children (but don't nest children of children)
        child_context = {**self.context, 'include_children': False}
        return CategorySerializer(children, many=True, context=child_context).data


class CategoryTreeSerializer(CategorySerializer):
    """
    Extended category serializer that always includes children.

    Use this for category tree endpoints where full hierarchy is needed.
    """

    def get_children(self, obj: Category) -> Dict[str, Any]:
        """Always include children for tree view."""
        children = obj.children.filter(is_active=True).order_by('display_order', 'name')
        return CategoryTreeSerializer(children, many=True, context=self.context).data
