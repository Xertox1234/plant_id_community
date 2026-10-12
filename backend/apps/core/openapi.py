"""OpenAPI shapes shared across apps (todo 599).

``RATE_LIMITED`` documents the 429 that
``apps.core.exceptions.custom_exception_handler`` answers for every
``@ratelimit(block=True)`` view. Every such view lists it, which
``apps/core/tests/test_openapi_rate_limit_429.py`` enforces.
"""

from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers

RATE_LIMITED = OpenApiResponse(
    inline_serializer(
        "RateLimitedError",
        {
            "error": serializers.BooleanField(),
            "message": serializers.CharField(),
            "code": serializers.CharField(help_text="rate_limit_exceeded"),
            "status_code": serializers.IntegerField(),
            "request_id": serializers.CharField(required=False),
        },
    ),
    description="Rate limit exceeded. The Retry-After header gives the seconds "
    "to wait before trying again.",
)
