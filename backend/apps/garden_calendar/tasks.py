"""Celery tasks for garden_calendar: care-task reminders over FCM (todo 410).

A CareTask's ``scheduled_date`` is its reminder. The beat sweep below finds
tasks that fell due in the last ``CARE_REMINDER_LOOKBACK_HOURS``, claims them
by setting ``notification_sent``, and sends each plant owner one push for all
of their due tasks.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from apps.core.fcm import (
    FCM_CREDENTIALS_STOP_FAILURES,
    clear_dead_fcm_token,
    is_dead_fcm_token_error,
    is_fcm_credentials_error,
    is_permanent_fcm_error,
    send_fcm_message,
)
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError, transaction
from django.utils import timezone

from .constants import (
    CARE_REMINDER_BATCH_SIZE,
    CARE_REMINDER_BODY_MAX_TASKS,
    CARE_REMINDER_COLLAPSE_KEY,
    CARE_REMINDER_EVENT,
    CARE_REMINDER_LOOKBACK_HOURS,
    CARE_REMINDER_SOFT_TIME_LIMIT,
    CARE_REMINDER_SWEEP_INTERVAL_MINUTES,
    CARE_REMINDER_TIME_LIMIT,
    CARE_REMINDER_TITLE_MAX_CHARS,
)

logger = logging.getLogger(__name__)


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


def _claim_due_tasks(now: datetime) -> list[dict]:
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
                "scheduled_date",
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


def _release(
    tasks: list[dict],
    now: datetime,
    task_id: str | None,
    *,
    next_claim_within: timedelta = timedelta(
        minutes=CARE_REMINDER_SWEEP_INTERVAL_MINUTES
    ),
) -> None:
    """Un-claim tasks after a transient send failure, so the next sweep retries.

    A released task is re-claimed every sweep only while it is inside the
    lookback window; after that no sweep selects it again. Warn when this is
    its last chance, so a reminder that keeps failing is not dropped silently
    (todo 457). ``next_claim_within`` is when the next claim runs at the
    latest: the next beat sweep by default, or this task's own autoretry,
    which comes sooner (todo 566). A task that leaves the window before
    either claims it is warned about either way (todo 593 #2).
    """
    from .models import CareTask

    CareTask.objects.filter(uuid__in=[t["uuid"] for t in tasks]).update(
        notification_sent=False
    )
    ages_out_before = (
        now - timedelta(hours=CARE_REMINDER_LOOKBACK_HOURS) + next_claim_within
    )
    for task in tasks:
        if task["scheduled_date"] < ages_out_before:
            logger.warning(
                "[FCM] care reminder for task %s (user=%s) leaves the %sh "
                "lookback before the next claim; it will not be sent (task=%s)",
                task["uuid"],
                task["plant__owner_id"],
                CARE_REMINDER_LOOKBACK_HOURS,
                task_id,
            )


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=60,
    max_retries=3,
    soft_time_limit=CARE_REMINDER_SOFT_TIME_LIMIT,
    time_limit=CARE_REMINDER_TIME_LIMIT,
    ignore_result=True,
)
def send_due_care_task_reminders(self) -> None:
    """Celery beat entry (settings.CELERY_BEAT_SCHEDULE): push due CareTasks.

    Delivery is FCM only (owner decision 2026-09-24). The device token lives
    on the forum profile, which the mobile app registers at every sign-in
    (``push_registration_service.dart``), forum use or not. The opt-out is
    ``User.care_reminder_notifications``.
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available

    task_id = self.request.id
    if not is_firebase_available():
        # Nothing is claimed, so enabling Firebase later still delivers the
        # tasks that fell due within the lookback window.
        logger.debug("[FCM] Firebase not configured — skipping care reminders")
        return

    fcm = get_fcm_client()
    if fcm is None:
        logger.error(
            "[FCM] FCM client unavailable — cannot send care reminders (task=%s)",
            task_id,
        )
        return

    now = timezone.now()
    claimed = _claim_due_tasks(now)
    if not claimed:
        return

    by_owner: dict[int, list[dict]] = defaultdict(list)
    for task in claimed:
        by_owner[task["plant__owner_id"]].append(task)

    # Everything after the claim runs under this guard. The claim is already
    # committed, so an escape (a DB blip that autoretry would re-run, or the
    # soft time limit) must un-claim every owner not yet handled; otherwise the
    # retry's claim cannot see those rows and they never push.
    done: set[int] = set()
    retry_later: list[dict] = []
    try:
        sent = _push_to_owners(fcm, by_owner, done, retry_later, task_id)
        if retry_later:
            _release(retry_later, now, task_id)
    except BaseException as exc:  # re-raised below; a worker shutdown must un-claim too
        unfinished = [t for o, ts in by_owner.items() if o not in done for t in ts]
        try:
            _release(
                unfinished + retry_later,
                now,
                task_id,
                next_claim_within=_next_claim_within(self, exc),
            )
        except Exception:
            logger.exception(
                "[FCM] care reminders: could not release %s claimed tasks; "
                "they will not push (task=%s)",
                len(unfinished) + len(retry_later),
                task_id,
            )
        raise

    logger.info(
        "[FCM] care reminders: %s tasks claimed, %s pushes sent, %s tasks "
        "released for retry (task=%s)",
        len(claimed),
        sent,
        len(retry_later),
        task_id,
    )


def _next_claim_within(task: Any, exc: BaseException) -> timedelta:
    """How soon the next claim runs after ``exc`` escapes ``task``.

    Read from the task's own autoretry options, so a change to the decorator
    cannot leave a hand-kept copy behind (todo 593 #2). An exception autoretry
    re-runs, with retries left, comes back within the backoff ceiling (the
    jittered countdown never exceeds it) plus a minute of queue latency;
    anything else waits for the next beat sweep.
    """
    from celery.utils.time import get_exponential_backoff_interval

    autoretry_for = tuple(getattr(task, "autoretry_for", ()))
    backoff = getattr(task, "retry_backoff", False)
    if (
        autoretry_for
        and backoff
        and isinstance(exc, autoretry_for)
        and task.request.retries < task.max_retries
    ):
        countdown = get_exponential_backoff_interval(
            factor=int(max(1.0, float(backoff))),
            retries=task.request.retries,
            maximum=int(getattr(task, "retry_backoff_max", 600)),
            full_jitter=False,
        )
        return timedelta(seconds=countdown + 60)
    return timedelta(minutes=CARE_REMINDER_SWEEP_INTERVAL_MINUTES)


def _push_to_owners(
    fcm: Any,
    by_owner: dict[int, list[dict]],
    done: set[int],
    retry_later: list[dict],
    task_id: str | None = None,
) -> int:
    """Send one push per owner; returns the number sent.

    Adds each handled owner to ``done`` and a transient failure's tasks to
    ``retry_later``, so the caller can un-claim exactly what did not go out.
    A credentials error leaves that owner's claim standing and keeps going.
    The sweep stops only after ``FCM_CREDENTIALS_STOP_FAILURES`` of them with
    no successful send yet: then every untried owner with a token moves to
    ``retry_later`` (todo 593 round 3). Either way the sweep logs one ERROR.
    """
    from django.contrib.auth import get_user_model
    from wagtail_forum.models import ForumProfile

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

    sent = 0
    credentials_failed: list[int] = []
    for owner_id, tasks in by_owner.items():
        token = tokens.get(owner_id)
        if not token:
            # Opted out, or no device registered: the claim stands, so the
            # task is not re-examined every sweep.
            done.add(owner_id)
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
        except SoftTimeLimitExceeded:
            # Not an FCM failure: stop, and let the caller un-claim the rest.
            raise
        except Exception as exc:
            if is_fcm_credentials_error(exc):
                # Keep the token: clearing it would wipe a healthy device on a
                # server misconfiguration (todo 566). The claim stands, as for
                # a tokenless owner: the error can be the device's (a
                # dev-build token, an APNs-only fault), and a released task is
                # re-claimed oldest-first, so it would head every sweep.
                done.add(owner_id)
                credentials_failed.append(owner_id)
                logger.warning(
                    "[FCM] care reminder hit a Firebase credentials error "
                    "(user=%s, task=%s): %s — token kept, claim stands",
                    owner_id,
                    task_id,
                    exc,
                )
                if (
                    not sent
                    and len(credentials_failed) >= FCM_CREDENTIALS_STOP_FAILURES
                ):
                    # No send has worked yet: the server's setup, where every
                    # later send fails the same way (owner decision
                    # 2026-10-11, todo 593 round 3). Release the untried
                    # owners who have a token; a tokenless owner's claim
                    # stands as it would have. The failed owners' claims
                    # stand too: released, they would be re-claimed first and
                    # stop the next sweep again, so a few bad devices could
                    # starve everyone until the lookback. Holding them makes
                    # each sweep move on; a real outage costs at most this
                    # many owners' reminders per sweep, named in the ERROR.
                    pending = [
                        t
                        for o, ts in by_owner.items()
                        if o not in done and o in tokens
                        for t in ts
                    ]
                    retry_later.extend(pending)
                    done.update(by_owner)
                    logger.error(
                        "[FCM] care reminders failed permanently on a Firebase "
                        "credentials error for %s owners with no successful "
                        "send (users=%s, task=%s): %s — stopping the sweep; "
                        "their claims stand, %s untried tasks released for "
                        "the next one",
                        len(credentials_failed),
                        credentials_failed,
                        task_id,
                        exc,
                        len(pending),
                    )
                    return sent
                continue
            if is_permanent_fcm_error(exc):
                if is_dead_fcm_token_error(exc):
                    # Forget the dead device, so the next sweep does not
                    # send to it again (todo 457).
                    clear_dead_fcm_token(owner_id, token)
                logger.warning(
                    "[FCM] care reminder failed permanently (user=%s, task=%s): %s",
                    owner_id,
                    task_id,
                    exc,
                )
            else:
                logger.warning(
                    "[FCM] care reminder failed (user=%s, task=%s): %s — "
                    "released for the next sweep",
                    owner_id,
                    task_id,
                    exc,
                )
                retry_later.extend(tasks)
        done.add(owner_id)
    if credentials_failed:
        logger.error(
            "[FCM] care reminders failed permanently on a Firebase credentials "
            "error for %s owner(s) (users=%s, task=%s) — tokens kept, claims "
            "stand",
            len(credentials_failed),
            credentials_failed,
            task_id,
        )
    return sent
