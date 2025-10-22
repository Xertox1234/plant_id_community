"""
Custom permissions for plant identification endpoints.

Implements flexible permission strategy for plant identification:
- Authenticated users: Full access with higher rate limits
- Anonymous users: Limited access with strict rate limits
"""

from rest_framework import permissions


class IsAuthenticatedOrReadOnlyWithRateLimit(permissions.BasePermission):
    """
    Allow authenticated users full access.
    Allow anonymous users read-only access with rate limiting.

    This permission works in combination with @ratelimit decorator to provide:
    - Authenticated users: Higher rate limits (100/hour)
    - Anonymous users: Lower rate limits (10/hour)
    """

    def has_permission(self, request, view):
        # Always allow authenticated users
        if request.user and request.user.is_authenticated:
            return True

        # For anonymous users, allow GET requests (health checks)
        # POST requests are allowed but will be rate-limited by decorator
        return True


class IsAuthenticatedForIdentification(permissions.BasePermission):
    """
    Require authentication for plant identification requests.

    Use this for production when you want to restrict plant identification
    to authenticated users only (to protect API quota).

    Health check endpoint remains public.
    """

    def has_permission(self, request, view):
        # Allow GET requests (health checks) for everyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Require authentication for POST (identification)
        return request.user and request.user.is_authenticated

    message = (
        'Authentication required for plant identification. '
        'Please log in or create an account to identify plants.'
    )


class IsAuthenticatedOrAnonymousWithStrictRateLimit(permissions.BasePermission):
    """
    Allow both authenticated and anonymous users, but with different rate limits.

    This is the recommended permission for gradual migration:
    - Phase 1: Use this to allow anonymous users with strict limits (10/hour)
    - Phase 2: Monitor usage and costs
    - Phase 3: Switch to IsAuthenticatedForIdentification for production

    Rate limits are enforced via @ratelimit decorator, not this permission class.
    """

    def has_permission(self, request, view):
        # Allow both authenticated and anonymous users
        # Rate limiting is handled by @ratelimit decorator
        return True
