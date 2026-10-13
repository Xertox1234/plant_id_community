"""Celery tasks for the core app."""

import logging

from celery import shared_task
from django.db import OperationalError

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    max_retries=2,
    ignore_result=True,
)
def reconcile_deliveries() -> None:
    """Beat entry (settings.CELERY_BEAT_SCHEDULE) for the delivery outbox
    (todo 619): re-drive deliveries whose enqueue was lost, whose transient
    failure is due again, or whose worker died; expire and prune old rows.
    Overlap-safe: see ``apps.core.delivery.reconcile``. A retry after a
    database error is safe for the same reason."""
    from .delivery import reconcile

    totals = reconcile()
    if any(totals.values()):
        logger.info(
            "[DELIVERY] reconcile: redriven=%(redriven)s expired=%(expired)s "
            "interrupted=%(interrupted)s pruned=%(pruned)s",
            totals,
        )
