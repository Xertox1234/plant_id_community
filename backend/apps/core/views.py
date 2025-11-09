"""
Core views for the application.

Includes CSRF token endpoint for SPA integration.
"""

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def csrf_token_view(request):
    """
    Provide CSRF token for JavaScript applications (Issue #144 fix).

    This endpoint allows SPAs to retrieve the CSRF token securely
    without reading it directly from the cookie (which would require
    CSRF_COOKIE_HTTPONLY = False).

    Usage in React:
    ```typescript
    const response = await fetch('/api/csrf/');
    const { csrfToken } = await response.json();
    // Use csrfToken in X-CSRFToken header
    ```

    Returns:
        JsonResponse: {"csrfToken": "abc123..."}
    """
    return JsonResponse({'csrfToken': get_token(request)})
