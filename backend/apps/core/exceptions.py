"""
Centralized exception handling for the Plant Community API.

Provides consistent error responses and logging across all API endpoints.
"""

import logging
import traceback
from typing import Any, Dict, Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django_ratelimit.exceptions import Ratelimited
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def get_request_id(request) -> Optional[str]:
    """Extract request ID from headers or request object."""
    if hasattr(request, "id"):
        return request.id
    return request.META.get("HTTP_X_REQUEST_ID")


def _retry_after_seconds(rate: Optional[str]) -> int:
    """Window length in seconds for a django-ratelimit rate string.

    Handles bare-unit windows ('30/m' -> 60) and multi-unit windows
    ('5/15m' -> 900). Falls back to one hour when the rate is unknown (e.g. a bare
    Ratelimited from a decorator that did not attach its rate — see
    apps.core.ratelimit).
    """
    # isinstance guard: django-ratelimit also accepts callable rates; parsing a
    # non-str would raise inside the exception handler (a 429 -> 500).
    if isinstance(rate, str) and "/" in rate:
        period = rate.rsplit("/", 1)[1]  # e.g. "m", "15m", "30s"
        unit_seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(period[-1:])
        if unit_seconds is not None:
            multiplier = period[:-1]
            try:
                count = int(multiplier) if multiplier else 1
            except ValueError:
                return 3600
            # A zero/negative multiplier (e.g. "5/0m") would yield Retry-After: 0,
            # telling the client to retry immediately and defeating the limit.
            # Treat it as invalid and use the same safe 1-hour fallback.
            if count <= 0:
                return 3600
            return count * unit_seconds
    return 3600


def custom_exception_handler(
    exc: Exception, context: Dict[str, Any]
) -> Optional[Response]:
    """
    Custom exception handler that logs errors with context and returns
    consistent error response format.

    Args:
        exc: The exception instance
        context: Dictionary containing request and view information

    Returns:
        Response object with standardized error format
    """
    # Handle Ratelimited exception before DRF processing
    # Ratelimited inherits from PermissionDenied, which DRF converts to 403
    # We need to return 429 instead
    if isinstance(exc, Ratelimited):
        request = context.get("request")
        view = context.get("view")
        request_id = get_request_id(request) if request else None

        log_context = {
            "request_id": request_id,
            "path": request.path if request else None,
            "method": request.method if request else None,
            "user": (
                str(request.user)
                if request and hasattr(request, "user")
                else "anonymous"
            ),
            "view": view.__class__.__name__ if view else None,
            "exception_type": "Ratelimited",
            "exception_message": str(exc),
        }

        logger.warning("429 Rate Limit Exceeded", extra=log_context)

        error_data = {
            "error": True,
            "message": "Rate limit exceeded. Please try again later.",
            "code": "rate_limit_exceeded",
            "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        }

        if request_id:
            error_data["request_id"] = request_id

        # Create response with Retry-After header
        response = Response(error_data, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Retry-After derived from the actual rate window (e.g. 30/m -> 60s),
        # not a hardcoded hour; falls back to 1h when the rate is unknown
        # (todo 115). apps.core.ratelimit attaches `.rate` to the exception.
        response["Retry-After"] = str(_retry_after_seconds(getattr(exc, "rate", None)))

        return response

    # Call REST framework's default exception handler first
    response = drf_exception_handler(exc, context)

    # Extract context information
    request = context.get("request")
    view = context.get("view")
    request_id = get_request_id(request) if request else None

    # Build logging context
    log_context = {
        "request_id": request_id,
        "path": request.path if request else None,
        "method": request.method if request else None,
        "user": (
            str(request.user) if request and hasattr(request, "user") else "anonymous"
        ),
        "view": view.__class__.__name__ if view else None,
        "exception_type": exc.__class__.__name__,
        "exception_message": str(exc),
    }

    # If DRF handled it, enhance the response
    if response is not None:
        # Log the exception with context
        if response.status_code >= 500:
            logger.error(
                f"API error: {exc.__class__.__name__}", extra=log_context, exc_info=True
            )
        else:
            logger.warning(
                f"API client error: {exc.__class__.__name__}", extra=log_context
            )

        # Standardize the response format
        error_data = {
            "error": True,
            "message": str(exc),
            "code": getattr(exc, "default_code", "error"),
            "status_code": response.status_code,
        }

        # Add request ID if available
        if request_id:
            error_data["request_id"] = request_id

        # Add field errors for validation exceptions
        if hasattr(exc, "detail"):
            if isinstance(exc.detail, dict):
                error_data["errors"] = exc.detail
            elif isinstance(exc.detail, list):
                error_data["errors"] = {"non_field_errors": exc.detail}
            else:
                error_data["errors"] = {"detail": str(exc.detail)}

        response.data = error_data
        return response

    # Handle non-DRF exceptions
    error_message = "An unexpected error occurred"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "internal_error"

    # Handle specific Django exceptions
    # IMPORTANT: Check Ratelimited before PermissionDenied since Ratelimited inherits from PermissionDenied
    if isinstance(exc, Ratelimited):
        error_message = "Rate limit exceeded. Please try again later."
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        error_code = "rate_limit_exceeded"
        logger.warning("429 Rate Limit Exceeded", extra=log_context)

    elif isinstance(exc, Http404):
        error_message = "Resource not found"
        status_code = status.HTTP_404_NOT_FOUND
        error_code = "not_found"
        logger.warning("404 Not Found", extra=log_context)

    elif isinstance(exc, PermissionDenied):
        error_message = "Permission denied"
        status_code = status.HTTP_403_FORBIDDEN
        error_code = "permission_denied"
        logger.warning("403 Forbidden", extra=log_context)

    elif isinstance(exc, ValidationError):
        error_message = "Validation error"
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "validation_error"
        logger.warning("Validation error", extra=log_context)

    else:
        # Log unexpected errors with full traceback
        logger.error(
            f"Unhandled exception: {exc.__class__.__name__}",
            extra={**log_context, "traceback": traceback.format_exc()},
            exc_info=True,
        )

    # Build error response
    error_data = {
        "error": True,
        "message": error_message,
        "code": error_code,
        "status_code": status_code,
    }

    # Add request ID if available
    if request_id:
        error_data["request_id"] = request_id

    # Add validation error details
    if isinstance(exc, ValidationError) and hasattr(exc, "message_dict"):
        error_data["errors"] = exc.message_dict

    return Response(error_data, status=status_code)


class PlantCommunityAPIException(APIException):
    """Base exception class for Plant Community API."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "A server error occurred."
    default_code = "error"

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail, code)


class ExternalAPIError(PlantCommunityAPIException):
    """Exception raised when external API calls fail."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "External service is temporarily unavailable."
    default_code = "external_api_error"


class RateLimitExceeded(PlantCommunityAPIException):
    """Exception raised when rate limit is exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded. Please try again later."
    default_code = "rate_limit_exceeded"


class InvalidImageError(PlantCommunityAPIException):
    """Exception raised for invalid image uploads."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid image file."
    default_code = "invalid_image"
