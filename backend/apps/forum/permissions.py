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


class IsAuthorOrModerator(permissions.BasePermission):
    """
    Allow authors to edit their own content OR moderators to edit any content.

    Combines IsAuthorOrReadOnly and IsModerator with OR logic.
    This is the correct pattern for "author OR moderator" permissions.

    Permissions:
    - Read (GET, HEAD, OPTIONS): Anyone
    - Write (POST, PUT, PATCH, DELETE): Author OR Moderator

    Usage:
        Apply to ThreadViewSet and PostViewSet for update/delete actions.
        Replaces the incorrect pattern of returning multiple permissions.

    Example:
        >>> # WRONG (AND logic - both must pass):
        >>> return [IsAuthorOrReadOnly(), IsModerator()]

        >>> # CORRECT (OR logic - either can pass):
        >>> return [IsAuthorOrModerator()]
    """

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        """
        Check if user is author OR moderator.

        Args:
            request: Django request object
            view: ViewSet instance
            obj: Object being accessed (Thread or Post)

        Returns:
            True if user is author or moderator, False otherwise
        """
        # Read permissions (GET, HEAD, OPTIONS) allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions for author OR moderator

        # Check if user is the author
        if obj.author == request.user:
            return True  # Author can edit their own content

        # Check if user is a moderator (staff or in Moderators group)
        if request.user.is_authenticated and (
            request.user.is_staff or
            request.user.groups.filter(name='Moderators').exists()
        ):
            return True  # Moderator can edit any content

        # Neither author nor moderator
        return False


class IsModeratorOrStaff(permissions.BasePermission):
    """
    Restrict access to moderation features to staff and moderators only.

    Phase 4.2: Content Moderation Queue
    Used for ModerationQueueViewSet and moderation-only endpoints.

    Moderators are identified by:
    - is_staff=True (Django admin staff)
    - is_superuser=True (Superusers)
    - Membership in 'Moderators' group

    Permissions:
    - Moderators/Staff: Full access to moderation queue
    - Regular users: Denied

    Usage:
        Apply to ModerationQueueViewSet for all actions.

    Example:
        >>> permission_classes = [IsModeratorOrStaff]
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Check if user has moderation permissions.

        Args:
            request: Django request object
            view: ViewSet instance

        Returns:
            True if user is staff/superuser or in Moderators group, False otherwise
        """
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return False

        # Check if user is staff, superuser, or in Moderators group
        return (
            request.user.is_staff or
            request.user.is_superuser or
            request.user.groups.filter(name='Moderators').exists()
        )

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        """
        Check if user has moderation permissions for specific object.

        Args:
            request: Django request object
            view: ViewSet instance
            obj: Object being accessed

        Returns:
            True if user has moderation permissions, False otherwise
        """
        # Same logic as has_permission
        return self.has_permission(request, view)
