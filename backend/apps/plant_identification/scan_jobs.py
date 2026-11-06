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
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .constants import SCAN_FAILURE_STALE, SCAN_SUMMARY_MAX_SUGGESTIONS
from .scan_models import ScanJob
from .services.quota_manager import QuotaManager

logger = logging.getLogger(__name__)


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
    """Today's date at ``utc_offset_minutes`` from UTC."""
    offset = parse_utc_offset(utc_offset_minutes)
    return (timezone.now() + timedelta(minutes=offset)).date()


def next_local_midnight(utc_offset_minutes: Any) -> datetime:
    """The next local midnight at that offset, as an aware UTC datetime."""
    offset = parse_utc_offset(utc_offset_minutes)
    tomorrow = local_date_for(offset) + timedelta(days=1)
    midnight = datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=dt_timezone.utc
    )
    return midnight - timedelta(minutes=offset)


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


def used_today(user, local_date: date, kind: str) -> int:
    """Scans of ``kind`` this user has spent or reserved on ``local_date``.

    An active job reserves its mode's slot; a finished one counts as what it
    was charged as (a degraded diagnosis counts as an identification). Failed
    and cancelled jobs have no charge and cost nothing.
    """
    used: int = ScanJob.objects.filter(
        Q(status__in=ScanJob.ACTIVE_STATUSES, mode=kind) | Q(charged_as=kind),
        user=user,
        local_date=local_date,
    ).count()
    return used


def allowance_for(user, utc_offset_minutes: Any) -> Dict[str, Any]:
    """The user's scan allowance for their local day.

    Expires the user's stale jobs first, so a stuck job stops reserving.
    """
    expire_stale_jobs(user.pk)
    offset = parse_utc_offset(utc_offset_minutes)
    today = local_date_for(offset)
    limits = daily_limits(user)
    allowance: Dict[str, Any] = {"is_premium": bool(user.has_premium_access())}
    for kind in SCAN_KINDS:
        used = used_today(user, today, kind)
        allowance[kind] = {
            "limit": limits[kind],
            "used": used,
            "remaining": max(0, limits[kind] - used),
        }
    allowance.update(
        {
            "resets_at": next_local_midnight(offset).isoformat().replace("+00:00", "Z"),
            "plant_id_available": bool(QuotaManager().can_call_plant_id(calls=2)),
            "slow_after_seconds": settings.SCAN_SLOW_AFTER_SECONDS,
            "premium_diagnose_limit": settings.SCAN_DIAGNOSE_DAILY_PREMIUM,
        }
    )
    return allowance
