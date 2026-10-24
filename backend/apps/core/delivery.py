"""The delivery outbox: durable intent, per-recipient claims, reconciliation
(todo 619).

Why
---
A Celery ``.delay()`` after commit is not durable: a broker refusal, a
message stranded in a dying worker's prefetch, or a send that reports
failure used to lose the delivery for good (a log line was all that was
left). Each delivery that must survive that is now a ``DeliveryIntent`` row,
written in the same transaction as its event.

Contract
--------
- **Record.** ``record_batch`` (forum fan-out, one row per recipient) and
  ``record_one`` (account mail) write ``pending`` rows due for
  reconciliation only after ``DELIVERY_GRACE_SECONDS``: the normal enqueue
  gets there first. A forum row is unique per (kind, event, post,
  recipient), so a duplicate dispatch inserts nothing and its batch claims
  nothing.
- **Claim.** A worker claims rows with one conditional UPDATE
  (``pending``, or ``claimed`` past the lease, to ``claimed`` + a fresh
  token), then sends only to the rows that UPDATE matched. Two workers
  racing on a row cannot both match it: PostgreSQL re-evaluates the WHERE on
  the locked row. Each claim counts an attempt. A task ignores
  ``next_attempt_at`` (a Celery retry runs on its own countdown);
  reconciliation honours it.
- **Outcome.** ``mark_sent`` / ``mark_suppressed`` (no longer eligible:
  opted out, blocked, hidden content, no address) / ``mark_failed``
  (permanent: rejected address, gone subscription) are terminal.
  ``mark_retry`` (transient: connection, timeout, 4xx SMTP) puts the row
  back to ``pending`` with exponential backoff, and makes it terminal at
  ``DELIVERY_MAX_ATTEMPTS``. A sent row is never claimed again, so a retry
  or re-drive sends only to the recipients that did not get it.
- **Reopen.** The one exception: ``record_reaccept`` puts a finished forum
  row back to ``pending`` under a new batch, at most once per
  ``FORUM_REACCEPT_COOLDOWN_SECONDS`` (an answer accepted again, todo 652).
  The old batch's task can no longer claim it. The earlier outcome is
  overwritten in place.
- **Hold.** ``mark_held`` puts a claimed row back to ``pending`` until a
  release time without spending an attempt: a quiet-hours or coalescing hold
  (todo 624) is not a failure. Reconciliation re-drives it once due, and
  never expires a row whose hold has not ended yet.
- **Reconcile.** ``reconcile()`` (beat, ``apps.core.tasks``) expires rows
  older than ``DELIVERY_MAX_AGE_SECONDS``, re-drives due ``pending`` rows
  and ``claimed`` rows whose lease ran out (the worker died) through each
  kind's redriver, and prunes finished rows after
  ``DELIVERY_RETENTION_DAYS``. It never charges a verification allowance:
  recovery belongs to the request that already paid for it.

At-least-once, not exactly-once
-------------------------------
SMTP and the push services give no idempotency key we can use, so the
outcome write after a send is the only record that it happened. A worker
killed (or a database write lost) between the provider accepting a message
and ``mark_sent`` leaves the row ``claimed``; after the lease it is re-driven
and that one recipient gets the message twice. The window is one send per
interrupted worker, and the alternative, dropping a message nobody can
prove was sent, is worse for account mail. Batch kinds that mark outcomes in
bulk after the loop (browser push) widen that window to the batch; a
browser replaces a notification with the same ``tag``, so a repeat shows
once.
"""

import logging
import sys
import uuid
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, F, Q, Value, When
from django.db.models.functions import Greatest
from django.utils import timezone
from django.utils.module_loading import import_string

from . import constants
from .models import DeliveryIntent
from .notification_ops import check_outbox_lag, log_outcomes, summary_counts

logger = logging.getLogger("apps.core.delivery")

Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status

