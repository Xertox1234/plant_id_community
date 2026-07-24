"""Reference DRF exception handler producing the forum API's error envelope.

The forum API deliberately raises only DRF ``APIException`` subclasses (see
``api/exceptions.py``) so every error path flows through one handler and returns
ONE consistent envelope. This module ships that handler as a package default, so
a host that mounts ``wagtail_forum`` gets the contract instead of bare DRF
``{"detail": ...}`` responses (audit M39).

A host registers it via::

    REST_FRAMEWORK = {
        "EXCEPTION_HANDLER": (
            "wagtail_forum.api.exception_handler.forum_exception_handler"
        ),
    }

or keeps its own compatible handler — the plant_id host uses
``apps.core.exceptions.custom_exception_handler``, which emits the identical core
envelope (plus an optional ``request_id`` when an ``X-Request-ID`` header is
present, and a 429 branch for its rate limiter). The package cannot import from
the host, so the envelope logic is duplicated here on purpose.

The core envelope shape (pinned by ``tests/api/test_error_envelope.py``)::

    {
        "error": true,
        "message": "<human-readable>",
        "code": "<machine code, e.g. conflict / unprocessable / not_found>",
        "status_code": <int>,
        "errors": {"<field>": ["<str>", ...]}   # only on validation failures
    }
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("wagtail_forum")


def _envelope(message, code, status_code, errors=None):
    data = {
        "error": True,
        "message": message,
        "code": code,
        "status_code": status_code,
    }
    if errors is not None:
        data["errors"] = errors
    return data


def _normalize_errors(detail):
    """Map a DRF exception's ``.detail`` to the envelope's ``errors`` field.

    Dict → as-is; list → ``non_field_errors``; scalar → ``detail`` — mirrors the
    host handler so the two are interchangeable.
    """
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, list):
        return {"non_field_errors": detail}
    if detail is not None:
        return {"detail": str(detail)}
    return None


def forum_exception_handler(exc, context):
    """Return the forum's consistent error envelope for any API exception."""
    response = drf_exception_handler(exc, context)

    # DRF-handled exceptions (APIException + subclasses: Conflict 409,
    # UnprocessableEntity 422, ValidationError 400, NotFound 404, …).
    if response is not None:
        response.data = _envelope(
            message=str(exc),
            code=getattr(exc, "default_code", "error"),
            status_code=response.status_code,
            errors=_normalize_errors(getattr(exc, "detail", None)),
        )
        return response

    # Non-DRF exceptions: mirror the host so a standalone host still gets the
    # envelope instead of Django's default HTML error page. NOTE: under DRF's
    # default dispatch the Http404/PermissionDenied branches below are defensive —
    # `drf_exception_handler` already converts those two to APIExceptions and
    # returns above, so a package `get_object_or_404` 404 flows through the
    # DRF-handled branch (message="No <Model> matches...", code="error"),
    # byte-identical to the host handler (audit M39: one shape, host-consistent).
    # They only fire if a host's DRF config does not convert them first.
    if isinstance(exc, Http404):
        code, status_code, message = (
            "not_found",
            http_status.HTTP_404_NOT_FOUND,
            ("Resource not found"),
        )
    elif isinstance(exc, DjangoPermissionDenied):
        code, status_code, message = (
            "permission_denied",
            http_status.HTTP_403_FORBIDDEN,
            "Permission denied",
        )
    elif isinstance(exc, DjangoValidationError):
        return Response(
            _envelope(
                "Validation error",
                "validation_error",
                http_status.HTTP_400_BAD_REQUEST,
                errors=getattr(exc, "message_dict", None),
            ),
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    else:
        logger.error(
            "[ERROR] Unhandled forum API exception: %s",
            exc.__class__.__name__,
            exc_info=True,
        )
        code, status_code, message = (
            "internal_error",
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred",
        )

    return Response(_envelope(message, code, status_code), status=status_code)
