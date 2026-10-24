"""Notification outcomes and operational alerts (todo 623).

One vocabulary for what happened to a notification, shared by every live
email and push path, and the ERROR logs that page through Sentry when the
machinery behind them breaks. It extends the delivery outbox's states (todo
619, ``apps/core/delivery.py``); it is not a second ledger and stores
nothing of its own.

Outcomes
--------
Send side, decided by this app:

- ``queued``: recorded, no attempt yet (an outbox row still pending, a
  quiet-hours or coalescing hold included, since a hold hands its attempt
  back).
- ``attempted``: a worker claimed it, or handed it to another task's retries
  (``delivery.HANDED_OFF``). Not proof the provider took it.
- ``accepted``: the provider (SMTP relay, FCM, a browser push service)
  accepted the message. This is all a send can know. It is **not**
  ``delivered`` and says nothing about display or engagement.
- ``retrying``: a transient failure, due again (outbox backoff, a weekly
  recovery run, a care reminder released for the next sweep).
- ``failed``: terminal: a permanent rejection, the attempts spent, expired.
- ``suppressed``: not sent on purpose: opted out, blocked, no address or
  device, or a provider suppression (todo 625).

Provider evidence only (``email_feedback.py``, from Resend's signed
webhook): ``delivered``, ``bounced``, ``complained``. No send path may report
them, so ``log_outcomes`` refuses them.

Engagement is not an outcome. A click is an ``EmailClick`` row (todo 625)
and never changes a delivery's status; opens are not collected.

Where each path records it
--------------------------
- Forum reply/mention/quote/answer email, forum browser push, forum mobile
  push, verification email, lockout email, newsletter confirmation: the
  outbox row (``outcome_of_intent``; ``manage.py delivery_outcomes`` counts
  them).
- ``EmailService.send_email`` / ``send_transactional_email``: the
  ``EmailOutcome`` on ``last_outcome`` (``outcome_of_email``) and, for
  ``send_email``, the ``EmailNotification`` row (``outcome_of_notification``).
- Forum weekly digest and blog newsletter: the command's summary line,
  logged as an ``[OUTCOME]`` line by ``delivery.schedule_weekly_recovery``.
  A run stopped by its soft time limit writes no summary, so its sends are
  not in any line; the continuation run reports only its own.
- Care-task reminders: an ``[OUTCOME]`` line per sweep.

Alerts
------
Sentry's logging integration turns every ERROR log into an event, so each
alert below is an ERROR line: counts, kinds and exception class names, never
an address, a token, a URL or a message body. No alert path binds the
exception (``except Exception:`` plus ``sys.exc_info()``), and
``plant_community_backend.sentry_config.before_send`` drops the frame
variables from these events, so ``attach_stacktrace`` cannot ship a caller's
``payload``, a task's ``token`` or a broker error's text.

- Broker refused an enqueue: ``log_broker_failure``.
- Exhausted retries: ``delivery.mark_retry`` and ``reconcile`` (expired and
  interrupted rows), the weekly recovery cap.
- Aged queue: ``check_outbox_lag`` in every reconcile pass.
- Missing push configuration with work to drop: ``report_push_unconfigured``.
- Missed or late worker/beat runs: Sentry Cron Monitors
  (``plant_community_backend/sentry_config.py``).
"""

import logging
import re
import sys
import time
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Min, Q
from django.utils import timezone

from . import constants

logger = logging.getLogger("apps.core.notification_ops")


class Outcome:
    QUEUED = "queued"
    ATTEMPTED = "attempted"
    ACCEPTED = "accepted"
    RETRYING = "retrying"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    # Provider evidence only.
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    COMPLAINED = "complained"


SEND_OUTCOMES = (
    Outcome.QUEUED,
    Outcome.ATTEMPTED,
    Outcome.ACCEPTED,
    Outcome.RETRYING,
    Outcome.FAILED,
    Outcome.SUPPRESSED,
)
PROVIDER_OUTCOMES = (Outcome.DELIVERED, Outcome.BOUNCED, Outcome.COMPLAINED)


# --- mapping each path's own result -------------------------------------------


