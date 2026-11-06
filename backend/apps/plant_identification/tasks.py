"""Celery tasks for Scan 2.0 background scan jobs (B3).

``run_scan_job`` claims a pending job, runs the providers on its stored
photos, and finalizes it with one conditional UPDATE, so a cancel or a stale
expiry that lands meanwhile always wins. ``notify_scan_job_finished`` sends
the "finished" push once per job, and ``send_scan_push_to_device`` delivers
it to one device.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from apps.core.fcm import (
    clear_dead_fcm_token,
    is_dead_fcm_token_error,
    is_fcm_credentials_error,
    is_permanent_fcm_error,
    send_fcm_message,
)
from apps.core.push_devices import device_tokens_for_users
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from .constants import (
    SCAN_FAILURE_ERROR,
    SCAN_FAILURE_NO_RESULT,
    SCAN_FAILURE_TIMEOUT,
    SCAN_JOB_COLLAPSE_KEY,
    SCAN_JOB_EVENT,
    SCAN_JOB_MAX_ATTEMPTS,
    SCAN_JOB_RETRY_COUNTDOWN,
    SCAN_JOB_SOFT_TIME_LIMIT,
    SCAN_JOB_TIME_LIMIT,
    SCAN_PUSH_FAILED,
    SCAN_PUSH_MAX_RETRIES,
    SCAN_PUSH_READY,
    SCAN_PUSH_RETRY_DELAY,
)
from .scan_jobs import (
    classify_scan,
    delete_scan_photos,
    expire_stale_jobs,
    summarize_scan_result,
)
from .scan_models import ScanJob
from .services.combined_identification_service import (
    CombinedPlantIdentificationService,
    ScanAborted,
)

logger = logging.getLogger(__name__)

FINISHED_STATUSES = ("done", "degraded", "failed")


def _read_shots(job: ScanJob) -> Dict[str, bytes]:
    """Each stored photo's bytes by role, read from the private scan storage."""
    shots: Dict[str, bytes] = {}
    for image in job.images.all():
        with image.image.open("rb") as fh:
            shots[image.role] = fh.read()
    return shots


def _still_processing(job_id: int) -> bool:
    """True while the job is still ours to run (no cancel or expiry landed)."""
    return ScanJob.objects.filter(pk=job_id, status="processing").exists()


def _enqueue_notify(job_id: int) -> None:
    """on_commit callback: a refused enqueue is logged, never raised."""
    try:
        notify_scan_job_finished.delay(job_id)
    except Exception as exc:
        logger.error(
            "[SCAN] Could not enqueue the finished push for job=%s: %s",
            job_id,
            type(exc).__name__,
        )


def _finalize(
    job_id: int,
    status: str,
    charged_as: str = "",
    result: Optional[Dict[str, Any]] = None,
    failure_reason: str = "",
) -> bool:
    """Record the outcome, unless the job left ``processing`` meanwhile.

    A cancel or a stale expiry that landed first wins: the UPDATE matches no
    row and nothing else happens (no charge, no onboarding tick, no push).
    """
    with transaction.atomic():
        updated = ScanJob.objects.filter(pk=job_id, status="processing").update(
            status=status,
            charged_as=charged_as,
            result=result,
            failure_reason=failure_reason,
            finished_at=timezone.now(),
        )
        if not updated:
            logger.info(
                "[SCAN] job=%s left processing before it finished; outcome dropped",
                job_id,
            )
            return False
        if status == "failed":
            delete_scan_photos([job_id])
        transaction.on_commit(lambda: _enqueue_notify(job_id))
    # After the commit: onboarding bookkeeping never touches the outcome's
    # transaction (a failed query inside it would poison the finalize).
    if status in ("done", "degraded"):
        from apps.users.onboarding import record_first_identification

        job = ScanJob.objects.select_related("user").get(pk=job_id)
        record_first_identification(job.user)
    logger.info(
        "[SCAN] job=%s finished status=%s charged_as=%s",
        job_id,
        status,
        charged_as or "-",
    )
    return True


