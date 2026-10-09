"""Celery tasks for the blog app."""

from celery import shared_task
from django.db import OperationalError


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