def outcome_of_intent(status: str, attempts: int, last_error: str = "") -> str:
    """The outcome of one outbox row (``DeliveryIntent``)."""
    from .delivery import HANDED_OFF, HOLDS
    from .models import DeliveryIntent

    S = DeliveryIntent.Status
    if status == S.PENDING:
        # A hold is queued even after an earlier transient failure: the
        # row is waiting by design, not backing off.
        if last_error in HOLDS:
            return Outcome.QUEUED
        return Outcome.RETRYING if attempts else Outcome.QUEUED
    if status == S.CLAIMED:
        return Outcome.ATTEMPTED
    if status == S.SENT:
        return Outcome.ATTEMPTED if last_error == HANDED_OFF else Outcome.ACCEPTED
    if status == S.SUPPRESSED:
        return Outcome.SUPPRESSED
    if status == S.FAILED:
        return Outcome.FAILED
    raise ValueError(f"unknown delivery status {status!r}")


def outcome_of_email(email_outcome: str) -> str:
    """The outcome of one ``EmailService`` send (``EmailOutcome``)."""
    from .services.email_service import EmailOutcome

    mapping = {
        EmailOutcome.SENT: Outcome.ACCEPTED,
        EmailOutcome.SUPPRESSED: Outcome.SUPPRESSED,
        EmailOutcome.PERMANENT: Outcome.FAILED,
        EmailOutcome.TRANSIENT: Outcome.RETRYING,
    }
    try:
        return mapping[email_outcome]
    except KeyError:
        raise ValueError(f"unknown email outcome {email_outcome!r}") from None


def outcome_of_notification(status: str) -> str:
    """The outcome an ``EmailNotification`` row records. Only the provider's
    webhook moves a row past ``sent`` (``email_feedback.py``)."""
    from .models import EmailNotification as N

    mapping = {
        N.STATUS_PENDING: Outcome.QUEUED,
        N.STATUS_SENT: Outcome.ACCEPTED,
        N.STATUS_FAILED: Outcome.FAILED,
        N.STATUS_DELIVERED: Outcome.DELIVERED,
        N.STATUS_BOUNCED: Outcome.BOUNCED,
        N.STATUS_COMPLAINED: Outcome.COMPLAINED,
    }
    try:
        return mapping[status]
    except KeyError:
        raise ValueError(f"unknown notification status {status!r}") from None


def outbox_outcome_counts(since=None) -> dict[str, dict[str, int]]:
    """{kind: {outcome: rows}} for outbox rows created since ``since`` (all
    retained rows when None). One aggregate query."""
    from .delivery import HANDED_OFF, HOLDS
    from .models import DeliveryIntent

    S = DeliveryIntent.Status
    rows = DeliveryIntent.objects.all()
    if since is not None:
        rows = rows.filter(created_at__gte=since)
    grouped = rows.values("kind", "status").annotate(
        n=Count("pk"),
        # Tried and not held: a hold after a transient failure is queued.
        tried=Count("pk", filter=Q(attempts__gt=0) & ~Q(last_error__in=HOLDS)),
        handed=Count("pk", filter=Q(last_error=HANDED_OFF)),
    )
    totals: dict[str, dict[str, int]] = {}
    for g in grouped:
        kind = totals.setdefault(g["kind"], {})
        status, n = g["status"], g["n"]
        if status == S.PENDING:
            parts = {Outcome.QUEUED: n - g["tried"], Outcome.RETRYING: g["tried"]}
        elif status == S.SENT:
            parts = {Outcome.ACCEPTED: n - g["handed"], Outcome.ATTEMPTED: g["handed"]}
        else:
            parts = {outcome_of_intent(status, 1): n}
        for outcome, count in parts.items():
            if count:
                kind[outcome] = kind.get(outcome, 0) + count
    return totals


def log_outcomes(channel: str, path: str, **counts: int) -> None:
    """One ``[OUTCOME]`` INFO line of counts for a send run. Only send-side
    outcomes: a send cannot know that a message was delivered."""
    unknown = sorted(set(counts) - set(SEND_OUTCOMES))
    if unknown:
        raise ValueError(
            f"{unknown} are not send outcomes; delivered/bounced/complained "
            "come only from the provider's feedback"
        )
    parts = " ".join(
        f"{outcome}={int(counts[outcome])}"
        for outcome in SEND_OUTCOMES
        if outcome in counts
    )
    logger.info("[OUTCOME] channel=%s path=%s %s", channel, path, parts)


_SUMMARY_COUNT = re.compile(r"\b(sent|failed|suppressed)=(\d+)\b")


def summary_counts(output: str) -> dict[str, int]:
    """sent/failed/suppressed totals from a weekly mail command's output."""
    totals = {"sent": 0, "failed": 0, "suppressed": 0}
    for name, value in _SUMMARY_COUNT.findall(output):
        totals[name] += int(value)
    return totals


# --- alerts --------------------------------------------------------------------


