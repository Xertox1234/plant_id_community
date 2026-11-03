"""Scan job outcome rules: classification, the client summary, stale expiry.

Pure functions over the combined service's result dict (Scan 2.0 B3), plus
the one conditional UPDATE that expires stuck jobs. The allowance functions
arrive with the API (B4).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from .constants import SCAN_FAILURE_STALE, SCAN_SUMMARY_MAX_SUGGESTIONS
from .scan_models import ScanJob

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


def expire_stale_jobs(user_id: int) -> int:
    """Fail this user's jobs still active past ``SCAN_JOB_STALE_MINUTES``.

    One conditional UPDATE. A worker that finishes later finds the job no
    longer ``processing`` and its finalize matches nothing. Returns the count.
    """
    now = timezone.now()
    cutoff = now - timedelta(minutes=settings.SCAN_JOB_STALE_MINUTES)
    expired: int = ScanJob.objects.filter(
        user_id=user_id,
        status__in=ScanJob.ACTIVE_STATUSES,
        created_at__lt=cutoff,
    ).update(status="failed", failure_reason=SCAN_FAILURE_STALE, finished_at=now)
    if expired:
        logger.warning(
            "[SCAN] Expired %s stale scan job(s) for user=%s", expired, user_id
        )
    return expired