# Each kind's redriver: called by reconcile() with that kind's due rows.
REDRIVERS: dict[str, str] = {
    Kind.FORUM_EMAIL: "apps.forum_host.tasks.redrive_forum_deliveries",
    Kind.FORUM_WEB_PUSH: "apps.forum_host.tasks.redrive_forum_deliveries",
    Kind.FORUM_PUSH: "apps.forum_host.tasks.redrive_forum_deliveries",
    Kind.VERIFICATION_EMAIL: "apps.users.tasks.redrive_verification_emails",
    Kind.NEWSLETTER_CONFIRMATION: "apps.blog.tasks.redrive_newsletter_confirmations",
    Kind.LOCKOUT_EMAIL: "apps.users.tasks.redrive_lockout_emails",
}

# A held row's ``last_error`` (todo 624): why it is waiting, not a failure.
HOLD_QUIET_HOURS = "quiet_hours"
HOLD_COALESCING = "coalescing"
HOLDS = (HOLD_QUIET_HOURS, HOLD_COALESCING)

_OPEN = (Status.PENDING, Status.CLAIMED)
_FINISHED = (Status.SENT, Status.SUPPRESSED, Status.FAILED)


def _claimable(now) -> Q:
    lease_cut = now - timedelta(seconds=constants.DELIVERY_CLAIM_LEASE_SECONDS)
    return Q(status=Status.PENDING) | Q(status=Status.CLAIMED, claimed_at__lt=lease_cut)


def _due(now) -> Q:
    lease_cut = now - timedelta(seconds=constants.DELIVERY_CLAIM_LEASE_SECONDS)
    return Q(status=Status.PENDING, next_attempt_at__lte=now) | Q(
        status=Status.CLAIMED, claimed_at__lt=lease_cut
    )


# --- record --------------------------------------------------------------------


def record_batch(
    kind, event, recipient_ids, payload, *, subject_key, due_at=None, reason=""
) -> str | None:
    """One pending row per recipient, in the caller's transaction. Returns
    the batch id to pass to the task, or None when there is no recipient.

    ``due_at`` is when reconciliation may first re-drive the rows (default:
    after ``DELIVERY_GRACE_SECONDS``); a held delivery passes its release
    time, with ``reason`` naming the hold."""
    ids = list(dict.fromkeys(int(pk) for pk in recipient_ids))
    if not ids:
        return None
    batch_id = uuid.uuid4()
    due = due_at or timezone.now() + timedelta(seconds=constants.DELIVERY_GRACE_SECONDS)
    DeliveryIntent.objects.bulk_create(
        [
            DeliveryIntent(
                kind=kind,
                event=str(event),
                recipient_id=pk,
                subject_key=str(subject_key),
                batch_id=batch_id,
                payload=dict(payload),
                next_attempt_at=due,
                last_error=str(reason)[:64],
            )
            for pk in ids
        ],
        ignore_conflicts=True,
    )
    return str(batch_id)


def record_one(
    kind, *, recipient_id=None, subject_key="", event="", payload=None
) -> DeliveryIntent:
    """A pending row for one message, reusing one already pending for the
    same kind, recipient and subject: requests that pile up while the broker
    is down recover as one message, not one each."""
    existing = (
        DeliveryIntent.objects.filter(
            kind=kind,
            recipient_id=recipient_id,
            subject_key=str(subject_key),
            status=Status.PENDING,
        )
        .order_by("pk")
        .first()
    )
    if existing is not None:
        return existing
    return DeliveryIntent.objects.create(
        kind=kind,
        event=str(event),
        recipient_id=recipient_id,
        subject_key=str(subject_key),
        payload=dict(payload or {}),
        next_attempt_at=timezone.now()
        + timedelta(seconds=constants.DELIVERY_GRACE_SECONDS),
    )


# --- claim ---------------------------------------------------------------------


def _claim(queryset, now) -> uuid.UUID | None:
    token = uuid.uuid4()
    claimed = queryset.filter(_claimable(now)).update(
        status=Status.CLAIMED,
        claim_token=token,
        claimed_at=now,
        attempts=F("attempts") + 1,
    )
    return token if claimed else None


