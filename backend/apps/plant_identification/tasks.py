import logging
from typing import Dict

import requests
from apps.core.exceptions import ExternalAPIError
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.exceptions import Retry
from channels.layers import get_channel_layer

from .exceptions import APIUnavailable, RateLimitExceeded
from .models import PlantIdentificationRequest
from .services.identification_service import PlantIdentificationService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
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
    # idempotent — it short-circuits on any non-"pending" status (Celery FAQ).
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

    if req.status != "pending":
        logger.info(
            "[CELERY] Skipping duplicate task for %s (status=%s)",
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

        results = service.identify_plant_from_request(req, progress_cb=progress_cb)
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
        # Let autoretry handle transient failures; if exhausted, mark failed
        try:
            req.status = "failed"
            req.save(update_fields=["status"])  # keep minimal write
        except Exception:
            pass
        emit("error", {"message": str(e)})
        raise
