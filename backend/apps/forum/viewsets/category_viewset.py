"""
Category viewset for forum API.

Provides CRUD operations for forum categories with hierarchical support.
"""

import logging
from typing import Dict, Any, Type, List
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission
from rest_framework.serializers import Serializer
from django.db.models import QuerySet

from ..models import Category
from ..serializers import CategorySerializer, CategoryTreeSerializer
from ..permissions import IsModerator

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for forum categories.

    Provides:
    - List: All active categories (flat or with children)
    - Retrieve: Single category detail
    - Create/Update/Delete: Admin only (permissions TBD in Phase 2c)

    Query Parameters:
        - include_children (bool): Include nested children in response
        - tree (bool): Return full category tree with all descendants

    Performance:
        - Conditionally prefetches children to avoid N+1 queries
        - Filters by is_active=True by default
        - Orders by display_order, name
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    ordering = ['display_order', 'name']

    def get_queryset(self) -> QuerySet[Category]:
        """
        Get categories queryset with conditional prefetching.

        Prefetches children when:
        - Action is 'retrieve' (detail view)
        - include_children=true query parameter
        - tree=true query parameter (custom action)

        Returns:
            QuerySet with active categories, optionally with children prefetched
        """
        qs = super().get_queryset()

        # Filter active categories only (can be overridden with ?is_active=false)
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            qs = qs.filter(is_active=True)

        # Conditional prefetch for children
        include_children = self.request.query_params.get('include_children', 'false')
        show_tree = self.request.query_params.get('tree', 'false')

        if (
            self.action == 'retrieve'
            or include_children.lower() == 'true'
            or show_tree.lower() == 'true'
        ):
            # Prefetch children to avoid N+1
            qs = qs.prefetch_related('children')

        # Order by display_order then name
        qs = qs.order_by('display_order', 'name')

        return qs

    def get_serializer_class(self) -> Type[Serializer]:
        """
        Use CategoryTreeSerializer for tree action, otherwise CategorySerializer.

        Returns:
            Serializer class appropriate for the action
        """
        if self.action == 'tree':
            return CategoryTreeSerializer
        return CategorySerializer

    def get_permissions(self) -> List[BasePermission]:
        """
        Dynamic permissions based on action.

        Returns:
            - IsModerator for create/update/delete
            - IsAuthenticatedOrReadOnly for list/retrieve
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsModerator()]
        return [IsAuthenticatedOrReadOnly()]

    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Add include_children to serializer context.

        Returns:
            Dict with request and include_children flag
        """
        context = super().get_serializer_context()
        context['request'] = self.request

        # Pass include_children to serializer
        include_children = self.request.query_params.get('include_children', 'false')
        # Also include children for retrieve action (detail view always shows children)
        context['include_children'] = (
            include_children.lower() == 'true' or
            self.action == 'retrieve'
        )

        return context

    @action(detail=False, methods=['GET'])
    def tree(self, request: Request) -> Response:
        """
        Return full category tree with all descendants.

        GET /api/v1/forum/categories/tree/

        Returns:
            List of root categories with nested children using CategoryTreeSerializer

        Performance:
            - Returns only root categories (parent=None)
            - Recursively includes all descendants via CategoryTreeSerializer
            - Prefetches children to avoid N+1 queries

        Example response:
        [
            {
                "id": "uuid",
                "name": "Plant Care",
                "slug": "plant-care",
                "children": [
                    {
                        "id": "uuid",
                        "name": "Watering",
                        "slug": "watering",
                        "children": []
                    },
                    ...
                ]
            },
            ...
        ]
        """
        # Get root categories only (parent=None)
        root_categories = self.get_queryset().filter(parent=None)

        # Use CategoryTreeSerializer to include nested children
        serializer = CategoryTreeSerializer(
            root_categories,
            many=True,
            context=self.get_serializer_context()
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
