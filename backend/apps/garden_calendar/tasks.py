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
from apps.core.notification_ops import Outcome, log_outcomes, report_push_unconfigured
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


def _due_tasks(now: datetime):
    """Unclaimed CareTasks due within the lookback window."""
    from .models import CareTask

    return CareTask.objects.filter(
        scheduled_date__lte=now,
        scheduled_date__gte=now - timedelta(hours=CARE_REMINDER_LOOKBACK_HOURS),
        completed=False,
        skipped=False,
        notification_sent=False,
        plant__is_active=True,
    )


def _claim_due_tasks(now: datetime) -> list[dict]:
    """Mark a batch of due tasks as notified and return them.

    ``skip_locked`` keeps two overlapping sweeps from claiming the same rows,
    so a task is pushed at most once. Claiming before sending means a crash
    mid-send loses that reminder rather than sending it twice.
    """
    from .models import CareTask

    with transaction.atomic():
        claimed = list(
            _due_tasks(now)
            .select_for_update(skip_locked=True, of=("self",))
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

    Delivery is FCM only (owner decision 2026-09-24), to every device the
    owner registered (``apps.core.push_devices``, todo 621), which the mobile
    app does at every sign-in (``push_registration_service.dart``), forum use
    or not. The opt-out is ``User.care_reminder_notifications``.
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available

    task_id = self.request.id
    if not is_firebase_available():
        # Nothing is claimed, so enabling Firebase later still delivers the
        # tasks that fell due within the lookback window. An alert only when
        # a reminder is actually due (todo 623): no ERROR every 15 minutes on
        # a deployment with nothing to send.
        if _due_tasks(timezone.now()).exists():
            report_push_unconfigured("FCM", "due care reminders")
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
    outcomes: dict[int, str] = {}
    try:
        sent = _push_to_owners(
            fcm, by_owner, done, retry_later, task_id, outcomes=outcomes
        )
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
    # Per owner, in the shared vocabulary (todo 623). "accepted" is FCM
    # taking the message, not the device showing it.
    for task in retry_later:
        outcomes[task["plant__owner_id"]] = Outcome.RETRYING
    tally = dict.fromkeys(
        (Outcome.ACCEPTED, Outcome.RETRYING, Outcome.FAILED, Outcome.SUPPRESSED), 0
    )
    for outcome in outcomes.values():
        tally[outcome] += 1
    log_outcomes("push", "care_reminder", **tally)


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
    outcomes: dict[int, str] | None = None,
) -> int:
    """Send one push per owner, to each of their devices; returns the number
    of owners at least one device reached.

    Adds each handled owner to ``done`` and a transient failure's tasks to
    ``retry_later``, so the caller can un-claim exactly what did not go out.
    Records each handled owner's outcome (``notification_ops.Outcome``) in
    ``outcomes`` when given (todo 623).

    A credentials error leaves that owner's claim standing and keeps going.
    The sweep stops only after ``FCM_CREDENTIALS_STOP_FAILURES`` of them with
    no successful send yet: then every untried owner with a token moves to
    ``retry_later`` (todo 593 round 3). Either way the sweep logs one ERROR.
    """
    from apps.core.push_devices import device_tokens_for_users
    from django.contrib.auth import get_user_model

    User = get_user_model()
    opted_in = set(
        User.objects.filter(
            pk__in=by_owner, care_reminder_notifications=True, is_active=True
        ).values_list("pk", flat=True)
    )
    # Every device of each owner (todo 621), legacy token included.
    tokens = device_tokens_for_users(opted_in)

    if outcomes is None:
        outcomes = {}
    sent = 0
    credentials_failed: list[int] = []
    for owner_id, tasks in by_owner.items():
        devices = tokens.get(owner_id)
        if not devices:
            # Opted out, or no device registered: the claim stands, so the
            # task is not re-examined every sweep.
            outcomes[owner_id] = Outcome.SUPPRESSED
            done.add(owner_id)
            continue
        first = tasks[0]
        data = {
            "event": CARE_REMINDER_EVENT,
            "care_task_uuid": str(first["uuid"]),
            "plant_uuid": str(first["plant_id"]),
            "count": str(len(tasks)),
        }
        content = _reminder_content(tasks)
        owner_sent = 0
        owner_credentials_exc: Exception | None = None
        transient: list[str] = []
        for token in devices:
            try:
                send_fcm_message(fcm, token, data, content, CARE_REMINDER_COLLAPSE_KEY)
                owner_sent += 1
            except SoftTimeLimitExceeded:
                # Not an FCM failure: stop, and let the caller un-claim the
                # rest. An owner with a device already sent counts as done,
                # so the retry does not send to that device twice.
                if owner_sent:
                    done.add(owner_id)
                raise
            except Exception as exc:
                if is_fcm_credentials_error(exc):
                    # Keep the token: clearing it would wipe a healthy device
                    # on a server misconfiguration (todo 566).
                    owner_credentials_exc = exc
                    logger.warning(
                        "[FCM] care reminder hit a Firebase credentials error "
                        "(user=%s, task=%s): %s — token kept",
                        owner_id,
                        task_id,
                        exc,
                    )
                elif is_permanent_fcm_error(exc):
                    if is_dead_fcm_token_error(exc):
                        # Forget that device only, so the next sweep does not
                        # send to it again (todos 457, 621).
                        clear_dead_fcm_token(owner_id, token)
                    logger.warning(
                        "[FCM] care reminder failed permanently (user=%s, "
                        "task=%s): %s",
                        owner_id,
                        task_id,
                        exc,
                    )
                else:
                    logger.warning(
                        "[FCM] care reminder failed (user=%s, task=%s): %s",
                        owner_id,
                        task_id,
                        exc,
                    )
                    transient.append(token)
        sent += 1 if owner_sent else 0
        outcomes[owner_id] = (
            Outcome.ACCEPTED
            if owner_sent
            else Outcome.RETRYING if transient else Outcome.FAILED
        )
        if transient:
            if len(transient) == len(devices):
                # No device got it and none failed for good: release the
                # owner's tasks for the next sweep, as for a one-device owner.
                logger.warning(
                    "[FCM] care reminder for user=%s released for the next "
                    "sweep (task=%s)",
                    owner_id,
                    task_id,
                )
                retry_later.extend(tasks)
            else:
                # Another device got it, or failed for good: releasing would
                # re-send to those. Retry each failed device alone instead
                # (todo 621).
                for token in transient:
                    _retry_device_later(owner_id, token, data, content, task_id)
        if owner_credentials_exc is not None and not owner_sent:
            # The claim stands, as for a tokenless owner: the error can be
            # the device's (a dev-build token, an APNs-only fault), and a
            # released task is re-claimed oldest-first, so it would head
            # every sweep.
            credentials_failed.append(owner_id)
            if not sent and len(credentials_failed) >= FCM_CREDENTIALS_STOP_FAILURES:
                # No send has worked yet: the server's setup, where every
                # later send fails the same way (owner decision 2026-10-11,
                # todo 593 round 3). Release the untried owners who have a
                # token; a tokenless owner's claim stands as it would have.
                # The failed owners' claims stand too: released, they would
                # be re-claimed first and stop the next sweep again, so a few
                # bad devices could starve everyone until the lookback.
                # Holding them makes each sweep move on; a real outage costs
                # at most this many owners' reminders per sweep, named in the
                # ERROR.
                done.add(owner_id)
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
                    owner_credentials_exc,
                    len(pending),
                )
                return sent
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