def claim_batch(kind, batch_id, recipient_ids) -> dict[int, int]:
    """Claim this batch's rows for ``recipient_ids``: {recipient pk: row pk}
    for the rows this worker now owns. Empty when another worker holds them
    or they are finished. Two queries, whatever the recipient count."""
    ids = [int(pk) for pk in recipient_ids]
    if not batch_id or not ids:
        return {}
    now = timezone.now()
    token = _claim(
        DeliveryIntent.objects.filter(
            kind=kind, batch_id=batch_id, recipient_id__in=ids
        ),
        now,
    )
    if token is None:
        return {}
    return dict(
        DeliveryIntent.objects.filter(claim_token=token).values_list(
            "recipient_id", "pk"
        )
    )


def claim_one(kind=None, *, intent_id=None, recipient_id=None) -> DeliveryIntent | None:
    """Claim one row: by ``intent_id``, or the oldest open row of ``kind`` for
    ``recipient_id``. None when there is nothing to claim."""
    now = timezone.now()
    if intent_id is not None:
        queryset = DeliveryIntent.objects.filter(pk=intent_id)
    else:
        candidate = (
            DeliveryIntent.objects.filter(kind=kind, recipient_id=recipient_id)
            .filter(_claimable(now))
            .order_by("pk")
            .values_list("pk", flat=True)
            .first()
        )
        if candidate is None:
            return None
        queryset = DeliveryIntent.objects.filter(pk=candidate)
    token = _claim(queryset, now)
    if token is None:
        return None
    return DeliveryIntent.objects.filter(claim_token=token).first()


def claim_related(kind, event, recipient_id, topic_id, *, exclude) -> dict[int, str]:
    """Claim the other open rows of ``kind`` and ``event`` for one recipient
    on one topic (a coalescing fold, todo 624): {row pk: subject key}.
    Ignores ``next_attempt_at``, like every claim: a row still waiting out
    its own window is folded into this send rather than sent after it."""
    now = timezone.now()
    queryset = DeliveryIntent.objects.filter(
        kind=kind,
        event=str(event),
        recipient_id=recipient_id,
        payload__topic_id=str(topic_id),
    ).exclude(pk__in=list(exclude))
    token = _claim(queryset, now)
    if token is None:
        return {}
    return dict(
        DeliveryIntent.objects.filter(claim_token=token).values_list(
            "pk", "subject_key"
        )
    )


def has_any(kind, recipient_id) -> bool:
    """Whether ``recipient_id`` has any row of ``kind``: a task that finds
    nothing to claim tells "another worker has it, or it went out" (rows
    exist) from "enqueued before the outbox existed" (none)."""
    return DeliveryIntent.objects.filter(kind=kind, recipient_id=recipient_id).exists()


REACCEPT_COOLING = "cooling"


