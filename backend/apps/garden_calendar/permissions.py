"""
Custom permissions for garden calendar endpoints.

Implements ownership-based permissions for garden resources:
- IsGardenOwner: User owns the garden bed
- IsPlantOwner: User owns the plant (via garden bed)
- IsCareTaskOwner: User owns the care task (via plant)
"""
from typing import Any
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView
from django.db.models import Model


class IsGardenOwner(permissions.BasePermission):
    """
    Permission check to ensure user owns the garden bed.

    Works for both object-level and view-level permissions.
    For list views, allows all authenticated users.
    For detail views, restricts to garden bed owner.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check view-level permission.

        Args:
            request: DRF request object
            view: The view being accessed

        Returns:
            True if user is authenticated (list views allow all users)
        """
        # Require authentication for all garden operations
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request: Request, view: APIView, obj: Model) -> bool:
        """
        Check object-level permission for garden bed.

        Args:
            request: DRF request object
            view: The view being accessed
            obj: The GardenBed instance

        Returns:
            True if user owns the garden bed
        """
        # Read permissions are allowed to owner
        # Write permissions are allowed to owner
        return obj.owner == request.user

    message = 'You do not have permission to access this garden bed.'


class IsPlantOwner(permissions.BasePermission):
    """
    Permission check to ensure user owns the plant (via garden bed ownership).

    Works for both object-level and view-level permissions.
    For list views, allows all authenticated users.
    For detail views, restricts to garden bed owner.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check view-level permission.

        Args:
            request: DRF request object
            view: The view being accessed

        Returns:
            True if user is authenticated
        """
        # Require authentication for all plant operations
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request: Request, view: APIView, obj: Model) -> bool:
        """
        Check object-level permission for plant or related objects.

        Args:
            request: DRF request object
            view: The view being accessed
            obj: The Plant, Harvest, or related instance

        Returns:
            True if user owns the garden bed containing this plant
        """
        # Handle different object types that relate to plants
        if hasattr(obj, 'garden_bed'):
            # Direct Plant object
            return obj.garden_bed.owner == request.user
        elif hasattr(obj, 'plant'):
            # Harvest or other object related through plant
            return obj.plant.garden_bed.owner == request.user

        # Fallback: deny if no ownership path found
        return False

    message = 'You do not have permission to access this plant.'


class IsCareTaskOwner(permissions.BasePermission):
    """
    Permission check to ensure user owns the care task (via plant → garden bed).

    Works for both object-level and view-level permissions.
    For list views, allows all authenticated users.
    For detail views, restricts to garden bed owner.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check view-level permission.

        Args:
            request: DRF request object
            view: The view being accessed

        Returns:
            True if user is authenticated
        """
        # Require authentication for all care task operations
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request: Request, view: APIView, obj: Model) -> bool:
        """
        Check object-level permission for care task.

        Args:
            request: DRF request object
            view: The view being accessed
            obj: The CareTask instance

        Returns:
            True if user owns the garden bed containing the plant for this task
        """
        # Check ownership via plant → garden bed
        return obj.plant.garden_bed.owner == request.user

    message = 'You do not have permission to access this care task.'


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission for community features (events, templates).

    - Read: Anyone (authenticated)
    - Write/Update/Delete: Owner only
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check view-level permission.

        Args:
            request: DRF request object
            view: The view being accessed

        Returns:
            True if user is authenticated
        """
        # All authenticated users can read
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request: Request, view: APIView, obj: Model) -> bool:
        """
        Check object-level permission.

        Args:
            request: DRF request object
            view: The view being accessed
            obj: The object instance (Event, Template, etc.)

        Returns:
            True if read-only or user is the owner/organizer/creator
        """
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for owner
        # Handle different owner field names
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif hasattr(obj, 'organizer'):
            return obj.organizer == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user

        # Fallback: deny if no owner field found
        return False

    message = 'You do not have permission to modify this resource.'