def _retry_device_later(
    owner_id: int,
    token: str,
    data: dict[str, str],
    content: tuple[str, str],
    task_id: str | None,
) -> None:
    """Enqueue one device's retry; a refused enqueue is logged, not raised.

    Runs inside the sweep's send loop, where an escape would un-claim every
    owner not yet handled; a broker hiccup must not do that.
    """
    try:
        send_care_reminder_to_device.delay(owner_id, token, data, list(content))
    except Exception as exc:
        logger.warning(
            "[FCM] care reminder retry for one device of user=%s could not be "
            "enqueued (task=%s): %s — that device misses this reminder",
            owner_id,
            task_id,
            exc,
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_care_reminder_to_device(
    self, owner_id: int, token: str, data: dict, content: list[str]
) -> None:
    """Retry one care reminder to ONE device (todo 621).

    The sweep hands a device here when it failed transiently and another
    device of the owner got the reminder (or failed for good), so the
    sweep's own release, which re-sends to every device, would duplicate
    it. Skipped when the owner opted out since, or the token is no longer
    theirs. Backoff 30s, 60s, 120s; permanent failures are not retried.
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from apps.core.push_devices import is_registered
    from django.contrib.auth import get_user_model

    if not is_firebase_available():
        return
    User = get_user_model()
    if not User.objects.filter(
        pk=owner_id, care_reminder_notifications=True, is_active=True
    ).exists():
        return
    if not is_registered(owner_id, token):
        return
    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot retry a care reminder")
        return
    title, body = content
    try:
        send_fcm_message(fcm, token, data, (title, body), CARE_REMINDER_COLLAPSE_KEY)
    except Exception as exc:
        if is_permanent_fcm_error(exc):
            if is_dead_fcm_token_error(exc):
                clear_dead_fcm_token(owner_id, token)
            logger.log(
                logging.ERROR if is_fcm_credentials_error(exc) else logging.WARNING,
                "[FCM] care reminder retry failed permanently (user=%s, "
                "task_id=%s): %s",
                owner_id,
                self.request.id,
                exc,
            )
            return
        logger.warning(
            "[FCM] care reminder retry failed (user=%s, task_id=%s): %s — retrying",
            owner_id,
            self.request.id,
            exc,
        )
        raise self.retry(
            exc=exc, countdown=self.default_retry_delay * (2**self.request.retries)
        )