@shared_task(
    bind=True,
    max_retries=1,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=SCAN_JOB_SOFT_TIME_LIMIT,
    time_limit=SCAN_JOB_TIME_LIMIT,
    ignore_result=True,
)
def run_scan_job(self, job_id: int) -> None:
    """Run one scan job: claim, identify, classify, finalize, then notify.

    The claim is a conditional UPDATE on an active status, so a cancelled,
    finished or expired job is never run, and a redelivery re-claims only a
    job still active. A scan that names no plant is retried once
    automatically; any unexpected error finalizes the job as failed. Retry
    config: ``max_retries=1`` with that one explicit ``self.retry``; provider
    errors are already converted to "no result" inside the service.
    """
    # attempts__lt: a job whose worker keeps dying (acks_late redelivers it)
    # stops being re-run; the stale expiry then fails it.
    claimed = ScanJob.objects.filter(
        pk=job_id,
        status__in=ScanJob.ACTIVE_STATUSES,
        attempts__lt=SCAN_JOB_MAX_ATTEMPTS,
    ).update(status="processing", attempts=F("attempts") + 1)
    if not claimed:
        logger.info("[SCAN] job=%s is not claimable; nothing to run", job_id)
        return

    try:
        # Inside the try: a failed read after the claim must finalize the job,
        # not leave it processing until the stale expiry.
        job = ScanJob.objects.get(pk=job_id)
        shots = _read_shots(job)
        results = CombinedPlantIdentificationService().scan(
            shots,
            job.mode,
            should_continue=lambda: _still_processing(job_id),
        )
        status, charged_as = classify_scan(job.mode, results)
        summary = summarize_scan_result(job.mode, results)
    except ScanAborted:
        # Cancelled or expired before the paid call: the cancel/expiry
        # already wrote the outcome, and no Plant.id call was made.
        logger.info("[SCAN] job=%s left processing; Plant.id not called", job_id)
        return
    except SoftTimeLimitExceeded:
        logger.error("[SCAN] job=%s hit the soft time limit", job_id)
        _finalize(job_id, "failed", failure_reason=SCAN_FAILURE_TIMEOUT)
        raise
    except Exception as exc:
        logger.error(
            "[SCAN] job=%s failed unexpectedly: %s",
            job_id,
            type(exc).__name__,
            exc_info=True,
        )
        _finalize(job_id, "failed", failure_reason=SCAN_FAILURE_ERROR)
        return

    # Outside the try: Retry is an Exception and must not be finalized away.
    if status == "failed" and self.request.retries == 0:
        logger.warning("[SCAN] job=%s named no plant; retrying once", job_id)
        raise self.retry(countdown=SCAN_JOB_RETRY_COUNTDOWN)

    _finalize(
        job_id,
        status,
        charged_as=charged_as,
        result=summary,
        failure_reason=SCAN_FAILURE_NO_RESULT if status == "failed" else "",
    )


@shared_task(ignore_result=True)
def expire_stale_scan_jobs() -> int:
    """Beat: fail every scan job stuck past the stale limit (scan-2 audit M2).

    The per-user expiry only runs when that user asks again; a job whose
    worker died would otherwise stay active, unnotified, until they do.
    """
    return expire_stale_jobs()


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=SCAN_PUSH_RETRY_DELAY,
    max_retries=SCAN_PUSH_MAX_RETRIES,
    ignore_result=True,
)
def notify_scan_job_finished(self, job_id: int) -> None:
    """Send the "finished" push for one job, once.

    The claim sets ``notified_at`` on a finished job that has none, so a
    second run sends nothing. Everything after the claim runs under a guard
    that releases it on any escape, so an ``OperationalError`` retry can
    claim again instead of finding the job already marked notified.
    """
    claimed = ScanJob.objects.filter(
        pk=job_id, notified_at__isnull=True, status__in=FINISHED_STATUSES
    ).update(notified_at=timezone.now())
    if not claimed:
        return
    try:
        job = ScanJob.objects.only("uuid", "status", "user_id").get(pk=job_id)
        tokens = device_tokens_for_users([job.user_id]).get(job.user_id, [])
    except BaseException:
        ScanJob.objects.filter(pk=job_id).update(notified_at=None)
        raise
    data = {"event": SCAN_JOB_EVENT, "job_id": str(job.uuid), "status": job.status}
    content = list(SCAN_PUSH_FAILED if job.status == "failed" else SCAN_PUSH_READY)
    for token in tokens:
        try:
            send_scan_push_to_device.delay(job.user_id, token, data, content)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            logger.warning(
                "[FCM] scan push for one device of user=%s could not be "
                "enqueued (job=%s): %s",
                job.user_id,
                job_id,
                type(exc).__name__,
            )


@shared_task(
    bind=True,
    max_retries=SCAN_PUSH_MAX_RETRIES,
    default_retry_delay=SCAN_PUSH_RETRY_DELAY,
    ignore_result=True,
)
def send_scan_push_to_device(
    self, owner_id: int, token: str, data: dict, content: list[str]
) -> None:
    """Send one scan-finished push to ONE device.

    Mirrors ``garden_calendar.tasks.send_care_reminder_to_device``: skipped
    when push is off, the account is inactive, or the token is no longer
    theirs. Backoff 30s, 60s, 120s; permanent failures are not retried and a
    dead token is forgotten.
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from apps.core.push_devices import is_registered
    from django.contrib.auth import get_user_model

    if not is_firebase_available():
        return
    User = get_user_model()
    if not User.objects.filter(pk=owner_id, is_active=True).exists():
        return
    if not is_registered(owner_id, token):
        return
    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot send a scan push")
        return
    title, body = content
    try:
        send_fcm_message(fcm, token, data, (title, body), SCAN_JOB_COLLAPSE_KEY)
    except SoftTimeLimitExceeded:
        # Celery's time limit is not a delivery failure: never retry it.
        raise
    except Exception as exc:
        if is_permanent_fcm_error(exc):
            if is_dead_fcm_token_error(exc):
                clear_dead_fcm_token(owner_id, token)
            logger.log(
                logging.ERROR if is_fcm_credentials_error(exc) else logging.WARNING,
                "[FCM] scan push failed permanently (user=%s, task_id=%s): %s",
                owner_id,
                self.request.id,
                exc,
            )
            return
        logger.warning(
            "[FCM] scan push failed (user=%s, task_id=%s): %s — retrying",
            owner_id,
            self.request.id,
            exc,
        )
        raise self.retry(
            exc=exc, countdown=self.default_retry_delay * (2**self.request.retries)
        ) from exc
