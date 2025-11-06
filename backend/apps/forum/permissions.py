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


class CanUploadImages(permissions.BasePermission):
    """
    Require minimum trust level to upload images.

    Phase 6.1: Trust Level Service - ViewSet Integration
    Prevents NEW users from uploading images (trust level too low).

    Trust level requirements:
    - NEW users: CANNOT upload images (can_upload_images=False)
    - BASIC+ users (basic, trusted, veteran, expert): CAN upload images
    - Staff/superuser: Always allowed (bypass)

    This prevents abuse from new accounts while allowing established members
    to share images freely.

    Permissions:
    - POST (upload): Requires trust_level != 'new' OR staff
    - Other methods: Allowed

    Usage:
        Apply to PostViewSet.upload_image action only.

    Example:
        >>> @action(detail=True, methods=['POST'], permission_classes=[CanUploadImages])
        >>> def upload_image(self, request, pk=None):
        >>>     ...

    Error Response (403 Forbidden):
        {
            "detail": "Image uploads require BASIC trust level or higher. You are currently NEW. "
                     "Requirements for BASIC: 7 days active, 5 posts. Your progress: 2 days, 1 posts."
        }
    """

    message = "Image uploads require BASIC trust level or higher."

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Check if user can upload images based on trust level.

        Args:
            request: Django request object
            view: ViewSet instance

        Returns:
            True if user can upload images, False otherwise
        """
        # Allow all non-POST requests (should not be reached for upload_image, but defensive)
        if request.method != 'POST':
            return True

        # Require authenticated user
        if not request.user.is_authenticated:
            self.message = "Authentication required to upload images."
            return False

        # Import TrustLevelService here to avoid circular imports
        from .services.trust_level_service import TrustLevelService
        from .constants import TRUST_LEVEL_NEW, TRUST_LEVEL_BASIC, TRUST_LEVEL_REQUIREMENTS

        # Staff/superuser always allowed
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check permission via TrustLevelService
        if TrustLevelService.can_perform_action(request.user, 'can_upload_images'):
            return True

        # Permission denied - generate helpful error message
        try:
            trust_level = TrustLevelService.get_user_trust_level(request.user)
            info = TrustLevelService.get_trust_level_info(request.user)

            # Calculate progression requirements
            basic_req = TRUST_LEVEL_REQUIREMENTS[TRUST_LEVEL_BASIC]
            required_days = basic_req['days']
            required_posts = basic_req['posts']

            # Get current progress from progress_to_next if it exists
            if info.get('progress_to_next'):
                current_days = info['progress_to_next']['current_days']
                current_posts = info['progress_to_next']['current_posts']
            else:
                # If no progress_to_next (e.g., EXPERT level), calculate directly
                from django.utils import timezone
                current_days = (timezone.now() - request.user.date_joined).days
                current_posts = request.user.forum_posts.filter(is_active=True).count() if hasattr(request.user, 'forum_posts') else 0

            self.message = (
                f"Image uploads require BASIC trust level or higher. "
                f"You are currently {trust_level.upper()}. "
                f"Requirements for BASIC: {required_days} days active, {required_posts} posts. "
                f"Your progress: {current_days} days, {current_posts} posts."
            )
        except Exception:
            # Fallback to generic message if trust level info cannot be retrieved
            self.message = "Image uploads require BASIC trust level or higher."

        return False
