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


def _notification_content(event: str, data: dict) -> tuple[str, str] | None:
    """Human-readable (title, body) for an FCM tray notification (todo 253
    slice 6, AC6), or None for events that must stay tray-silent.

    Sent alongside the unchanged data payload as a notification+data hybrid:
    the OS renders the tray entry itself when the app is backgrounded, so a
    client needs zero display code; the data payload still rides along for
    richer in-app handling. Every field is optional — a missing/empty value
    degrades to generic wording, never an error (a push must not fail over
    cosmetics). Event values arrive as plain strings (Celery JSON-serializes
    NotificationVerb.MENTION to "mention" through the broker).

    Only reply_added and mention render a tray entry. moderation_decided is
    deliberately None: workflow.py fires it with status="published" on EVERY
    routine trust-autopublished post/reply/edit, so a visible block would
    tray-popup "Your post was published" at users for their own ordinary
    posts (slice-6 review, cross-file tracer) — it keeps the pre-slice
    data-only behavior. Unknown/future events also stay data-only until
    someone designs their copy.
    """
    from .constants import PUSH_TITLE_TOPIC_MAX_CHARS

    topic_title = str(data.get("topic_title") or "").strip()
    if len(topic_title) > PUSH_TITLE_TOPIC_MAX_CHARS:
        topic_title = topic_title[: PUSH_TITLE_TOPIC_MAX_CHARS - 1] + "…"
    actor = str(data.get("actor_name") or "").strip() or "Someone"

    if event == "reply_added":
        title = f'New reply in "{topic_title}"' if topic_title else "New forum reply"
        return title, f"{actor} replied"
    if event == "mention":
        title = (
            f'You were mentioned in "{topic_title}"'
            if topic_title
            else "You were mentioned on the forum"
        )
        return title, f"{actor} mentioned you"
    return None