def log_broker_failure(log: logging.Logger, message: str, *args) -> None:
    """ERROR for an enqueue the broker refused, from inside the ``except``.

    The exception's class name only, and no traceback: a broker error's
    message can carry its host or URL. The outbox row (where there is one)
    stays pending and reconciliation sends it once the broker is back."""
    exc_type = sys.exc_info()[0]
    name = exc_type.__name__ if exc_type is not None else "unknown"
    log.error(message + " (broker: %s)", *args, name)


# Per-process fallback for the alert throttle when the cache cannot answer:
# {cache key: time.monotonic() of the last alert}.
_LAST_ALERT: dict[str, float] = {}


def report_push_unconfigured(channel: str, context: str, *, has_work=None) -> bool:
    """ERROR when a push channel is not configured and there was work for it
    (todo 623). ``has_work`` (a callable) says whether anything could have
    been pushed, e.g. a recipient with a browser subscription or a device:
    with none, a deployment that deliberately runs without that channel
    stays quiet. At most once per channel per
    ``PUSH_UNCONFIGURED_ALERT_SECONDS``, through the shared cache, or a
    per-process clock when the cache cannot answer (a Redis outage under
    IGNORE_EXCEPTIONS answers None), so a 15-minute sweep never pages every
    run. The throttle is peeked at BEFORE the probe, so a throttled window
    costs no probe query. Returns whether it logged."""
    key = f"notification_ops:push_unconfigured:{channel}"
    if _throttled(key):
        return False
    if has_work is not None:
        try:
            if not has_work():
                return False
        except Exception:
            # No bound exception: frame locals reach Sentry.
            logger.warning(
                "[PUSH] could not check for %s work: %s",
                channel,
                getattr(sys.exc_info()[0], "__name__", "unknown"),
            )
            return False
    try:
        fresh = cache.add(key, 1, constants.PUSH_UNCONFIGURED_ALERT_SECONDS)
    except Exception:
        fresh = None
    if fresh is None:
        fresh = _throttle_locally(key)
    if not fresh:
        return False
    logger.error(
        "[PUSH] %s is not configured: %s were not pushed (check the "
        "credentials on the deployed service)",
        channel,
        context,
        stack_info=False,
    )
    return True


def _throttled(key: str) -> bool:
    """A cheap peek: True when this window's alert already went out, by the
    shared cache or, when the cache cannot answer, this process's clock."""
    try:
        if cache.get(key):
            return True
    except Exception:
        pass
    last = _LAST_ALERT.get(key)
    return (
        last is not None
        and time.monotonic() - last < constants.PUSH_UNCONFIGURED_ALERT_SECONDS
    )


def _throttle_locally(key: str) -> bool:
    """True at most once per ``PUSH_UNCONFIGURED_ALERT_SECONDS`` per key in
    this process."""
    now = time.monotonic()
    last = _LAST_ALERT.get(key)
    if last is not None and now - last < constants.PUSH_UNCONFIGURED_ALERT_SECONDS:
        return False
    _LAST_ALERT[key] = now
    return True


def check_outbox_lag(now=None) -> dict[str, int]:
    """Rows overdue by more than ``DELIVERY_QUEUE_LAG_ALERT_SECONDS``: due
    (a hold or a backoff counts from its release time) and still pending.

    A healthy reconcile pass re-drives every due row and moves it out of the
    due window, so a row this far past due means the backlog is larger than
    a pass takes (``DELIVERY_RECONCILE_BATCH``) or passes stopped. A stalled
    worker or broker is caught by the beat Cron Monitors instead: this check
    runs on that worker. ERROR when any row is overdue."""
    from .models import DeliveryIntent

    now = now or timezone.now()
    cut = now - timedelta(seconds=constants.DELIVERY_QUEUE_LAG_ALERT_SECONDS)
    lag = DeliveryIntent.objects.filter(
        status=DeliveryIntent.Status.PENDING, next_attempt_at__lt=cut
    ).aggregate(rows=Count("pk"), oldest=Min("next_attempt_at"))
    rows = lag["rows"] or 0
    oldest = int((now - lag["oldest"]).total_seconds()) if rows else 0
    if rows:
        logger.error(
            "[DELIVERY] %d delivery(ies) overdue by more than %ss (oldest %ss): "
            "the outbox is not draining",
            rows,
            constants.DELIVERY_QUEUE_LAG_ALERT_SECONDS,
            oldest,
        )
    return {"rows": rows, "oldest_seconds": oldest}
