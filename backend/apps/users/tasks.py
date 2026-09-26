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
    from .email_verification import deliver_verification_email, is_email_verified

    user = _load_user(user_id)
    if user is None or not user.email or is_email_verified(user):
        return
    if not deliver_verification_email(user):
        _retry_or_give_up(self, "Verification", user_id)


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
