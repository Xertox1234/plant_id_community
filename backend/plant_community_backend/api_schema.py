"""
drf-spectacular schema customization hooks.

This module provides preprocessing hooks for customizing the OpenAPI schema generation.
"""


def preprocess_exclude_wagtail(endpoints):
    """
    Exclude Wagtail API endpoints from the schema.

    Wagtail API endpoints use a different versioning scheme and can cause
    conflicts with DRF's NamespaceVersioning. This hook filters them out.

    We only include /api/v1/* endpoints in the OpenAPI schema since:
    - Wagtail API (/api/v2/*) uses its own schema system
    - Non-versioned auth endpoints (/api/auth/*) are duplicates of /api/v1/auth/*
    - OAuth endpoints (/accounts/*) are handled by allauth

    Args:
        endpoints: List of (path, path_regex, method, callback) tuples

    Returns:
        Filtered list of endpoints containing only DRF v1 API endpoints
    """
    # Only include /api/v1/ endpoints and schema/docs endpoints
    # This excludes Wagtail API v2, non-versioned auth, and other non-DRF endpoints
    filtered = []
    for path, path_regex, method, callback in endpoints:
        # Include only these endpoints:
        # - /api/v1/* (our versioned DRF API)
        # - /api/schema/ (schema endpoint)
        # - /api/docs/ and /api/redoc/ (documentation endpoints)
        if (path.startswith('/api/v1/') or
            path.startswith('/api/schema/') or
            path.startswith('/api/docs/') or
            path.startswith('/api/redoc/')):
            filtered.append((path, path_regex, method, callback))

    return filtered
