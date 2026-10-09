"""Celery tasks for the blog app."""

import logging

from celery import shared_task
from django.db import OperationalError

from .constants import (
    NEWSLETTER_CONTINUATION_DELAY,
    NEWSLETTER_SOFT_TIME_LIMIT,
    NEWSLETTER_TIME_LIMIT,
)

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=30,
    max_retries=3,
    ignore_result=True,
)
def send_newsletter_confirmation(email: str) -> None:
    """Decide whether `email` gets a newsletter confirmation link, and send it.

    The signup view enqueues this for every valid address, so its response
    reveals nothing (todo 409). A retry never sends twice: a resend inside the
    throttle window is skipped. The cost is that an OperationalError while
    undoing the stamp of a failed send leaves the address throttled for that
    window, so the reader asks again later.
    """
    from .newsletter import request_confirmation

    request_confirmation(email)


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    max_retries=3,
    soft_time_limit=NEWSLETTER_SOFT_TIME_LIMIT,
    time_limit=NEWSLETTER_TIME_LIMIT,
    ignore_result=True,
)
def send_blog_weekly_newsletter(self):
    """Celery beat entry (settings.CELERY_BEAT_SCHEDULE) for
    `manage.py send_blog_newsletter` (todo 409).

    The command makes a rerun safe: its run lock turns away an overlapping
    fire, and each subscriber's `last_sent_at` is claimed before their email
    goes out, so a retry or a continuation sends only to those still due.
    """
    from io import StringIO

    from celery.exceptions import SoftTimeLimitExceeded
    from django.core.management import call_command

    logger.info(f"[EMAIL] blog newsletter: starting (task={self.request.id})")
    out = StringIO()
    try:
        call_command("send_blog_newsletter", stdout=out)
    except SoftTimeLimitExceeded:
        logger.warning(
            f"[EMAIL] blog newsletter hit the soft time limit (task={self.request.id}); "
            "re-enqueuing to finish the subscribers still due"
        )
        send_blog_weekly_newsletter.apply_async(countdown=NEWSLETTER_CONTINUATION_DELAY)
        return
    finally:
        for line in out.getvalue().splitlines():
            if line.strip():
                logger.info(f"{line} (task={self.request.id})")
