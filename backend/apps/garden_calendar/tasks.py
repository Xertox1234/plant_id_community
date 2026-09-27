"""Celery tasks for garden_calendar: care-task reminders over FCM (todo 410).

A CareTask's ``scheduled_date`` is its reminder. The beat sweep below finds
tasks that fell due in the last ``CARE_REMINDER_LOOKBACK_HOURS``, claims them
by setting ``notification_sent``, and sends each plant owner one push for all
of their due tasks.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from apps.core.fcm import is_permanent_fcm_error, send_fcm_message
from celery import shared_task
from django.db import OperationalError, transaction
from django.utils import timezone

from .constants import (
    CARE_REMINDER_BATCH_SIZE,
    CARE_REMINDER_BODY_MAX_TASKS,
    CARE_REMINDER_COLLAPSE_KEY,
    CARE_REMINDER_EVENT,
    CARE_REMINDER_LOOKBACK_HOURS,
    CARE_REMINDER_TITLE_MAX_CHARS,
)

logger = logging.getLogger(__name__)

# A sweep sends one push per owner with due tasks, one after another.
CARE_REMINDER_SOFT_TIME_LIMIT = 4 * 60
CARE_REMINDER_TIME_LIMIT = 5 * 60


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _reminder_content(tasks: list[dict]) -> tuple[str, str]:
    """The tray (title, body) for one owner's due tasks."""
    if len(tasks) == 1:
        task = tasks[0]
        title = _truncate(task["title"] or "Plant care", CARE_REMINDER_TITLE_MAX_CHARS)
        return title, f"{task['plant__common_name']} is due for care."
    shown = [
        _truncate(t["title"] or t["plant__common_name"], CARE_REMINDER_TITLE_MAX_CHARS)
        for t in tasks[:CARE_REMINDER_BODY_MAX_TASKS]
    ]
    more = len(tasks) - len(shown)
    body = ", ".join(shown) + (f" and {more} more" if more else "")
    return f"{len(tasks)} plant care tasks are due", body


def _claim_due_tasks(now) -> list[dict]:
    """Mark a batch of due tasks as notified and return them.

    ``skip_locked`` keeps two overlapping sweeps from claiming the same rows,
    so a task is pushed at most once. Claiming before sending means a crash
    mid-send loses that reminder rather than sending it twice.
    """
    from .models import CareTask

    with transaction.atomic():
        claimed = list(
            CareTask.objects.select_for_update(skip_locked=True, of=("self",))
            .filter(
                scheduled_date__lte=now,
                scheduled_date__gte=now - timedelta(hours=CARE_REMINDER_LOOKBACK_HOURS),
                completed=False,
                skipped=False,
                notification_sent=False,
                plant__is_active=True,
            )
            .order_by("scheduled_date")
            .values(
                "uuid",
                "title",
                "plant_id",
                "plant__common_name",
                "plant__owner_id",
            )[:CARE_REMINDER_BATCH_SIZE]
        )
        if claimed:
            CareTask.objects.filter(uuid__in=[t["uuid"] for t in claimed]).update(
                notification_sent=True
            )
    return claimed


def _release(tasks: list[dict]) -> None:
    """Un-claim tasks after a transient send failure, so the next sweep retries."""
    from .models import CareTask

    CareTask.objects.filter(uuid__in=[t["uuid"] for t in tasks]).update(
        notification_sent=False
    )


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    max_retries=3,
    soft_time_limit=CARE_REMINDER_SOFT_TIME_LIMIT,
    time_limit=CARE_REMINDER_TIME_LIMIT,
    ignore_result=True,
)
def send_due_care_task_reminders() -> None:
    """Celery beat entry (settings.CELERY_BEAT_SCHEDULE): push due CareTasks.

    Delivery is FCM only (owner decision 2026-09-24). The device token lives
    on the forum profile, which the mobile app registers at every sign-in
    (``push_registration_service.dart``), forum use or not. The opt-out is
    ``User.care_reminder_notifications``.
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from django.contrib.auth import get_user_model
    from wagtail_forum.models import ForumProfile

    if not is_firebase_available():
        # Nothing is claimed, so enabling Firebase later still delivers the
        # tasks that fell due within the lookback window.
        logger.debug("[FCM] Firebase not configured — skipping care reminders")
        return

    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot send care reminders")
        return

    claimed = _claim_due_tasks(timezone.now())
    if not claimed:
        return

    by_owner: dict[int, list[dict]] = defaultdict(list)
    for task in claimed:
        by_owner[task["plant__owner_id"]].append(task)

    User = get_user_model()
    opted_in = set(
        User.objects.filter(
            pk__in=by_owner, care_reminder_notifications=True, is_active=True
        ).values_list("pk", flat=True)
    )
    tokens = dict(
        ForumProfile.objects.filter(user_id__in=opted_in)
        .exclude(fcm_token="")
        .values_list("user_id", "fcm_token")
    )

    sent = released = 0
    for owner_id, tasks in by_owner.items():
        token = tokens.get(owner_id)
        if not token:
            # Opted out, or no device registered: the claim stands, so the
            # task is not re-examined every sweep.
            continue
        first = tasks[0]
        data = {
            "event": CARE_REMINDER_EVENT,
            "care_task_uuid": str(first["uuid"]),
            "plant_uuid": str(first["plant_id"]),
            "count": str(len(tasks)),
        }
        try:
            send_fcm_message(
                fcm, token, data, _reminder_content(tasks), CARE_REMINDER_COLLAPSE_KEY
            )
            sent += 1
        except Exception as exc:
            if is_permanent_fcm_error(exc):
                logger.warning(
                    "[FCM] care reminder failed permanently (user=%s): %s",
                    owner_id,
                    exc,
                )
                continue
            logger.warning(
                "[FCM] care reminder failed (user=%s): %s — released for the "
                "next sweep",
                owner_id,
                exc,
            )
            _release(tasks)
            released += 1

    logger.info(
        "[FCM] care reminders: %s tasks claimed, %s pushes sent, %s owners "
        "released for retry",
        len(claimed),
        sent,
        released,
    )
