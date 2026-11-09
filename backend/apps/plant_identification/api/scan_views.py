"""Scan 2.0 job API (B4): allowance, create, status, cancel and the photo stream.

All endpoints need a signed-in user and only ever see that user's jobs: the
queryset is filtered by owner, so another user's job or photo is a 404.

Create runs under a row lock on the user, so two simultaneous creates are
serialized: the second sees the first's active job (409) or its spent slot
(429), never a second free slot.
"""

from __future__ import annotations

import logging
import uuid as uuid_module
from datetime import timedelta
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
    SCAN_DECISION_WINDOW_HOURS,
    SCAN_FAILURE_ENQUEUE,
    SCAN_MAX_PHOTO_BYTES,
    SCAN_MODE_CHOICES,
    SCAN_MODE_ROLES,
    SCAN_PHOTO_CACHE_CONTROL,
    SCAN_REQUIRED_ROLE,
)
from ..scan_jobs import (
    allowance_for,
    delete_scan_photos,
    erase_scan,
    expire_stale_jobs,
    local_date_for,
    parse_utc_offset,
    resets_at_for,
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
            help_text=(
                "When the next diagnosis comes back, in UTC: a scan counts "
                "for 24 hours after it was made (a rolling window, not a "
                "calendar day)."
            )
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
ERROR_NOT_UNDECIDED = _error_schema(
    "ScanNotUndecidedError",
    "not_undecided: the scan is not waiting for a decision (or has not finished).",
)
ERROR_DECISION_CONFLICT = _error_schema(
    "ScanDecisionConflictError",
    "not_finished: the scan is still running. already_kept: a kept scan can "
    "only be removed, not dismissed.",
)
ERROR_CREATE_429 = _error_schema(
    "ScanCreateLimitError",
    "allowance_exhausted: no scans of this kind left in the last 24 hours "
    "(kind, limit and resets_at, when this kind's next scan comes back, are "
    "set). rate_limit_exceeded: too many requests; the "
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
    description=(
        "Minutes east of UTC (-840..840); absent or invalid means UTC. "
        "Recorded on the job; it does not move the allowance window."
    ),
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
        try:
            validate_image_file(upload)
        except ValidationError as exc:
            # Keyed by role like every other photo error, so the client can
            # tell which photo failed (scan-2 audit L4).
            raise ValidationError({role: exc.detail}) from None
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
        jobs = ScanJob.objects.filter(user=self.request.user)
        # Erased scans are gone to the client (404) except where dismiss and
        # remove answer them as an idempotent 204.
        if self.action not in ("dismiss", "remove"):
            jobs = jobs.exclude(decision__in=ScanJob.ERASED_DECISIONS)
        return jobs.prefetch_related("images")

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
        """The signed-in user's scan allowance over the last 24 hours."""
        offset = request.query_params.get("utc_offset_minutes")
        return Response(allowance_for(request.user, offset))

    def _refusal(self, request: Request, user, mode: str) -> Response | None:
        """The 409/429/503 that stops this create, or None to go ahead."""
        expire_stale_jobs(user.pk)  # a stuck job must not 409 forever
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
        allowance = allowance_for(user)
        if allowance[mode]["remaining"] <= 0:
            return _error(
                request,
                status.HTTP_429_TOO_MANY_REQUESTS,
                "allowance_exhausted",
                "No scans of this kind left for now.",
                kind=mode,
                limit=allowance[mode]["limit"],
                resets_at=resets_at_for(user, mode),
            )
        if mode == "diagnose" and not allowance["plant_id_available"]:
            return _error(
                request,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "plant_id_busy",
                "Plant health checks are busy right now. Try again later.",
            )
        return None

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
        """Start a scan. The photos are form files named by role.

        The photos are decoded and re-encoded BEFORE the user row is locked
        (scan-2 audit M5): a cheap unlocked check first refuses a user who
        would be refused anyway, so an exhausted user forces no decode, and
        the lock is held only for the authoritative re-check and the inserts.
        """
        mode = str(request.data.get("mode", ""))
        if mode not in SCAN_MODE_ROLES:
            raise ValidationError({"mode": ["Must be diagnose or identify."]})
        offset = parse_utc_offset(request.data.get("utc_offset_minutes"))
        # New clients send the header and decide each scan themselves; an old
        # build does not, so its scans stay kept and its photos are never swept.
        decision = (
            "undecided" if request.headers.get("X-Scan-Decisions") == "1" else "kept"
        )
        # retry_of is lenient on purpose: anything unusable is ignored, never a 400.
        try:
            retry_of = uuid_module.UUID(str(request.data.get("retry_of", "")))
        except ValueError:
            retry_of = None

        refused = self._refusal(request, request.user, mode)
        if refused is not None:
            return refused
        photos = _validated_photos(request, mode)

        User = get_user_model()
        written: list[str] = []
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                # Authoritative: a concurrent create may have won meanwhile.
                refused = self._refusal(request, user, mode)
                if refused is not None:
                    return refused

                job = ScanJob.objects.create(
                    user=user,
                    mode=mode,
                    local_date=local_date_for(offset),
                    utc_offset_minutes=offset,
                    decision=decision,
                )
                if retry_of is not None:
                    # Try again on a degraded scan: refund its identify charge.
                    # Inside the lock and after the refusal re-check, so a
                    # refused create refunds nothing.
                    target = ScanJob.objects.filter(
                        user=user, uuid=retry_of, status="degraded"
                    ).first()
                    if target is not None:
                        erase_scan(
                            target.pk,
                            "dismissed",
                            from_decisions=("undecided",),
                            refund=True,
                        )
                for role, photo in photos.items():
                    image = ScanJobImage.objects.create(job=job, role=role, image=photo)
                    if image.image.name:
                        written.append(image.image.name)
                job_id = job.pk
                transaction.on_commit(lambda: _enqueue_scan_job(job_id))
        except Exception:
            # The rows rolled back, but photos already written to storage did
            # not, and with no row nothing would ever delete them.
            storage = scan_photo_storage()
            for name in written:
                try:
                    storage.delete(name)
                except Exception:
                    logger.exception("[SCAN] Could not delete orphaned photo %s", name)
            raise

        logger.info("[SCAN] job=%s created mode=%s user=%s", job.pk, mode, user.pk)
        return self._job_response(job, status.HTTP_201_CREATED)

    @extend_schema(responses={200: ScanJobSerializer, 404: ERROR_NOT_FOUND})
    def retrieve(self, request: Request, uuid=None) -> Response:
        """One scan job, with its result once it has finished."""
        expire_stale_jobs(request.user.pk)
        # get_object already prefetched the images: no re-fetch (L8).
        job = self.get_object()
        return Response(
            ScanJobSerializer(job, context=self.get_serializer_context()).data
        )

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
        # One transaction: a crash between the UPDATE and the photo delete
        # must not leave a cancelled job with its photos (files go on commit).
        with transaction.atomic():
            cancelled = ScanJob.objects.filter(
                pk=job.pk, status__in=ScanJob.ACTIVE_STATUSES
            ).update(status="cancelled", finished_at=timezone.now())
            if cancelled:
                delete_scan_photos([job.pk])
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
        parameters=[
            OpenApiParameter(
                "decision",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=True,
                enum=["undecided"],
                description="Only 'undecided' is supported.",
            )
        ],
        responses={200: ScanJobSerializer(many=True), 400: ERROR_INVALID},
    )
    def list(self, request: Request) -> Response:
        """Finished scans still waiting for keep-or-dismiss, newest first."""
        if request.query_params.get("decision") != "undecided":
            return _error(
                request,
                status.HTTP_400_BAD_REQUEST,
                "invalid",
                "Pass decision=undecided.",
            )
        cutoff = timezone.now() - timedelta(hours=SCAN_DECISION_WINDOW_HOURS)
        jobs = (
            self.get_queryset()
            .filter(
                decision="undecided",
                status__in=("done", "degraded"),
                finished_at__gte=cutoff,
            )
            .order_by("-finished_at")[:50]
        )
        return Response(
            ScanJobSerializer(
                jobs, many=True, context=self.get_serializer_context()
            ).data
        )

    @extend_schema(
        request=None,
        responses={
            200: ScanJobSerializer,
            404: ERROR_NOT_FOUND,
            409: ERROR_NOT_UNDECIDED,
        },
    )
    @action(detail=True, methods=["post"])
    def keep(self, request: Request, uuid=None) -> Response:
        """Keep a finished scan. Keeping a kept scan again changes nothing."""
        job = self.get_object()
        kept = ScanJob.objects.filter(
            pk=job.pk, decision="undecided", status__in=("done", "degraded")
        ).update(decision="kept", decided_at=timezone.now())
        if not kept:
            current = ScanJob.objects.get(pk=job.pk)
            already = current.decision == "kept" and current.status in (
                "done",
                "degraded",
            )
            if not already:
                return _error(
                    request,
                    status.HTTP_409_CONFLICT,
                    "not_undecided",
                    "This scan is not waiting for a decision.",
                )
        else:
            logger.info("[SCAN] job=%s kept by user=%s", job.pk, request.user.pk)
        return self._job_response(job)

    def _erase(
        self, request: Request, job: ScanJob, decision: str, from_decisions
    ) -> Response:
        """Shared dismiss/remove body: idempotent 204 once erased."""
        erased_codes = ScanJob.ERASED_DECISIONS
        if job.decision in erased_codes:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if job.status not in ("done", "degraded"):
            return _error(
                request,
                status.HTTP_409_CONFLICT,
                "not_finished",
                "This scan has not finished yet.",
            )
        if decision == "dismissed" and job.decision == "kept":
            return self._already_kept(request)
        if erase_scan(job.pk, decision, from_decisions=from_decisions):
            logger.info(
                "[SCAN] job=%s %s by user=%s", job.pk, decision, request.user.pk
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        # Lost a race with another decision: re-read and apply the same rules.
        current = ScanJob.objects.get(pk=job.pk)
        if current.decision in erased_codes:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return self._already_kept(request)

    @staticmethod
    def _already_kept(request: Request) -> Response:
        return _error(
            request,
            status.HTTP_409_CONFLICT,
            "already_kept",
            "A kept scan can only be removed.",
        )

    @extend_schema(
        request=None,
        responses={
            204: OpenApiResponse(description="Dismissed (or already erased)."),
            404: ERROR_NOT_FOUND,
            409: ERROR_DECISION_CONFLICT,
        },
    )
    @action(detail=True, methods=["post"])
    def dismiss(self, request: Request, uuid=None) -> Response:
        """Dismiss an undecided scan: photos and result are erased, no refund."""
        return self._erase(request, self.get_object(), "dismissed", ("undecided",))

    @extend_schema(
        request=None,
        responses={
            204: OpenApiResponse(description="Removed (or already erased)."),
            404: ERROR_NOT_FOUND,
            409: ERROR_DECISION_CONFLICT,
        },
    )
    @action(detail=True, methods=["post"])
    def remove(self, request: Request, uuid=None) -> Response:
        """Remove a kept or undecided scan: photos and result are erased."""
        return self._erase(request, self.get_object(), "removed", ("kept", "undecided"))

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
        # From the prefetched images, not a second query (L8).
        image = next((i for i in job.images.all() if i.role == role), None)
        if image is None or not image.image.name:
            raise NotFound("No photo for that role.")
        try:
            handle = scan_photo_storage().open(image.image.name, "rb")
        except FileNotFoundError:
            # The row outlived its object (django-storages maps an S3 404 to
            # FileNotFoundError, as FileSystemStorage does): the documented
            # 404, not a 500. Other storage errors still surface (L1).
            logger.warning(
                "[SCAN] Photo object missing for job=%s role=%s", job.pk, role
            )
            raise NotFound("No photo for that role.") from None
        response = FileResponse(handle, content_type="image/jpeg")
        response["Cache-Control"] = SCAN_PHOTO_CACHE_CONTROL
        return response
