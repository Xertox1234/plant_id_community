"""
drf-spectacular schema customization hooks.

This module provides preprocessing hooks for customizing the OpenAPI schema generation.
"""

import re


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
        if (
            path.startswith("/api/v1/")
            or path.startswith("/api/schema/")
            or path.startswith("/api/docs/")
            or path.startswith("/api/redoc/")
        ):
            filtered.append((path, path_regex, method, callback))

    return filtered


# --- Rate-limit (429) documentation (todo 254) ------------------------------
# Host forum views are throttled with django-ratelimit, which drf-spectacular
# cannot see (no DRF throttle_classes). The forum_host wrappers flag each
# throttled HTTP method on `_forum_throttled_methods`; the preprocessing hook
# records the resulting (path, method) pairs and the postprocessing hook injects
# a 429 there — and only there, so unthrottled GETs stay clean. A new throttled
# wrapper is documented automatically ("survives new wrappers").

# One OpenAPI response object reused for every rate-limited operation.
RATE_LIMIT_429_RESPONSE = {
    "description": (
        "Rate limit exceeded. Retry after the window given in the Retry-After "
        "header."
    ),
    "headers": {
        "Retry-After": {
            "description": "Seconds to wait before retrying.",
            "schema": {"type": "integer"},
        }
    },
}

# Filled by record_throttled_operations (preprocessing) and read by
# document_throttle_429 (postprocessing) within a single schema generation. Keyed
# by the SCHEMA path — SCHEMA_PATH_PREFIX_TRIM strips the /api/v1 prefix, so we
# strip it here too to match the postprocessing result's `paths` keys.
_THROTTLED_OPERATIONS = set()

_SCHEMA_PATH_PREFIX = re.compile(r"^/api/v[0-9]")


def record_throttled_operations(endpoints):
    """Preprocessing hook: record every (schema_path, method) whose MOUNTED view
    is rate-limited.

    The forum_host wrappers set ``_forum_throttled_methods`` (a set of HTTP
    methods) on themselves; this reads the class off each endpoint's callback and
    notes the throttled operations so ``document_throttle_429`` can add a 429.
    Returns ``endpoints`` unchanged.
    """
    _THROTTLED_OPERATIONS.clear()
    for path, path_regex, method, callback in endpoints:
        # DRF's as_view() sets `.cls`; Django's plain views set `.view_class`.
        view = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        throttled = getattr(view, "_forum_throttled_methods", ()) if view else ()
        if method.upper() in throttled:
            _THROTTLED_OPERATIONS.add(
                (_SCHEMA_PATH_PREFIX.sub("", path), method.lower())
            )
    return endpoints


def document_throttle_429(result, generator, request, public):
    """Postprocessing hook: add a 429 response to every rate-limited operation
    recorded by :func:`record_throttled_operations`."""
    paths = result.get("paths", {})
    for path, method in _THROTTLED_OPERATIONS:
        operation = paths.get(path, {}).get(method)
        if operation is not None:
            operation.setdefault("responses", {}).setdefault(
                "429", RATE_LIMIT_429_RESPONSE
            )
    return result