def record_reaccept(
    kind: str,
    event: str,
    recipient_id: int,
    payload: dict,
    *,
    subject_key: str | int,
) -> str | None:
    """``record_batch`` for an event that may legitimately happen again on the
    same post, an answer accepted, cleared and accepted again (todo 652).

    The forum unique key would swallow the second acceptance's row (ON
    CONFLICT DO NOTHING). So a FINISHED row (sent, suppressed or failed) is
    reopened as pending under a new batch, and the send keeps the outbox's
    pacing, quiet hours and retries. A row recorded, reopened or finished
    within ``FORUM_REACCEPT_COOLDOWN_SECONDS`` is not (the later of
    ``created_at`` and ``updated_at``, so a row held for hours and sent late
    still counts from its send): toggling an acceptance never floods the
    answerer's browser or inbox. The phone push is outside the outbox and
    unchanged. The reopen resets ``created_at``, which reconciliation's max
    age measures from, so a reopened row is re-driven, never expired at once. Returns the batch id, or
    ``REACCEPT_COOLING`` when
    the caller must not send on this channel. A row still pending or claimed
    is the same acceptance in flight and dedups as before. In the caller's
    transaction."""
    now = timezone.now()
    row = (
        DeliveryIntent.objects.select_for_update()
        .filter(
            kind=kind,
            event=str(event),
            subject_key=str(subject_key),
            recipient_id=recipient_id,
        )
        .exclude(status__in=[Status.PENDING, Status.CLAIMED])
        .first()
    )
    if row is None:
        return record_batch(
            kind, event, [recipient_id], payload, subject_key=subject_key
        )
    if max(row.created_at, row.updated_at) > now - timedelta(
        seconds=constants.FORUM_REACCEPT_COOLDOWN_SECONDS
    ):
        return REACCEPT_COOLING
    batch_id = uuid.uuid4()
    DeliveryIntent.objects.filter(pk=row.pk).update(
        status=Status.PENDING,
        batch_id=batch_id,
        payload=dict(payload),
        attempts=0,
        next_attempt_at=now + timedelta(seconds=constants.DELIVERY_GRACE_SECONDS),
        claimed_at=None,
        claim_token=None,
        last_error="",
        created_at=now,
        updated_at=now,
    )
    return str(batch_id)


# --- outcome -------------------------------------------------------------------


def _finish(pks, status, reason="") -> int:
    pks = list(pks)
    if not pks:
        return 0
    # ``updated_at`` explicitly: a queryset update skips auto_now, and the
    # finish time is what reply coalescing measures its window from (todo
    # 624) and what retention prunes by.
    return DeliveryIntent.objects.filter(pk__in=pks).update(
        status=status,
        last_error=str(reason)[:64],
        claim_token=None,
        updated_at=timezone.now(),
    )


# A sent row whose message was handed to another task's retries rather than
# accepted by the provider (forum push, todo 624): finished, but not proof of
# delivery, so reply coalescing does not measure its window from it.
HANDED_OFF = "handed_off"


def mark_sent(pks, reason="") -> int:
    return _finish(pks, Status.SENT, reason)


def mark_suppressed(pks, reason="ineligible") -> int:
    return _finish(pks, Status.SUPPRESSED, reason)


def mark_suppressed_by_reason(rows_by_reason: dict) -> None:
    """{reason: [row pk, ...]} — one UPDATE per reason."""
    for reason, pks in rows_by_reason.items():
        mark_suppressed(pks, reason)


def mark_failed(pks, error="failed") -> int:
    return _finish(pks, Status.FAILED, error)


def mark_held(pks, release_at, reason=HOLD_QUIET_HOURS) -> int:
    """Hold claimed rows until ``release_at`` (todo 624): back to pending,
    due then, and the claim's attempt handed back, since a hold is not a
    failed attempt. Reconciliation re-drives them once due."""
    pks = list(pks)
    if not pks:
        return 0
    return DeliveryIntent.objects.filter(pk__in=pks).update(
        status=Status.PENDING,
        next_attempt_at=release_at,
        last_error=str(reason)[:64],
        claim_token=None,
        attempts=Greatest(F("attempts") - 1, Value(0)),
    )


def release(pks) -> int:
    """Hand claimed rows back untouched: pending, due as before, the
    claim's attempt returned. For a fold whose send did not go out."""
    pks = list(pks)
    if not pks:
        return 0
    return DeliveryIntent.objects.filter(pk__in=pks).update(
        status=Status.PENDING,
        claim_token=None,
        attempts=Greatest(F("attempts") - 1, Value(0)),
    )


def retry_delay(attempts: int) -> timedelta:
    """Backoff after ``attempts`` failed attempts: base, 2x, 4x, ..."""
    exponent = max(0, int(attempts) - 1)
    return timedelta(seconds=constants.DELIVERY_RETRY_BASE_SECONDS * 2**exponent)


