"""Celery tasks for account mail (todo 447 item 11).

Registration, verification and account-link requests used to send SMTP
inline, so a slow mail server (``EMAIL_TIMEOUT=30``) held the request open.
Each view now queues one of these after its transaction commits
(``email_verification.enqueue_on_commit``).

Every task takes a user pk and re-reads the account, so it acts on the state
at send time: a verification mail for an address confirmed in the meantime is
dropped. ``EmailService`` returns False instead of raising, so a failed send
is retried here with ``self.retry``; each attempt is logged, and the last
failure is logged as an error. A retry only follows a send that reported
failure, so a delivered mail is never sent twice.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import OperationalError

from . import constants

logger = logging.getLogger(__name__)

_TASK_OPTIONS = dict(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=constants.ACCOUNT_MAIL_RETRY_DELAY,
    max_retries=constants.ACCOUNT_MAIL_MAX_RETRIES,
    ignore_result=True,
)


def _load_user(user_id):
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        logger.info(f"[EMAIL] Account {user_id} is gone; mail dropped")
    return user


def _retry_or_give_up(task, kind, user_id):
    """Retry a send that reported failure, with backoff; log the final one."""
    if task.request.retries >= task.max_retries:
        logger.error(
            f"[EMAIL] {kind} mail for account {user_id} failed after "
            f"{task.request.retries + 1} attempts; giving up"
        )
        return
    logger.warning(f"[EMAIL] {kind} mail for account {user_id} failed; retrying")
    raise task.retry(
        countdown=constants.ACCOUNT_MAIL_RETRY_DELAY * 2**task.request.retries
    )


@shared_task(**_TASK_OPTIONS)
def send_verification_email_task(self, user_id: int) -> None:
    """Send the verification mail ``send_verification_email`` recorded.

    Outbox (todo 619): the task claims the account's pending
    ``verification_email`` row before sending and records the outcome, so a
    duplicate task (a re-drive racing a slow first enqueue) finds nothing
    to claim and sends nothing. A failed send goes back to pending and is
    retried here with backoff, and by reconciliation if this task's own
    retry is lost; the last failure is terminal. An account with no row at
    all was queued before the outbox existed and is sent as before.
    """
    from apps.core import delivery

    from .email_verification import deliver_verification_email, is_email_verified

    kind = delivery.Kind.VERIFICATION_EMAIL
    user = _load_user(user_id)
    if user is None:
        return
    intent = delivery.claim_one(kind, recipient_id=user_id)
    if intent is None and delivery.has_any(kind, user_id):
        logger.info(
            f"[EMAIL] Verification mail for account {user_id} already sent or "
            f"in progress; duplicate dropped"
        )
        return
    rows = [intent.pk] if intent is not None else []
    if not user.email or is_email_verified(user):
        delivery.mark_suppressed(rows, "not_needed")
        return
    if deliver_verification_email(user):
        delivery.mark_sent(rows)
        return
    if self.request.retries >= self.max_retries:
        delivery.mark_failed(rows, "send_failed")
    else:
        delivery.mark_retry(rows, "send_failed")
    _retry_or_give_up(self, "Verification", user_id)


def redrive_verification_emails(rows) -> None:
    """Reconciliation's redriver (todo 619): re-enqueue the task for each
    account with a due verification row. Charges no allowance."""
    for row in rows:
        send_verification_email_task.delay(row.recipient_id)


@shared_task(**_TASK_OPTIONS)
def send_lockout_email_task(self, user_id: int, intent_id: int | None = None) -> None:
    """Tell an account it was locked out (todo 619: off the login request).

    ``SecurityMonitor._lock_account`` enqueues this after the lockout is
    already enforced in the cache, so neither a slow SMTP server nor a
    broker outage changes what a login answers. The details (attempt count,
    client IPs, lock time) are read from the lockout record in the cache,
    never carried in the task's arguments: a lockout that has already
    expired has nothing left to warn about, and the mail is dropped. A
    failed send is retried with backoff, then logged and dropped.
    ``intent_id`` is the outbox row reconciliation re-drives when the
    enqueue itself failed.
    """
    from apps.core import delivery
    from apps.core.constants import LOCKOUT_STATUS_KEY
    from apps.core.security import SecurityMonitor
    from django.core.cache import cache

    if intent_id is not None and self.request.retries == 0:
        if delivery.claim_one(intent_id=intent_id) is None:
            return  # another worker has it, or it is finished
    rows = [intent_id] if intent_id is not None else []
    user = _load_user(user_id)
    if user is None or not user.email:
        delivery.mark_suppressed(rows, "no_destination")
        return
    lockout_data = cache.get(LOCKOUT_STATUS_KEY.format(username=user.username))
    if not lockout_data:
        logger.info(f"[EMAIL] Lockout for account {user_id} is over; mail dropped")
        delivery.mark_suppressed(rows, "lockout_over")
        return
    if SecurityMonitor._send_lockout_notification(user.username, lockout_data):
        delivery.mark_sent(rows)
        return
    if self.request.retries >= self.max_retries:
        delivery.mark_failed(rows, "send_failed")
    _retry_or_give_up(self, "Lockout", user_id)


def redrive_lockout_emails(rows) -> None:
    """Reconciliation's redriver (todo 619) for lockout mail whose enqueue
    failed."""
    for row in rows:
        send_lockout_email_task.delay(row.recipient_id, intent_id=row.pk)


@shared_task(**_TASK_OPTIONS)
def send_welcome_email_task(self, user_id: int) -> None:
    from apps.core.services.email_service import EmailService

    user = _load_user(user_id)
    if user is None:
        return
    if not EmailService().send_welcome_email(user):
        _retry_or_give_up(self, "Welcome", user_id)


@shared_task(**_TASK_OPTIONS)
def send_provider_linked_notice_task(self, user_id: int, provider: str) -> None:
    from .account_links import deliver_provider_linked_notice

    user = _load_user(user_id)
    if user is None or not user.email:
        return
    if not deliver_provider_linked_notice(user, provider):
        _retry_or_give_up(self, "Sign-in link notice", user_id)
