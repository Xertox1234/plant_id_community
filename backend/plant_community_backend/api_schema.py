"""
drf-spectacular schema customization hooks.

This module provides preprocessing hooks for customizing the OpenAPI schema generation.
"""

import copy
import re
import threading

from django.conf import settings


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

# One OpenAPI 429 response, deep-copied per operation (below) so a later per-op
# schema tweak can't mutate every throttled endpoint at once.
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

# Throttled (schema_path, method) pairs, recorded by the preprocessing hook and
# read by the postprocessing hook. Thread-LOCAL, not a module global:
# SpectacularAPIView regenerates the schema per request, so concurrent generations
# on different threads must not share this — a plain global would race
# clear()/add() against another thread's read (missing 429s, or a "set changed
# size during iteration" 500). Pre- and post-processing for ONE generation run on
# the same thread, so thread-local isolation is both correct and sufficient.
_state = threading.local()


def _trim_schema_prefix(path):
    """Strip SCHEMA_PATH_PREFIX (when TRIM is on) so recorded paths match the
    trimmed keys in the generated schema's ``paths`` — derived from the SAME
    settings drf-spectacular uses, so the two cannot drift on a version bump."""
    spec = settings.SPECTACULAR_SETTINGS
    prefix = spec.get("SCHEMA_PATH_PREFIX") or ""
    if not (prefix and spec.get("SCHEMA_PATH_PREFIX_TRIM")):
        return path
    return re.sub("^" + prefix, "", path)


def record_throttled_operations(endpoints):
    """Preprocessing hook: record every (schema_path, method) whose MOUNTED view
    is rate-limited.

    The forum_host wrappers set ``_forum_throttled_methods`` (a set of HTTP
    methods) on themselves; this reads the class off each endpoint's callback and
    notes the throttled operations so ``document_throttle_429`` can add a 429.
    Returns ``endpoints`` unchanged.
    """
    throttled_ops = set()
    for path, path_regex, method, callback in endpoints:
        # DRF's as_view() sets `.cls`; Django's plain views set `.view_class`.
        view = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        throttled = getattr(view, "_forum_throttled_methods", ()) if view else ()
        if method.upper() in throttled:
            throttled_ops.add((_trim_schema_prefix(path), method.lower()))
    _state.throttled_operations = throttled_ops
    return endpoints


def document_throttle_429(result, generator, request, public):
    """Postprocessing hook: add a 429 response to every rate-limited operation
    recorded by :func:`record_throttled_operations`."""
    paths = result.get("paths", {})
    for path, method in getattr(_state, "throttled_operations", set()):
        operation = paths.get(path, {}).get(method)
        if operation is not None:
            operation.setdefault("responses", {}).setdefault(
                "429", copy.deepcopy(RATE_LIMIT_429_RESPONSE)
            )
    return result