def _send_fcm_message(fcm, token: str, str_data: dict, content, event: str):
    """Build and send one FCM message (data payload + optional tray notification).

    Shared by send_forum_push (single) and send_forum_push_batch (todo 268) so
    the collapse-key / notification-hybrid construction can never drift between
    the two shapes. Raises on send failure; the caller classifies transient vs.
    permanent (see _is_permanent_fcm_error) and decides whether to retry.
    """
    message_kwargs = {"data": str_data, "token": token}
    if content is not None:
        title, body = content
        # Stable collapse key: a retry after an accepted-but-timed-out send
        # REPLACES the tray entry instead of stacking a duplicate. Deliberately
        # per-EVENT-TYPE, not per-post (FCM keeps at most 4 collapse keys pending
        # per offline device). See docs/rules/celery.md.
        collapse_key = f"forum-{event}"
        message_kwargs["notification"] = fcm.Notification(title=title, body=body)
        message_kwargs["android"] = fcm.AndroidConfig(collapse_key=collapse_key)
        message_kwargs["apns"] = fcm.APNSConfig(
            headers={"apns-collapse-id": collapse_key}
        )
    message = fcm.Message(**message_kwargs)
    return fcm.send(message)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_forum_push(self, event: str, recipient_user_id: int, data: dict):
    """Send a single FCM data message for a forum event.

    Args:
        event: one of "reply_added", "moderation_decided", "topic_created",
               "mention" (todo 253 slice 4, H4 — dispatched from both
               reply_added and topic_created's mention handling, not a
               signal name of its own).
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

    content = _notification_content(event, data)

    try:
        response = _send_fcm_message(fcm, token, str_data, content, event)
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
def send_forum_push_batch(event: str, recipient_user_ids: list[int], data: dict):
    """Fan out one forum FCM push to many recipients from a SINGLE enqueue (todo 268).

    forum_host/notifications.py used to call send_forum_push.delay() once per
    subscriber inside transaction.on_commit — N sequential broker round-trips
    blocking the reply request, plus N worker executions each re-fetching the
    same rows. This variant is enqueued once with the full recipient list: one
    bulk ForumProfile fetch, then a server-side send loop.

    Per-recipient transient FCM failures are handed off to the single-recipient
    send_forum_push task (which owns the backoff/retry logic) rather than
    retrying the whole batch — a batch-level retry would re-send to EVERY
    recipient (the collapse key dedupes the tray, not the wasted work). Only the
    rare failure path re-enqueues; the common all-success path stays at one
    enqueue. autoretry_for=(OperationalError,) covers only the pre-send bulk
    fetch.

    Args:
        event: forum event name (see send_forum_push).
        recipient_user_ids: pks of the Users to notify.
        data: FCM data payload (values coerced to str).
    """
    from apps.garden.firebase_config import get_fcm_client, is_firebase_available
    from wagtail_forum.models import ForumProfile

    if not recipient_user_ids:
        return

    if not is_firebase_available():
        logger.debug("[FCM] Firebase not configured — skipping forum push (%s)", event)
        return

    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot send forum push")
        return

    # One bulk fetch instead of N: the profile row carries both the recipient
    # (forum_notifications) and the fcm_token. A user with no ForumProfile has
    # no token, so the single-task path would skip them too — omitting them
    # here is equivalent.
    profiles = ForumProfile.objects.filter(
        user_id__in=recipient_user_ids
    ).select_related("user")

    str_data = {k: str(v) for k, v in data.items()}
    str_data["event"] = event
    content = _notification_content(event, data)

    for profile in profiles:
        user = profile.user
        if getattr(user, "forum_notifications", True) is not True:
            continue
        if not profile.fcm_token:
            continue
        try:
            response = _send_fcm_message(
                fcm, profile.fcm_token, str_data, content, event
            )
            logger.info("[FCM] forum.%s sent to user=%s: %s", event, user.pk, response)
        except Exception as exc:
            if _is_permanent_fcm_error(exc):
                logger.warning(
                    "[FCM] forum.%s send failed permanently (user=%s): %s"
                    " — not retrying",
                    event,
                    user.pk,
                    exc,
                )
                continue
            # Transient: hand off to the retry-capable single-recipient task
            # rather than retrying (and re-sending) the whole batch.
            logger.warning(
                "[FCM] forum.%s send failed (user=%s): %s — re-enqueuing single",
                event,
                user.pk,
                exc,
            )
            send_forum_push.delay(event, user.pk, data)


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3)
def send_forum_email_batch(event: str, recipient_user_ids: list[int], data: dict):
    """Send forum reply-notification emails to many recipients from a SINGLE
    enqueue (todo 268), replacing the per-recipient send_forum_email fan-out.

    The Post and all recipient Users are fetched ONCE up front, then the loop
    only calls NotificationService — whose send path
    (EmailService.send_email()) swallows every send/render failure and returns a
    bool, so it can never raise. This ordering is load-bearing: email has no
    collapse-key dedup, so autoretry_for=(OperationalError,) must be able to
    fire ONLY before any email is sent, or a transient-DB retry would
    double-email everyone. All OperationalError-raising DB access happens in the
    up-front fetch; the send loop does none.

    Args:
        event: only "reply_added" is wired (todo 253 slice 2, H1); mention/
               moderation/digest are later slices.
        recipient_user_ids: pks of the Users to email.
        data: the shared payload dict — carries "post_id" (str). The reply Post
              is fetched here (once for the batch) so push's data stays minimal
              and the email reflects the post at send time.
    """
    if event != "reply_added":
        logger.debug(
            "[EMAIL] forum email skipped — event=%s not implemented yet", event
        )
        return

    if not recipient_user_ids:
        return

    from apps.core.services.notification_service import NotificationService
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from wagtail_forum.api.views import plain_text_excerpt
    from wagtail_forum.models import Post

    from .constants import FORUM_EMAIL_EXCERPT_MAX_CHARS

    User = get_user_model()

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

    # Materialize up front so a transient OperationalError can only fire here,
    # before any email is sent (see the docstring's retry-safety note).
    users = list(User.objects.filter(pk__in=recipient_user_ids))

    topic = post.topic
    topic_url = f"{settings.SITE_URL}{topic.get_absolute_url()}"
    author_name = post.author.display_name if post.author else "[deleted]"
    excerpt = plain_text_excerpt(post.body, FORUM_EMAIL_EXCERPT_MAX_CHARS)
    service = NotificationService()

    for user in users:
        if not user.email:
            # Skip explicitly so a user with no email on file gets a clear skip
            # log here. (Belt-and-suspenders: since todo 267,
            # EmailService.send_email() also returns False rather than a phantom
            # True for a 0-recipient send — this guard just keeps the skip reason
            # legible at this layer.)
            logger.warning(
                "[EMAIL] forum email skipped — user %s has no email on file", user.pk
            )
            continue
        sent = service.send_forum_reply_notification(
            user=user,
            topic_title=topic.title,
            reply_author=author_name,
            reply_excerpt=excerpt,
            topic_url=topic_url,
        )
        logger.info("[EMAIL] forum.%s email to user=%s: sent=%s", event, user.pk, sent)
