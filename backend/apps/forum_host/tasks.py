"""Celery tasks for forum push (Issue 14) and email (todo 253 slice 2, H1)
notifications.

Fired by forum_host/notifications.py dispatch() via .delay() so that:
- The publish transaction is never held open waiting for FCM/SMTP.
- A failed delivery never rolls back a moderation decision.
- Tasks are retried automatically by Celery on their respective transient
  error classes (FCM send errors for push; OperationalError for email).
"""

import logging

from celery import shared_task
from django.db import OperationalError

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


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3)
def send_forum_email(event: str, recipient_user_id: int, data: dict):
    """Send a single forum notification email via NotificationService.

    Enqueued from forum_host/notifications.py via transaction.on_commit,
    mirroring send_forum_push, so a rolled-back publish never sends an email.

    Retry is narrowly scoped to OperationalError (a transient DB error during
    the User/Post fetches below), not a broad catch-all: unlike push's
    fcm.send() (which raises on a transient FCM error), this task's actual
    send call — NotificationService.send_forum_reply_notification() ->
    EmailService.send_email() — swallows every send/render failure internally
    (ConnectionError, TemplateDoesNotExist, a blanket Exception) and returns a
    bool, so it can never raise; wrapping IT in retry would be untested dead
    code. The DB fetches below CAN genuinely raise OperationalError on a
    connection blip, and per docs/rules/celery.md ("every task declares
    retry config... never leave a network-touching task with default no
    retries") that failure must not silently drop the notification — the
    DoesNotExist/ValueError/TypeError branches return early first, so
    autoretry only ever fires on the one real transient-failure class.

    Args:
        event: forum event name. Only "reply_added" is wired (todo 253 slice
               2, H1); mention/moderation/digest are later slices.
        recipient_user_id: pk of the User to email.
        data: the same payload dict shared with send_forum_push — carries
              "post_id" (str). The reply Post is re-fetched here (rather than
              embedding rendered content in the FCM-shared payload) so push's
              data stays minimal and the email reflects the post at send time.
    """
    if event != "reply_added":
        logger.debug(
            "[EMAIL] forum email skipped — event=%s not implemented yet", event
        )
        return

    from apps.core.services.notification_service import NotificationService
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from wagtail_forum.api.views import plain_text_excerpt
    from wagtail_forum.models import Post

    from .constants import FORUM_EMAIL_EXCERPT_MAX_CHARS

    User = get_user_model()

    try:
        user = User.objects.get(pk=recipient_user_id)
    except User.DoesNotExist:
        logger.warning(
            "[EMAIL] forum email skipped — user %s not found", recipient_user_id
        )
        return

    if not user.email:
        # EmailService.send_email() silently no-ops for a blank recipient
        # (Django's EmailMessage.recipients() filters out falsy addresses,
        # send() then returns 0) but still logs "sent successfully" and
        # returns True — it does not surface the 0-recipients case as a
        # failure. Guard here so a user with no email on file gets a clear
        # skip log instead of a misleading success one.
        logger.warning(
            "[EMAIL] forum email skipped — user %s has no email on file",
            recipient_user_id,
        )
        return

    try:
        post_id = int(data.get("post_id", ""))
        post = Post.objects.select_related("topic__board", "author").get(pk=post_id)
    except (TypeError, ValueError):
        logger.warning(
            "[EMAIL] forum email skipped — invalid post_id in payload: %r",
            data.get("post_id"),
        )
        return
    except Post.DoesNotExist:
        logger.warning("[EMAIL] forum email skipped — post %s not found", post_id)
        return

    topic = post.topic
    topic_url = f"{settings.SITE_URL}{topic.get_absolute_url()}"
    author_name = post.author.display_name if post.author else "[deleted]"
    excerpt = plain_text_excerpt(post.body, FORUM_EMAIL_EXCERPT_MAX_CHARS)

    sent = NotificationService().send_forum_reply_notification(
        user=user,
        topic_title=topic.title,
        reply_author=author_name,
        reply_excerpt=excerpt,
        topic_url=topic_url,
    )
    logger.info(
        "[EMAIL] forum.%s email to user=%s: sent=%s", event, recipient_user_id, sent
    )
