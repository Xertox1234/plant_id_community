"""FCM send helpers shared by every push feature (forum, care reminders).

Lifted out of ``apps/forum_host/tasks.py`` for todo 410, so the care-reminder
sweep in ``garden_calendar`` does not import the forum's private helpers.
"""

from typing import Any


def is_permanent_fcm_error(exc: Exception) -> bool:
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


def send_fcm_message(
    fcm: Any,
    token: str,
    str_data: dict[str, str],
    content: tuple[str, str] | None,
    collapse_key: str,
) -> str:
    """Build and send one FCM message (data payload + optional tray notification).

    ``content`` is a (title, body) pair, or None for a data-only message. The
    collapse key makes a retry after an accepted-but-timed-out send REPLACE the
    tray entry instead of stacking a duplicate; FCM keeps at most 4 collapse
    keys pending per offline device, so keep them per event type, not per
    object (docs/rules/celery.md). Raises on send failure; the caller classifies
    it with ``is_permanent_fcm_error`` and decides whether to retry.
    """
    message_kwargs: dict[str, Any] = {"data": str_data, "token": token}
    if content is not None:
        title, body = content
        message_kwargs["notification"] = fcm.Notification(title=title, body=body)
        message_kwargs["android"] = fcm.AndroidConfig(collapse_key=collapse_key)
        message_kwargs["apns"] = fcm.APNSConfig(
            headers={"apns-collapse-id": collapse_key}
        )
    return fcm.send(fcm.Message(**message_kwargs))
