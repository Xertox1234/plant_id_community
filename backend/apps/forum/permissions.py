"""
Forum permission classes.

Provides trust level-based access control for forum operations.
"""

from rest_framework import permissions
from typing import Any


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Allow authors to edit/delete their own content.

    Permissions:
    - Read (GET, HEAD, OPTIONS): Anyone
    - Write (POST, PUT, PATCH, DELETE): Author only

    Usage:
        Apply to ThreadViewSet and PostViewSet for update/delete actions.

    Example:
        >>> permission_classes = [IsAuthorOrReadOnly]
    """

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        """
        Check if user has permission to access this object.

        Args:
            request: Django request object
            view: ViewSet instance
            obj: Object being accessed (Thread or Post)

        Returns:
            True if user can access object, False otherwise
        """
        # Read permissions (GET, HEAD, OPTIONS) allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for the author
        return obj.author == request.user


class IsModerator(permissions.BasePermission):
    """
    Allow moderators to manage any content.

    Moderators are identified by:
    - is_staff=True (Django admin staff)
    - Membership in 'Moderators' group

    Permissions:
    - Moderators can create/update/delete any content
    - Regular users denied

    Usage:
        Apply to CategoryViewSet for create/update/delete actions.
        Combine with IsAuthorOrReadOnly for ThreadViewSet/PostViewSet.

    Example:
        >>> permission_classes = [IsModerator]
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Check if user is a moderator.

        Args:
            request: Django request object
            view: ViewSet instance

        Returns:
            True if user is staff or in Moderators group, False otherwise
        """
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return False

        # Check if user is staff or in Moderators group
        return (
            request.user.is_staff or
            request.user.groups.filter(name='Moderators').exists()
        )


class CanCreateThread(permissions.BasePermission):
    """
    Require minimum trust level to create threads.

    Trust level requirements:
    - New users (trust_level='new'): CANNOT create threads
    - Basic+ users (basic, trusted, veteran, expert): CAN create threads

    This prevents spam from new users while allowing established members
    to create threads freely.

    Permissions:
    - POST (create): Requires trust_level != 'new'
    - Other methods: Allowed

    Usage:
        Apply to ThreadViewSet for create action only.

    Example:
        >>> permission_classes = [CanCreateThread]
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Check if user can create threads based on trust level.

        Args:
            request: Django request object
            view: ViewSet instance

        Returns:
            True if user can create threads, False otherwise
        """
        # Allow all non-POST requests (list, retrieve, update, delete)
        if request.method != 'POST':
            return True

        # Require authenticated user
        if not request.user.is_authenticated:
            return False

        # Check trust level (new users cannot create threads)
        try:
            profile = request.user.forum_profile
            # Allow all trust levels except 'new'
            return profile.trust_level != 'new'
        except AttributeError:
            # No forum profile exists, deny permission
            # Note: Forum profiles should be created via signals when user is created
            return False
