import logging
from typing import Dict

import requests
from apps.core.exceptions import ExternalAPIError
from asgiref.sync import async_to_sync
from celery import Task, shared_task
from celery.exceptions import Retry
from channels.layers import get_channel_layer

from .exceptions import APIUnavailable, RateLimitExceeded
from .models import PlantIdentificationRequest
from .services.identification_service import PlantIdentificationService

logger = logging.getLogger(__name__)

# Statuses that mean the request is finalized — never to be overwritten or
# re-processed. Two terminal-success states plus the terminal-failure state.
TERMINAL_STATUSES = ("identified", "needs_help", "failed")


class IdentificationTask(Task):
    """Base task that owns the terminal "failed" write for run_identification.

    Celery calls ``on_failure`` once the task ultimately fails — either a
    non-retryable error, or autoretry/``self.retry`` exhaustion
    (``MaxRetriesExceededError``, audit M12). Marking the request "failed" ONLY
    here (never mid-flight in the task body) means a failed write can't:
      - pre-empt ``autoretry_for`` before it gets a chance to retry, or
      - clobber a terminal-success status on a retried run, or
      - leave the request stuck "pending"/"processing" when retries run out.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        request_uuid = args[0] if args else kwargs.get("request_uuid")
        if not request_uuid:
            return
        # Don't overwrite a request that already reached a terminal state
        # (a successful run that some later signal failed on, etc.).
        updated = (
            PlantIdentificationRequest.objects.filter(request_id=request_uuid)
            .exclude(status__in=TERMINAL_STATUSES)
            .update(status="failed")
        )
        if updated:
            logger.error(
                "[CELERY] run_identification failed for %s, marked failed: %s",
                request_uuid,
                exc,
            )


@shared_task(
    bind=True,
    base=IdentificationTask,
    # Retry only transient external-API failures — never permanent errors
    # (bad input, missing records, programming bugs), which never recover.
    autoretry_for=(
        ExternalAPIError,
        APIUnavailable,
        requests.exceptions.RequestException,
    ),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
    retry_jitter=True,
    rate_limit="100/h",  # Limit task execution rate
    # Durability: a worker killed mid-identification (up to 120s of external I/O)
    # must not silently drop the message. ack the message only after the task
    # returns, and requeue it if the worker is lost. Safe because the task is
    # idempotent — it short-circuits on any terminal status (Celery FAQ).
    # NB: the per-task decorator option is `reject_on_worker_lost` (the `task_`
    # prefix names the *global* setting, not the task attribute).
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_identification(self, request_uuid: str) -> Dict:
    """
    Celery task to process a PlantIdentificationRequest asynchronously.

    Args:
        request_uuid: The UUID string of PlantIdentificationRequest.request_id

    Returns:
        Dict with final status and results_count for simple monitoring.
    """
    try:
        req = PlantIdentificationRequest.objects.get(request_id=request_uuid)
    except PlantIdentificationRequest.DoesNotExist:
        logger.error("Identification request not found: %s", request_uuid)
        return {"status": "not_found", "results_count": 0}

    # Skip only requests that already reached a terminal status. A "processing"
    # request is NOT terminal — it's an autoretry (or a worker-lost requeue) of an
    # attempt that set "processing" then failed, and MUST be allowed to re-run.
    # Guarding on `!= "pending"` (the old behavior) skipped every retry, making
    # autoretry a silent no-op (audit H1).
    if req.status in TERMINAL_STATUSES:
        logger.info(
            "[CELERY] Skipping finalized task for %s (status=%s)",
            request_uuid,
            req.status,
        )
        return {"status": req.status, "results_count": 0}

    channel_layer = get_channel_layer()

    def emit(event_type: str, payload: Dict):
        try:
            async_to_sync(channel_layer.group_send)(
                f"plant_id_req_{request_uuid}",
                {"type": event_type, **payload},
            )
        except Exception:
            # Don't break task if websocket layer is unavailable
            pass

    emit("progress", {"stage": "queued", "status": "queued", "data": {}})

    try:
        service = PlantIdentificationService()
        emit(
            "progress",
            {
                "stage": "processing_start",
                "status": "processing",
                "data": {"request_id": request_uuid},
            },
        )

        # Define granular progress callback to forward service events to websocket
        def progress_cb(stage: str, status: str, data: Dict):
            emit("progress", {"stage": stage, "status": status, "data": data or {}})

        # reraise_transient=True: let retryable external-API errors propagate so
        # autoretry_for fires. (Synchronous view callers leave this False and keep
        # graceful fallback — the service is shared.)
        results = service.identify_plant_from_request(
            req, progress_cb=progress_cb, reraise_transient=True
        )
        emit("completed", {"status": req.status, "results_count": len(results)})
        return {"status": req.status, "results_count": len(results)}
    except RateLimitExceeded as e:
        # Handle rate limiting with exponential backoff
        logger.warning(f"Rate limit hit for request {request_uuid}: {e}")
        emit(
            "progress",
            {
                "stage": "rate_limited",
                "status": "queued",
                "data": {"retry_after": e.retry_after, "message": str(e)},
            },
        )
        # Retry with exponential backoff based on retry_after hint
        retry_in = min(e.retry_after if e.retry_after else 60, 300)  # Max 5 minutes
        raise self.retry(exc=e, countdown=retry_in)
    except Exception as e:
        logger.exception("Async identification failed for %s: %s", request_uuid, e)
        # Don't write a terminal "failed" status here. Re-raise so autoretry_for
        # can retry transient failures; the terminal write is owned solely by
        # IdentificationTask.on_failure, which runs once retries are exhausted.
        # A mid-flight write would pre-empt the retry and could clobber a
        # terminal-success status on a retried run (audit H1).
        emit("error", {"message": str(e)})
        raise