def mark_retry(pks, error="transient") -> tuple[int, int]:
    """A transient failure: back to pending with backoff, or terminal once
    the attempts are spent. Returns (to retry, now failed)."""
    pks = list(pks)
    if not pks:
        return 0, 0
    now = timezone.now()
    reason = str(error)[:64]
    rows = DeliveryIntent.objects.filter(pk__in=pks)
    failed = rows.filter(attempts__gte=constants.DELIVERY_MAX_ATTEMPTS).update(
        status=Status.FAILED, last_error=reason, claim_token=None
    )
    retried = rows.filter(attempts__lt=constants.DELIVERY_MAX_ATTEMPTS).update(
        status=Status.PENDING,
        last_error=reason,
        claim_token=None,
        next_attempt_at=Case(
            *[
                When(attempts=n, then=Value(now + retry_delay(n)))
                for n in range(1, constants.DELIVERY_MAX_ATTEMPTS)
            ],
            default=Value(now + retry_delay(1)),
        ),
    )
    if failed:
        logger.error(
            "[DELIVERY] %d delivery(ies) failed after %d attempts (last error %s); "
            "giving up",
            failed,
            constants.DELIVERY_MAX_ATTEMPTS,
            reason,
        )
    return retried, failed


# --- reconcile -----------------------------------------------------------------


def reconcile() -> dict[str, int]:
    """One reconciliation pass. Safe to run concurrently: due rows are taken
    under ``SKIP LOCKED`` and pushed out of the due window before they are
    re-driven, and every task claims before it sends."""
    now = timezone.now()
    totals = {
        "expired": 0,
        "interrupted": 0,
        "overdue": 0,
        "redriven": 0,
        "pruned": 0,
    }
    lease_cut = now - timedelta(seconds=constants.DELIVERY_CLAIM_LEASE_SECONDS)

    # A row still inside its hold is not stale: its member asked for it
    # later (todo 624). Nor is one whose hold has only just ended: this pass
    # re-drives it below, so a hold that ran close to the max age is still
    # released rather than expired the moment it is due. The re-drive clears
    # the hold reason, so a released row that is never picked up expires
    # like any other on a later pass.
    hold_grace = now - timedelta(seconds=constants.DELIVERY_REDRIVE_INTERVAL_SECONDS)
    totals["expired"] = (
        DeliveryIntent.objects.filter(
            status__in=_OPEN,
            created_at__lt=now - timedelta(seconds=constants.DELIVERY_MAX_AGE_SECONDS),
        )
        .exclude(
            status=Status.PENDING,
            last_error__in=HOLDS,
            next_attempt_at__gt=hold_grace,
        )
        .update(status=Status.FAILED, last_error="expired", claim_token=None)
    )
    totals["interrupted"] = DeliveryIntent.objects.filter(
        status=Status.CLAIMED,
        claimed_at__lt=lease_cut,
        attempts__gte=constants.DELIVERY_MAX_ATTEMPTS,
    ).update(status=Status.FAILED, last_error="interrupted", claim_token=None)
    # Terminal failures nobody else reports (todo 623): Sentry's logging
    # integration makes each ERROR an event. Counts only.
    if totals["expired"] or totals["interrupted"]:
        logger.error(
            "[DELIVERY] %d delivery(ies) expired undelivered after %ss and %d "
            "interrupted on their last attempt; giving up",
            totals["expired"],
            constants.DELIVERY_MAX_AGE_SECONDS,
            totals["interrupted"],
        )
    # Before the re-drive below moves due rows out of the due window.
    # Guarded: an alerting query must never stop the re-drive below.
    try:
        totals["overdue"] = check_outbox_lag(now)["rows"]
    except Exception:
        totals["overdue"] = 0  # unknown this pass; callers always find the key
        # No bound exception: a frame local would reach Sentry (todo 623).
        logger.error(
            "[DELIVERY] the outbox lag check failed: %s; re-driving anyway",
            getattr(sys.exc_info()[0], "__name__", "unknown"),
        )

    with transaction.atomic():
        rows = list(
            DeliveryIntent.objects.filter(_due(now))
            .select_for_update(skip_locked=True)
            .order_by("next_attempt_at", "pk")[: constants.DELIVERY_RECONCILE_BATCH]
        )
        if rows:
            DeliveryIntent.objects.filter(pk__in=[row.pk for row in rows]).update(
                status=Status.PENDING,
                claim_token=None,
                next_attempt_at=now
                + timedelta(seconds=constants.DELIVERY_REDRIVE_INTERVAL_SECONDS),
                # A released hold is no longer one (the task re-holds it if
                # it must wait again).
                last_error=Case(
                    When(last_error__in=HOLDS, then=Value("")),
                    default=F("last_error"),
                ),
            )
    by_kind = defaultdict(list)
    for row in rows:
        by_kind[row.kind].append(row)
    for kind, kind_rows in by_kind.items():
        path = REDRIVERS.get(kind)
        if path is None:
            logger.error("[DELIVERY] no redriver for delivery kind %s", kind)
            continue
        try:
            import_string(path)(kind_rows)
        except Exception as exc:
            # The type only: a broker error can carry its URL. The rows stay
            # pending and are due again after the redrive interval.
            logger.error(
                "[DELIVERY] re-driving %d %s delivery(ies) failed: %s",
                len(kind_rows),
                kind,
                type(exc).__name__,
            )
            continue
        totals["redriven"] += len(kind_rows)

    totals["pruned"], _ = DeliveryIntent.objects.filter(
        status__in=_FINISHED,
        updated_at__lt=now - timedelta(days=constants.DELIVERY_RETENTION_DAYS),
    ).delete()
    return totals


