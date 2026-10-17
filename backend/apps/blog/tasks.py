"""Celery tasks for the blog app."""

import logging

from celery import shared_task
from django.db import OperationalError

from .constants import (
    NEWSLETTER_CONFIRMATION_MAX_RETRIES,
    NEWSLETTER_CONFIRMATION_RETRY_DELAY,
    NEWSLETTER_CONTINUATION_DELAY,
    NEWSLETTER_SOFT_TIME_LIMIT,
    NEWSLETTER_TIME_LIMIT,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=30,
    max_retries=NEWSLETTER_CONFIRMATION_MAX_RETRIES,
    ignore_result=True,
)
def send_newsletter_confirmation(
    self, email: str, intent_id: int | None = None
) -> None:
    """Decide whether `email` gets a newsletter confirmation link, and send it.

    The signup view enqueues this for every valid address, so its response
    reveals nothing (todo 409). A retry never sends twice: a resend inside the
    throttle window is skipped. The cost is that an OperationalError while
    undoing the stamp of a failed send leaves the address throttled for that
    window, so the reader asks again later.

    A send that fails is retried with backoff (todo 619): the failure gave
    the stamp back, so the retry re-decides and is not throttled, and an
    address subscribed in the meantime is skipped. A skip is never retried.
    ``intent_id`` is the outbox row reconciliation re-drives after a lost
    enqueue; its outcome is recorded on it.
    """
    from apps.core import delivery

    from .newsletter import (
        CONFIRMATION_FAILED,
        CONFIRMATION_SENT,
        CONFIRMATION_SUPPRESSED,
        request_confirmation_outcome,
    )

    if intent_id is not None and self.request.retries == 0:
        if delivery.claim_one(intent_id=intent_id) is None:
            return  # another worker has it, or it is finished
    outcome = request_confirmation_outcome(email)
    if outcome != CONFIRMATION_FAILED:
        if intent_id is not None:
            if outcome == CONFIRMATION_SENT:
                delivery.mark_sent([intent_id])
            elif outcome == CONFIRMATION_SUPPRESSED:
                delivery.mark_suppressed([intent_id], "address_suppressed")
            else:
                delivery.mark_suppressed([intent_id], "not_needed")
        return
    if self.request.retries >= self.max_retries:
        logger.error(
            "[EMAIL] newsletter confirmation failed after %s attempts; giving up",
            self.request.retries + 1,
        )
        if intent_id is not None:
            delivery.mark_failed([intent_id], "send_failed")
        return
    logger.warning("[EMAIL] newsletter confirmation failed; retrying")
    raise self.retry(
        countdown=NEWSLETTER_CONFIRMATION_RETRY_DELAY * 2**self.request.retries
    )


def redrive_newsletter_confirmations(rows) -> None:
    """Reconciliation's redriver (todo 619): re-enqueue each confirmation
    whose signup enqueue was lost. The task re-decides, so a reader who
    subscribed or was sent a link meanwhile gets nothing extra."""
    from apps.core import delivery

    from .models import BlogNewsletter

    by_pk = BlogNewsletter.objects.in_bulk(
        [int(row.subject_key) for row in rows if row.subject_key.isdigit()]
    )
    for row in rows:
        subscriber = (
            by_pk.get(int(row.subject_key)) if row.subject_key.isdigit() else None
        )
        if subscriber is None:
            delivery.mark_suppressed([row.pk], "recipient_missing")
            continue
        send_newsletter_confirmation.delay(subscriber.email, intent_id=row.pk)


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    max_retries=3,
    soft_time_limit=NEWSLETTER_SOFT_TIME_LIMIT,
    time_limit=NEWSLETTER_TIME_LIMIT,
    ignore_result=True,
)
def send_blog_weekly_newsletter(self, recovery: int = 0):
    """Celery beat entry (settings.CELERY_BEAT_SCHEDULE) for
    `manage.py send_blog_newsletter` (todo 409).

    The command makes a rerun safe: its run lock turns away an overlapping
    fire, and each subscriber's `last_sent_at` is claimed before their email
    goes out, so a retry or a continuation sends only to those still due.

    A run that reports failed sends enqueues a bounded recovery run
    (``recovery`` counts them, todo 619); see
    ``apps.core.delivery.schedule_weekly_recovery``.
    """
    from io import StringIO

    from apps.core.delivery import schedule_weekly_recovery
    from celery.exceptions import SoftTimeLimitExceeded
    from django.core.management import call_command

    logger.info("[EMAIL] blog newsletter: starting (task=%s)", self.request.id)
    out = StringIO()
    try:
        call_command("send_blog_newsletter", stdout=out)
    except SoftTimeLimitExceeded:
        logger.warning(
            "[EMAIL] blog newsletter hit the soft time limit (task=%s); "
            "re-enqueuing to finish the subscribers still due",
            self.request.id,
        )
        # A continuation keeps its run's recovery count (todo 619).
        extra = {"kwargs": {"recovery": recovery}} if recovery else {}
        send_blog_weekly_newsletter.apply_async(
            countdown=NEWSLETTER_CONTINUATION_DELAY, **extra
        )
        return
    finally:
        for line in out.getvalue().splitlines():
            if line.strip():
                # No prefix of our own: this relays `send_blog_newsletter`'s stdout, and
                # every line it writes already opens with [EMAIL]. Adding one
                # here would log "[EMAIL] [EMAIL] ..." (todo 392).
                # log-prefix: exempt (relayed command output, already prefixed)
                logger.info("%s (task=%s)", line, self.request.id)
    schedule_weekly_recovery(
        send_blog_weekly_newsletter, out.getvalue(), recovery, "blog newsletter"
    )
