"""Scan job outcome rules: classification, the client summary, stale expiry.

Pure functions over the combined service's result dict (Scan 2.0 B3), plus
the one conditional UPDATE that expires stuck jobs, and the per-user daily
allowance the API (B4) enforces.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .constants import (
    SCAN_ALLOWANCE_WINDOW_HOURS,
    SCAN_FAILURE_STALE,
    SCAN_SUMMARY_MAX_SUGGESTIONS,
)
from .scan_models import ScanJob, ScanJobImage
from .services.quota_manager import QuotaManager

logger = logging.getLogger(__name__)


def delete_scan_photos(job_ids: Iterable[int]) -> None:
    """Delete the photo rows of these jobs, one by one.

    Per row, never a queryset ``.delete()`` bypass: each ``post_delete`` signal
    removes its file once the surrounding transaction commits.
    """
    for img in ScanJobImage.objects.filter(job_id__in=list(job_ids)):
        img.delete()


def erase_scan(
    job_id: int,
    decision: str,
    *,
    from_decisions: Tuple[str, ...],
    refund: bool = False,
) -> bool:
    """Erase a finished scan's photos and result; the row itself stays.

    A conditional UPDATE: False when the job is not ``done``/``degraded`` or
    its decision is not in ``from_decisions`` (a concurrent decision won).
    ``status`` and ``charged_as`` are untouched unless ``refund`` clears the
    charge, because the allowance counts rows.
    """
    with transaction.atomic():
        extra: Dict[str, Any] = {"charged_as": ""} if refund else {}
        updated = ScanJob.objects.filter(
            pk=job_id,
            decision__in=from_decisions,
            status__in=("done", "degraded"),
        ).update(decision=decision, decided_at=timezone.now(), result=None, **extra)
        if not updated:
            return False
        delete_scan_photos([job_id])
    return True


def classify_scan(mode: str, results: Dict[str, Any]) -> Tuple[str, str]:
    """``(status, charged_as)`` for a finished scan.

    No plant named is a failure and costs nothing. A diagnosis whose health
    check did not run still named the plant, so it is ``degraded`` and charged
    as an identification, leaving the diagnosis unused.
    """
    if not results.get("combined_suggestions"):
        return "failed", ""
    if mode == "identify":
        return "done", "identify"
    if results.get("disease_detection_status") == "ok":
        return "done", "diagnose"
    return "degraded", "identify"


def _diagnosis(results: Dict[str, Any]) -> Dict[str, Any]:
    if results.get("disease_detection_status") != "ok":
        return {
            "state": "unavailable",
            "name": None,
            "probability": None,
            "description": None,
        }
    # plant_id_service._format_response: health_assessment is None when no
    # disease was suggested, else a dict whose is_healthy is the API's binary.
    disease = results.get("disease_detection")
    if disease is None or disease.get("is_healthy"):
        return {
            "state": "healthy",
            "name": None,
            "probability": None,
            "description": None,
        }
    return {
        "state": "found",
        "name": disease.get("disease_name"),
        "probability": disease.get("probability"),
        "description": disease.get("description"),
    }


def summarize_scan_result(
    mode: str, results: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """The client-facing result of a scan, or None when no plant was named."""
    suggestions = results.get("combined_suggestions") or []
    if not suggestions:
        return None
    top = suggestions[0]
    return {
        "plant_name": top.get("plant_name"),
        "scientific_name": top.get("scientific_name"),
        "confidence": results.get("confidence_score", top.get("probability")),
        "description": top.get("description"),
        "suggestions": [
            {
                "plant_name": s.get("plant_name"),
                "scientific_name": s.get("scientific_name"),
                "probability": s.get("probability"),
            }
            for s in suggestions[:SCAN_SUMMARY_MAX_SUGGESTIONS]
        ],
        "diagnosis": None if mode == "identify" else _diagnosis(results),
    }


def expire_stale_jobs(user_id: Optional[int] = None) -> int:
    """Fail jobs still active past ``SCAN_JOB_STALE_MINUTES``; one user's, or all.

    A conditional UPDATE: a worker that finishes later finds the job no longer
    ``processing`` and its finalize matches nothing. Each expired job gets its
    "couldn't check" push after the commit, or at once outside a transaction
    (the notify task's own claim makes a duplicate a no-op). ``None`` is the periodic sweep (scan-2 audit M2): a
    job orphaned by a dead worker is failed even if its owner never asks
    again. Returns the count.
    """
    now = timezone.now()
    cutoff = now - timedelta(minutes=settings.SCAN_JOB_STALE_MINUTES)
    stale = ScanJob.objects.filter(
        status__in=ScanJob.ACTIVE_STATUSES, created_at__lt=cutoff
    )
    if user_id is not None:
        stale = stale.filter(user_id=user_id)
    job_ids = list(stale.values_list("pk", flat=True))
    if not job_ids:
        return 0
    expired: int = ScanJob.objects.filter(
        pk__in=job_ids, status__in=ScanJob.ACTIVE_STATUSES
    ).update(status="failed", failure_reason=SCAN_FAILURE_STALE, finished_at=now)
    if expired:
        logger.warning(
            "[SCAN] Expired %s stale scan job(s) (user=%s)",
            expired,
            user_id if user_id is not None else "all",
        )
        # Local import: tasks imports this module.
        from .tasks import _enqueue_notify

        # Only the rows this UPDATE failed: one that finished between the two
        # queries already has its own push.
        for job_id in ScanJob.objects.filter(
            pk__in=job_ids, failure_reason=SCAN_FAILURE_STALE, finished_at=now
        ).values_list("pk", flat=True):
            transaction.on_commit(partial(_enqueue_notify, job_id))
        # A failed scan keeps no photos. Same row set as the pushes above.
        delete_scan_photos(
            ScanJob.objects.filter(
                pk__in=job_ids, failure_reason=SCAN_FAILURE_STALE, finished_at=now
            ).values_list("pk", flat=True)
        )
    return expired


MAX_UTC_OFFSET_MINUTES = 840  # UTC+14 / UTC-14, the widest real offsets
SCAN_KINDS = ("diagnose", "identify")


def parse_utc_offset(raw: Any) -> int:
    """The client's UTC offset in minutes, clamped to +/-840.

    Absent or non-numeric means 0 (UTC); an out-of-range number is clamped.
    """
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 0
    return max(-MAX_UTC_OFFSET_MINUTES, min(MAX_UTC_OFFSET_MINUTES, value))


def local_date_for(utc_offset_minutes: Any) -> date:
    """Today's date at ``utc_offset_minutes`` from UTC.

    Recorded on each job for reporting only; the allowance is a rolling
    window (``SCAN_ALLOWANCE_WINDOW_HOURS``) and never reads it.
    """
    offset = parse_utc_offset(utc_offset_minutes)
    return (timezone.now() + timedelta(minutes=offset)).date()


def daily_limits(user) -> Dict[str, int]:
    """This user's daily scan allowance per kind (premium vs free)."""
    if user.has_premium_access():
        return {
            "diagnose": settings.SCAN_DIAGNOSE_DAILY_PREMIUM,
            "identify": settings.SCAN_IDENTIFY_DAILY_PREMIUM,
        }
    return {
        "diagnose": settings.SCAN_DIAGNOSE_DAILY_FREE,
        "identify": settings.SCAN_IDENTIFY_DAILY_FREE,
    }


def _window() -> timedelta:
    return timedelta(hours=SCAN_ALLOWANCE_WINDOW_HOURS)


def counted_created_at(user, kind: str, now: datetime) -> List[datetime]:
    """When each scan of ``kind`` still counted against the allowance was made.

    Oldest first. A scan counts for ``SCAN_ALLOWANCE_WINDOW_HOURS`` after it
    was created. An active job reserves its mode's slot; a finished one
    counts as what it was charged as (a degraded diagnosis counts as an
    identification). Failed and cancelled jobs have no charge and cost
    nothing.
    """
    return list(
        ScanJob.objects.filter(
            Q(status__in=ScanJob.ACTIVE_STATUSES, mode=kind) | Q(charged_as=kind),
            user=user,
            created_at__gt=now - _window(),
        )
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )


def _slot_back_at(counted: List[datetime], limit: int, now: datetime) -> datetime:
    """When the next slot comes back: the scan that frees it, plus the window.

    With every slot used that is the scan whose expiry brings ``remaining``
    to 1; otherwise the oldest counted scan; ``now`` when nothing counts.
    """
    if not counted:
        return now
    return counted[min(max(0, len(counted) - limit), len(counted) - 1)] + _window()


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def allowance_for(user, utc_offset_minutes: Any = None) -> Dict[str, Any]:
    """The user's scan allowance over the rolling window.

    Expires the user's stale jobs first, so a stuck job stops reserving.
    ``utc_offset_minutes`` is accepted for compatibility and ignored: the
    window is the same at every offset (scan-2 audit M1). ``resets_at`` is
    when the next diagnosis comes back (``resets_at_for`` gives any kind's).
    """
    expire_stale_jobs(user.pk)
    now = timezone.now()
    limits = daily_limits(user)
    allowance: Dict[str, Any] = {"is_premium": bool(user.has_premium_access())}
    resets: Dict[str, str] = {}
    for kind in SCAN_KINDS:
        counted = counted_created_at(user, kind, now)
        allowance[kind] = {
            "limit": limits[kind],
            "used": len(counted),
            "remaining": max(0, limits[kind] - len(counted)),
        }
        resets[kind] = _utc_iso(_slot_back_at(counted, limits[kind], now))
    allowance.update(
        {
            "resets_at": resets["diagnose"],
            "plant_id_available": bool(QuotaManager().can_call_plant_id(calls=2)),
            "slow_after_seconds": settings.SCAN_SLOW_AFTER_SECONDS,
            "premium_diagnose_limit": settings.SCAN_DIAGNOSE_DAILY_PREMIUM,
        }
    )
    return allowance


def resets_at_for(user, kind: str) -> str:
    """When the next ``kind`` scan comes back for this user (UTC, ``Z``)."""
    now = timezone.now()
    limit = daily_limits(user)[kind]
    return _utc_iso(_slot_back_at(counted_created_at(user, kind, now), limit, now))
