"""Mobile push-device registration API (todo 621).

``POST /api/v1/push-devices/`` registers this installation's FCM token for the
caller, ``POST /api/v1/push-devices/unregister/`` removes it at sign-out. The
token is a credential: it is never logged and never echoed back.

Function views, as for the browser push endpoints in ``apps/users/views.py``,
so there is no ``get_permissions()`` to forget ``super()`` in.
"""

import logging

from django.db import IntegrityError
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from .. import ratelimit as core_ratelimit
from ..constants import (
    PUSH_DEVICE_INSTALLATION_ID_MAX_LENGTH,
    PUSH_DEVICE_PLATFORMS,
    PUSH_DEVICE_RATE_LIMIT,
    PUSH_DEVICE_TOKEN_MAX_LENGTH,
)
from ..openapi import RATE_LIMITED
from ..push_devices import register_device, unregister_device

logger = logging.getLogger(__name__)


class PushDeviceRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=PUSH_DEVICE_TOKEN_MAX_LENGTH)
    installation_id = serializers.CharField(
        max_length=PUSH_DEVICE_INSTALLATION_ID_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )
    platform = serializers.ChoiceField(
        choices=PUSH_DEVICE_PLATFORMS, required=False, allow_blank=True
    )


class PushDeviceUnregisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=PUSH_DEVICE_TOKEN_MAX_LENGTH)


_ERROR = inline_serializer("PushDeviceError", {"error": serializers.CharField()})
_REGISTERED = inline_serializer(
    "PushDeviceRegistered", {"registered": serializers.BooleanField()}
)
_REMOVED = inline_serializer(
    "PushDeviceRemoved", {"removed": serializers.IntegerField()}
)


@extend_schema(
    summary="Register this device for push notifications",
    request=PushDeviceRegisterSerializer,
    responses={
        200: _REGISTERED,
        400: _ERROR,
        409: _ERROR,
        429: RATE_LIMITED,
    },
    examples=[
        OpenApiExample(
            "iPhone",
            value={
                "token": "example-fcm-token",
                "installation_id": "00000000-0000-4000-8000-000000000000",
                "platform": "ios",
            },
            request_only=True,
        )
    ],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@core_ratelimit.ratelimit(
    key="user", rate=PUSH_DEVICE_RATE_LIMIT, method="POST", block=True
)
def register_push_device(request: Request) -> Response:
    """Register (or re-register) this installation's token for the caller.

    Idempotent. The token, and the installation, are released from any other
    row, so a shared device follows whoever signed in last and a rotated
    token replaces the old one; the caller's other devices are untouched.
    """
    serializer = PushDeviceRegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "A device token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = serializer.validated_data
    try:
        register_device(
            request.user,
            data["token"],
            installation_id=data.get("installation_id") or None,
            platform=data.get("platform") or "",
        )
    except IntegrityError:
        return Response(
            {"error": "Device registration changed concurrently; retry"},
            status=status.HTTP_409_CONFLICT,
        )
    logger.info("[PUSH] device registered (user=%s)", request.user.pk)
    return Response({"registered": True})


@extend_schema(
    summary="Remove this device's push registration",
    request=PushDeviceUnregisterSerializer,
    responses={200: _REMOVED, 400: _ERROR, 429: RATE_LIMITED},
    examples=[
        OpenApiExample(
            "Sign out",
            value={"token": "example-fcm-token"},
            request_only=True,
        )
    ],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@core_ratelimit.ratelimit(
    key="user", rate=PUSH_DEVICE_RATE_LIMIT, method="POST", block=True
)
def unregister_push_device(request: Request) -> Response:
    """Remove the caller's registration of this token, and nothing else.

    200 with ``removed: 0`` when there was none (already removed, or another
    account has since claimed the device): sign-out has nothing to retry.
    """
    serializer = PushDeviceUnregisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "A device token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    removed = unregister_device(request.user, serializer.validated_data["token"])
    logger.info(
        "[PUSH] device unregistered (user=%s, rows=%s)", request.user.pk, removed
    )
    return Response({"removed": removed})
