"""Scan 2.0 job API (B4): allowance, create, status, cancel and the photo stream.

All endpoints need a signed-in user and only ever see that user's jobs: the
queryset is filtered by owner, so another user's job or photo is a 404.

Create runs under a row lock on the user, so two simultaneous creates are
serialized: the second sees the first's active job (409) or its spent slot
(429), never a second free slot.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from apps.core.exceptions import get_request_id
from apps.core.ratelimit import ratelimit
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.decorators import method_decorator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from ..constants import (
    SCAN_CREATE_RATE,
    SCAN_FAILURE_ENQUEUE,
    SCAN_MAX_PHOTO_BYTES,
    SCAN_MODE_CHOICES,
    SCAN_MODE_ROLES,
    SCAN_PHOTO_CACHE_CONTROL,
    SCAN_REQUIRED_ROLE,
)
from ..scan_jobs import (
    allowance_for,
    expire_stale_jobs,
    local_date_for,
    parse_utc_offset,
)
from ..scan_models import ScanJob, ScanJobImage
from ..scan_storage import normalize_scan_photo, scan_photo_storage
from ..tasks import run_scan_job
from ..utils import validate_image_file
from .scan_serializers import SCAN_ROLES, ScanJobCreateSerializer, ScanJobSerializer

logger = logging.getLogger(__name__)


_LIMIT_FIELDS = {
    "limit": serializers.IntegerField(),
    "used": serializers.IntegerField(),
    "remaining": serializers.IntegerField(),
}
ALLOWANCE_KIND_SCHEMA = inline_serializer("ScanAllowanceKind", _LIMIT_FIELDS)


ALLOWANCE_SCHEMA = inline_serializer(
    "ScanAllowance",
    {
        "is_premium": serializers.BooleanField(),
        "diagnose": ALLOWANCE_KIND_SCHEMA,
        "identify": ALLOWANCE_KIND_SCHEMA,
        "resets_at": serializers.DateTimeField(
            help_text="The next local midnight, in UTC."
        ),
        "plant_id_available": serializers.BooleanField(
            help_text="False when Plant.id has no room for a diagnosis right now."
        ),
        "slow_after_seconds": serializers.IntegerField(),
        "premium_diagnose_limit": serializers.IntegerField(),
    },
)


def _error_schema(name: str, codes: str, **extra: serializers.Field):
    return OpenApiResponse(
        inline_serializer(
            name,
            {
                "error": serializers.BooleanField(),
                "message": serializers.CharField(),
                "code": serializers.CharField(help_text=codes),
                "status_code": serializers.IntegerField(),
                "request_id": serializers.CharField(required=False),
                **extra,
            },
        ),
        description=codes,
    )


ERROR_INVALID = _error_schema(
    "ScanInvalidError",
    "invalid",
    errors=serializers.DictField(required=False),
)
ERROR_NOT_FOUND = _error_schema("ScanNotFoundError", "not_found")
ERROR_IN_PROGRESS = _error_schema(
    "ScanInProgressError",
    "scan_in_progress: another scan is still running.",
    job_id=serializers.UUIDField(),
)
ERROR_NOT_ACTIVE = _error_schema(
    "ScanNotActiveError", "not_active: the job has already finished."
)
ERROR_CREATE_429 = _error_schema(
    "ScanCreateLimitError",
    "allowance_exhausted: no scans of this kind left today (kind, limit and "
    "resets_at are set). rate_limit_exceeded: too many requests; the "
    "Retry-After header gives the seconds to wait.",
    kind=serializers.ChoiceField(choices=SCAN_MODE_CHOICES, required=False),
    limit=serializers.IntegerField(required=False),
    resets_at=serializers.DateTimeField(required=False),
)
ERROR_BUSY = _error_schema(
    "ScanPlantIdBusyError",
    "plant_id_busy: diagnoses are paused for now; identification still works.",
)

UTC_OFFSET_PARAM = OpenApiParameter(
    "utc_offset_minutes",
    OpenApiTypes.INT,
    OpenApiParameter.QUERY,
    required=False,
    description="Minutes east of UTC (-840..840); absent or invalid means UTC.",
)
ROLE_PARAM = OpenApiParameter(
    "role", OpenApiTypes.STR, OpenApiParameter.PATH, enum=list(SCAN_ROLES)
)


def _error(
    request: Request, status_code: int, code: str, message: str, **extra: Any
) -> Response:
    """The standard error envelope, plus fields the client acts on."""
    body: Dict[str, Any] = {
        "error": True,
        "message": message,
        "code": code,
        "status_code": status_code,
        **extra,
    }
    request_id = get_request_id(request)
    if request_id:
        body["request_id"] = request_id
    return Response(body, status=status_code)


def _validated_photos(request: Request, mode: str) -> Dict[str, Any]:
    """Each uploaded photo by role, re-encoded; raises ValidationError (400)."""
    if mode not in SCAN_MODE_ROLES:
        raise ValidationError({"mode": ["Must be diagnose or identify."]})
    allowed = SCAN_MODE_ROLES[mode]
    files = request.FILES
    unknown = sorted(name for name in files if name not in allowed)
    if unknown:
        raise ValidationError(
            {"photos": [f"Photo roles not allowed for {mode}: {', '.join(unknown)}."]}
        )
    required = SCAN_REQUIRED_ROLE[mode]
    if required not in files:
        raise ValidationError({required: [f"A {required} photo is required."]})
    photos: Dict[str, Any] = {}
    for role in allowed:
        upload = files.get(role)
        if upload is None:
            continue
        if upload.size > SCAN_MAX_PHOTO_BYTES:
            raise ValidationError({role: ["Photo too large: the maximum is 10 MB."]})
        validate_image_file(upload)
        upload.seek(0)
        try:
            photos[role] = normalize_scan_photo(upload)
        except ValueError:
            raise ValidationError({role: ["Not a readable image."]}) from None
    return photos


def _enqueue_scan_job(job_id: int) -> None:
    """on_commit callback: start the job, or fail it if the broker refuses.

    Never raises. A refused enqueue would otherwise leave a committed
    ``pending`` job that nothing runs, and every retry would 409 against it
    until the stale expiry. Failing it frees the slot at once, free of charge.
    """
    try:
        run_scan_job.delay(job_id)
    except Exception as exc:
        logger.error(
            "[SCAN] Could not enqueue job=%s, failing it: %s",
            job_id,
            type(exc).__name__,
        )
        try:
            ScanJob.objects.filter(pk=job_id, status="pending").update(
                status="failed",
                failure_reason=SCAN_FAILURE_ENQUEUE,
                finished_at=timezone.now(),
            )
        except Exception:
            # The stale expiry frees the slot later.
            logger.exception("[SCAN] Could not fail unenqueued job=%s", job_id)


class AnyAcceptNegotiation(BaseContentNegotiation):
    """Never 406: always the first renderer (JSON).

    The photo action answers with a ``FileResponse``, which DRF does not
    render, so its Accept header only matters for an error body. Default
    negotiation runs before the handler and would refuse ``Accept: image/*``
    (what image loaders send) with a 406; this picks JSON for errors instead.
    """

    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class ScanJobViewSet(GenericViewSet):
    """Background multi-photo scans with a per-user daily allowance."""

    # Actions under @method_decorator(ratelimit(...)): the OpenAPI hook
    # documents their 429 (plant_community_backend.api_schema).
    _throttled_actions = frozenset({"create"})

    queryset = ScanJob.objects.none()
    serializer_class = ScanJobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_value_regex = "[0-9a-f-]{36}"

    def get_permissions(self):
        # super() keeps any @action-level permission_classes (CLAUDE.md gotcha 1).
        return super().get_permissions()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ScanJob.objects.none()
        return ScanJob.objects.filter(user=self.request.user).prefetch_related("images")

    def get_object(self) -> ScanJob:
        # A missing job and another user's job raise the same DRF NotFound,
        # so both answer the documented ``code: "not_found"`` with one body.
        try:
            job: ScanJob = super().get_object()
        except Http404:
            raise NotFound("Scan not found.") from None
        return job

    def _job_response(self, job: ScanJob, status_code: int = 200) -> Response:
        job = self.get_queryset().get(pk=job.pk)
        data = ScanJobSerializer(job, context=self.get_serializer_context()).data
        return Response(data, status=status_code)

    @extend_schema(
        parameters=[UTC_OFFSET_PARAM],
        responses={200: ALLOWANCE_SCHEMA},
    )
    @action(detail=False, methods=["get"])
    def allowance(self, request: Request) -> Response:
        """Today's scan allowance for the signed-in user."""
        offset = request.query_params.get("utc_offset_minutes")
        return Response(allowance_for(request.user, offset))

    @extend_schema(
        request={"multipart/form-data": ScanJobCreateSerializer},
        responses={
            201: ScanJobSerializer,
            400: ERROR_INVALID,
            409: ERROR_IN_PROGRESS,
            429: ERROR_CREATE_429,
            503: ERROR_BUSY,
        },
        examples=[
            OpenApiExample(
                "Diagnose with two photos",
                value={
                    "mode": "diagnose",
                    "utc_offset_minutes": -300,
                    "problem": "example-spotted-leaf.jpg",
                    "leaf": "example-monstera-leaf.jpg",
                },
                description="Attach each photo as a file part named by its role.",
                request_only=True,
                media_type="multipart/form-data",
            )
        ],
    )
    @method_decorator(
        ratelimit(
            group="plant_identification.scan_create",
            key="user",
            rate=SCAN_CREATE_RATE,
            method="POST",
            block=True,
        )
    )
    def create(self, request: Request) -> Response:
        """Start a scan. The photos are form files named by role."""
        mode = str(request.data.get("mode", ""))
        offset = parse_utc_offset(request.data.get("utc_offset_minutes"))
        User = get_user_model()
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            expire_stale_jobs(user.pk)

            active = (
                ScanJob.objects.filter(user=user, status__in=ScanJob.ACTIVE_STATUSES)
                .order_by("-created_at")
                .first()
            )
            if active is not None:
                return _error(
                    request,
                    status.HTTP_409_CONFLICT,
                    "scan_in_progress",
                    "Another scan is still running.",
                    job_id=str(active.uuid),
                )

            photos = _validated_photos(request, mode)

            allowance = allowance_for(user, offset)
            if allowance[mode]["remaining"] <= 0:
                return _error(
                    request,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "allowance_exhausted",
                    "No scans of this kind left today.",
                    kind=mode,
                    limit=allowance[mode]["limit"],
                    resets_at=allowance["resets_at"],
                )

            if mode == "diagnose" and not allowance["plant_id_available"]:
                return _error(
                    request,
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "plant_id_busy",
                    "Plant health checks are busy right now. Try again later.",
                )

            job = ScanJob.objects.create(
                user=user,
                mode=mode,
                local_date=local_date_for(offset),
                utc_offset_minutes=offset,
            )
            for role, photo in photos.items():
                ScanJobImage.objects.create(job=job, role=role, image=photo)
            job_id = job.pk
            transaction.on_commit(lambda: _enqueue_scan_job(job_id))

        logger.info("[SCAN] job=%s created mode=%s user=%s", job.pk, mode, user.pk)
        return self._job_response(job, status.HTTP_201_CREATED)

    @extend_schema(responses={200: ScanJobSerializer, 404: ERROR_NOT_FOUND})
    def retrieve(self, request: Request, uuid=None) -> Response:
        """One scan job, with its result once it has finished."""
        expire_stale_jobs(request.user.pk)
        return self._job_response(self.get_object())

    @extend_schema(
        request=None,
        responses={
            200: ScanJobSerializer,
            404: ERROR_NOT_FOUND,
            409: ERROR_NOT_ACTIVE,
        },
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, uuid=None) -> Response:
        """Cancel a scan that is still running. A cancelled scan costs nothing."""
        job = self.get_object()
        cancelled = ScanJob.objects.filter(
            pk=job.pk, status__in=ScanJob.ACTIVE_STATUSES
        ).update(status="cancelled", finished_at=timezone.now())
        if not cancelled:
            return _error(
                request,
                status.HTTP_409_CONFLICT,
                "not_active",
                "This scan has already finished.",
            )
        logger.info("[SCAN] job=%s cancelled by user=%s", job.pk, request.user.pk)
        return self._job_response(job)

    @extend_schema(
        parameters=[ROLE_PARAM],
        responses={
            (200, "image/jpeg"): OpenApiTypes.BINARY,
            404: ERROR_NOT_FOUND,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"photos/(?P<role>[a-z]+)",
        content_negotiation_class=AnyAcceptNegotiation,
    )
    def photos(self, request: Request, uuid=None, role: str = "") -> FileResponse:
        """Stream one of the job's photos. Private: never served from storage."""
        job = self.get_object()
        image = ScanJobImage.objects.filter(job=job, role=role).first()
        if image is None or not image.image.name:
            raise NotFound("No photo for that role.")
        handle = scan_photo_storage().open(image.image.name, "rb")
        response = FileResponse(handle, content_type="image/jpeg")
        response["Cache-Control"] = SCAN_PHOTO_CACHE_CONTROL
        return response
