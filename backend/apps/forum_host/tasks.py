"""Celery tasks for forum push notifications (Issue 14).

Fired by forum_host/notifications.py dispatch() via .delay() so that:
- The publish transaction is never held open waiting for FCM.
- A failed push never rolls back a moderation decision.
- Tasks are retried automatically by Celery on transient FCM errors.
"""

import logging

from celery import shared_task

logger = logging.getLogger("forum_host.tasks")


def _is_permanent_fcm_error(exc: Exception) -> bool:
    """Permanent FCM failures must not be retried (docs/patterns/domain/celery.md;
    audit 2026-07-11 M33): a stale/invalid device token (UnregisteredError) or a
    malformed message can never succeed on retry. firebase_admin is an optional,
    lazily-imported dependency, so classification is best-effort — unclassifiable
    errors stay retryable (transient by default).
    """
    try:
        from firebase_admin import exceptions as fb_exceptions
        from firebase_admin import messaging
    except ImportError:  # pragma: no cover — Firebase not installed
        return False
    return isinstance(
        exc,
        (
            messaging.UnregisteredError,
            messaging.SenderIdMismatchError,
            messaging.ThirdPartyAuthError,
            fb_exceptions.InvalidArgumentError,
        ),
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_forum_push(self, event: str, recipient_user_id: int, data: dict):
    """Send a single FCM data message for a forum event.

    Args:
        event: one of "reply_added", "moderation_decided", "topic_created".
        recipient_user_id: pk of the User whose FCM token to look up.
        data: dict of string key/value pairs to include in the FCM data payload.
              All values are coerced to strings (FCM requirement).
    """
    from apps.garden.firebase_config import get_fcm_client, is_firebase_available
    from django.contrib.auth import get_user_model
    from wagtail_forum.models import ForumProfile

    User = get_user_model()

    if not is_firebase_available():
        logger.debug("[FCM] Firebase not configured — skipping forum push (%s)", event)
        return

    try:
        user = User.objects.get(pk=recipient_user_id)
    except User.DoesNotExist:
        logger.warning(
            "[FCM] forum push skipped — user %s not found", recipient_user_id
        )
        return

    if not getattr(user, "forum_notifications", True) is True:
        logger.debug(
            "[FCM] forum push skipped — user %s has forum_notifications=False",
            recipient_user_id,
        )
        return

    profile = ForumProfile.for_user(user)
    token = profile.fcm_token
    if not token:
        logger.debug(
            "[FCM] forum push skipped — user %s has no FCM token", recipient_user_id
        )
        return

    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot send forum push")
        return

    # Coerce all values to strings — FCM data payloads must be str:str.
    str_data = {k: str(v) for k, v in data.items()}
    str_data["event"] = event

    try:
        message = fcm.Message(data=str_data, token=token)
        response = fcm.send(message)
        logger.info(
            "[FCM] forum.%s sent to user=%s: %s", event, recipient_user_id, response
        )
    except Exception as exc:
        if _is_permanent_fcm_error(exc):
            # e.g. the device token is stale — retrying can never succeed.
            logger.warning(
                "[FCM] forum.%s send failed permanently (user=%s, task_id=%s):"
                " %s — not retrying",
                event,
                recipient_user_id,
                self.request.id,
                exc,
            )
            return
        logger.warning(
            "[FCM] forum.%s send failed (user=%s, task_id=%s): %s — retrying",
            event,
            recipient_user_id,
            self.request.id,
            exc,
        )
        # Exponential backoff: 30s, 60s, 120s across max_retries=3.
        raise self.retry(
            exc=exc, countdown=self.default_retry_delay * (2**self.request.retries)
        )
