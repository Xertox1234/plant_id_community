"""DRF permission classes for the users app."""

from rest_framework.permissions import BasePermission


class IsPremiumUser(BasePermission):
    """Allow access only to users with premium entitlement.

    Delegates to ``User.has_premium_access()``, so staff and superusers are
    granted access implicitly. Anonymous users are always denied.
    """

    message = "This feature requires a premium account."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user.is_authenticated and user.has_premium_access())