# --- weekly mail recovery ------------------------------------------------------


def schedule_weekly_recovery(task, output: str, recovery: int, label: str) -> bool:
    """After a weekly mail run (forum digest, blog newsletter), enqueue one
    bounded recovery run of ``task`` when the command's summary line
    reported failed sends (todo 619).

    A recovery run is the same command: its run lock turns away an overlap,
    its per-member claim rechecks consent (still opted in, still active,
    still has an address) and skips everyone whose send was accepted, and an
    empty digest is still not sent. A member whose send failed stays due, so
    the recovery run is what retries them, at most
    ``WEEKLY_RECOVERY_MAX_RUNS`` times, ``WEEKLY_RECOVERY_DELAY_SECONDS``
    apart and doubling. Returns whether a recovery run was enqueued.
    """
    counts = summary_counts(output)
    failed = counts["failed"]
    enqueued = _enqueue_weekly_recovery(task, failed, recovery, label)
    # The run's outcomes in the shared vocabulary (todo 623), logged after
    # the decision so the line says what happened: a failed member is
    # retrying only when a recovery run was actually enqueued, else failed
    # (it stays due for the next scheduled run, which is not a retry).
    log_outcomes(
        "email",
        label.replace(" ", "_"),
        accepted=counts["sent"],
        suppressed=counts["suppressed"],
        retrying=failed if enqueued else 0,
        failed=0 if enqueued else failed,
    )
    return enqueued


def _enqueue_weekly_recovery(task, failed: int, recovery: int, label: str) -> bool:
    if not failed:
        return False
    if recovery >= constants.WEEKLY_RECOVERY_MAX_RUNS:
        logger.error(
            "[EMAIL] %s: %d send(s) still failed after %d recovery run(s); "
            "they stay due for the next scheduled run",
            label,
            failed,
            recovery,
        )
        return False
    countdown = constants.WEEKLY_RECOVERY_DELAY_SECONDS * 2**recovery
    try:
        task.apply_async(kwargs={"recovery": recovery + 1}, countdown=countdown)
    except Exception as exc:
        logger.error(
            "[EMAIL] %s: could not enqueue a recovery run for %d failed send(s): %s",
            label,
            failed,
            type(exc).__name__,
        )
        return False
    logger.warning(
        "[EMAIL] %s: %d send(s) failed; recovery run %d in %ss",
        label,
        failed,
        recovery + 1,
        countdown,
    )
    return True
