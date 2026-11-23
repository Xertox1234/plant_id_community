"""Celery tasks for forum push (Issue 14) and email (todo 253 slice 2, H1)
notifications.

Fired by forum_host/notifications.py dispatch() via .delay() so that:
- The publish transaction is never held open waiting for FCM/SMTP.
- A failed delivery never rolls back a moderation decision.
- Tasks are retried automatically by Celery on their respective transient
  error classes (FCM send errors for push; OperationalError for email).
"""

import logging
from datetime import timedelta

from apps.core import fcm as core_fcm
from apps.core.notification_ops import report_push_unconfigured
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError
from django.utils import timezone
from wagtail_forum.preferences import wants_channel

from . import constants, pacing
from .eligibility import (
    REASON_PREFERENCE,
    REASON_READ,
    already_read_ids,
    client_payload,
    recheck,
)

logger = logging.getLogger("forum_host.tasks")


# Sized for a cohort, not a single object: the global 90 s/120 s limits are
# for the per-post tasks below. A digest run costs a few queries + one SMTP
# round-trip per due member; ~1,500 members fit in 25 minutes at 1 s each.
DIGEST_SOFT_TIME_LIMIT = 25 * 60
DIGEST_TIME_LIMIT = 30 * 60
DIGEST_CONTINUATION_DELAY = 60
# A recovery run that finds the run lock held (an hourly quiet-hours run can
# be mid-send when it fires) waits and tries again instead of ending its
# retry chain: every DIGEST_LOCK_WAIT_DELAY seconds, at most
# DIGEST_LOCK_WAIT_MAX_RUNS times. 8 x 5 min = 40 min, longer than the lock
# can outlive its holder (WAGTAILFORUM_DIGEST_RUN_LOCK_SECONDS, 35 min).
DIGEST_LOCK_WAIT_DELAY = 5 * 60
DIGEST_LOCK_WAIT_MAX_RUNS = 8
# The line `send_forum_digest` writes when another run holds its lock.
DIGEST_LOCK_HELD_MARKER = "another run holds the lock"


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=60,  # seconds; a transient DB blip retries in 1/2/4 min
    max_retries=3,
    soft_time_limit=DIGEST_SOFT_TIME_LIMIT,
    time_limit=DIGEST_TIME_LIMIT,
    ignore_result=True,
)
def send_forum_weekly_digest(
    self, recovery: int = 0, quiet_only: bool = False, lock_wait: int = 0
):
    """Celery beat entry (settings.CELERY_BEAT_SCHEDULE) for the package's
    `send_forum_digest` command (todo 340). The package owns content and
    sending; this is only the host's scheduling wire.

    Overlap safety is the COMMAND's: a cache run-lock makes a second fire
    (beat re-firing after a worker restart, two containers during a deploy)
    exit immediately, and `last_digest_sent_at` is committed per member with
    that member's send before the loop advances, so a run killed by the time
    limit resumes where it stopped — the continuation re-enqueued below
    simply picks up the members still due. Retrying on OperationalError is
    safe for the same reason. The lock's TTL is the package setting
    WAGTAILFORUM_DIGEST_RUN_LOCK_SECONDS, whose default (35 min) is
    DIGEST_TIME_LIMIT plus 5 minutes; change both together (todo 548).

    A run that reports failed sends enqueues a bounded recovery run
    (``recovery`` counts them, todo 619): the failed members are still due,
    and the command's claim rechecks their consent and never repeats an
    accepted send (``apps.core.delivery.schedule_weekly_recovery``).

    Quiet hours (todo 728): the command skips a due member whose quiet
    window covers the run and leaves them due. ``quiet_only`` is the hourly
    follow-up beat entries' run (``forum-weekly-digest-quiet-release-*``),
    which looks only at members with quiet hours on and sends to those whose
    window has ended. It is a beat entry, not an ``eta`` on this task: a hold
    can last most of a day, and a broker message that old is redelivered by
    Redis's visibility timeout (see ``pacing``). The run lock and the
    per-member claim are the same for both runs, so no member gets two.

    The shared lock must not cost a recovery run its turn: a recovery run
    lands about 30 and 90 minutes after the main run, where an hourly
    follow-up run can be holding the lock. The command then exits with no
    summary line, which would read as "nothing failed" and end the retries.
    So a recovery run turned away by the lock is re-enqueued with the same
    ``recovery`` count (``lock_wait`` counts the waits, bounded by
    ``DIGEST_LOCK_WAIT_MAX_RUNS``). Any other run turned away is left alone,
    as before; that includes a soft-limit continuation of the main run that
    meets an hourly run's lock, whose remaining members then wait for the
    next weekly run.
    """
    from io import StringIO

    from apps.core.delivery import schedule_weekly_recovery
    from celery.exceptions import SoftTimeLimitExceeded
    from django.core.management import call_command

    logger.info("[EMAIL] forum weekly digest: starting (task=%s)", self.request.id)
    out = StringIO()
    try:
        # The option is passed only on the follow-up run, so the main run's
        # call is exactly what it was before todo 728.
        scope = (
            {
                "quiet_hours_only": True,
                "held_at": _last_main_digest_run(timezone.now()).isoformat(),
            }
            if quiet_only
            else {}
        )
        call_command("send_forum_digest", frequency="weekly", stdout=out, **scope)
    except SoftTimeLimitExceeded:
        logger.warning(
            "[EMAIL] forum weekly digest hit the soft time limit (task=%s); "
            "re-enqueuing to finish the members still due",
            self.request.id,
        )
        # A continuation keeps its run's recovery count (todo 619) and its
        # scope (todo 728).
        kwargs: dict = {}
        if recovery:
            kwargs["recovery"] = recovery
        if quiet_only:
            kwargs["quiet_only"] = True
        extra = {"kwargs": kwargs} if kwargs else {}
        send_forum_weekly_digest.apply_async(
            countdown=DIGEST_CONTINUATION_DELAY, **extra
        )
        return
    finally:
        for line in out.getvalue().splitlines():
            if line.strip():
                # No prefix of our own: this relays `send_forum_digest`'s stdout, and
                # every line it writes already opens with [EMAIL]. Adding one
                # here would log "[EMAIL] [EMAIL] ..." (todo 392).
                # log-prefix: exempt (relayed command output, already prefixed)
                logger.info("%s (task=%s)", line, self.request.id)
    if recovery and DIGEST_LOCK_HELD_MARKER in out.getvalue():
        _retry_recovery_after_the_lock(self.request.id, recovery, lock_wait)
        return
    schedule_weekly_recovery(
        send_forum_weekly_digest, out.getvalue(), recovery, "forum weekly digest"
    )


def _last_main_digest_run(now):
    """When the main weekly digest last fired at or before ``now``, read from
    its beat entry. The follow-up runs pass it to the command, which then
    sends only to members whose quiet window covered that run."""
    from django.conf import settings

    schedule = settings.CELERY_BEAT_SCHEDULE["forum-weekly-digest"]["schedule"]
    candidate = now.replace(
        hour=min(schedule.hour), minute=min(schedule.minute), second=0, microsecond=0
    )
    # Celery counts Sunday as 0; Python counts Monday as 0.
    for _ in range(8):
        if candidate <= now and (candidate.weekday() + 1) % 7 in schedule.day_of_week:
            return candidate
        candidate -= timedelta(days=1)
    raise RuntimeError("the forum-weekly-digest beat entry matches no day")


def _retry_recovery_after_the_lock(
    task_id: str | None, recovery: int, lock_wait: int
) -> None:
    """Re-enqueue a recovery run that another digest run's lock turned away,
    keeping its ``recovery`` count, so the failed members are still retried."""
    if lock_wait >= DIGEST_LOCK_WAIT_MAX_RUNS:
        logger.error(
            "[EMAIL] forum weekly digest: recovery run %d still found the run "
            "lock held after %d wait(s); the failed sends stay due for the "
            "next scheduled run (task=%s)",
            recovery,
            lock_wait,
            task_id,
        )
        return
    try:
        send_forum_weekly_digest.apply_async(
            kwargs={"recovery": recovery, "lock_wait": lock_wait + 1},
            countdown=DIGEST_LOCK_WAIT_DELAY,
        )
    except Exception as exc:
        # The type only: a broker error can carry its URL.
        logger.error(
            "[EMAIL] forum weekly digest: could not re-enqueue recovery run "
            "%d behind the run lock: %s (task=%s)",
            recovery,
            type(exc).__name__,
            task_id,
        )
        return
    logger.warning(
        "[EMAIL] forum weekly digest: recovery run %d found the run lock "
        "held; trying again in %ss (wait %d of %d, task=%s)",
        recovery,
        DIGEST_LOCK_WAIT_DELAY,
        lock_wait + 1,
        DIGEST_LOCK_WAIT_MAX_RUNS,
        task_id,
    )


def _permanent_failure_level(exc: Exception) -> int:
    """ERROR for a project-wide credentials failure, else WARNING (todo 566)."""
    if core_fcm.is_fcm_credentials_error(exc):
        return logging.ERROR
    return logging.WARNING


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

    Only reply_added, mention, quote and answer_accepted render a tray entry. moderation_decided is
    deliberately None: workflow.py fires it with status="published" on EVERY
    routine trust-autopublished post/reply/edit, so a visible block would
    tray-popup "Your post was published" at users for their own ordinary
    posts (slice-6 review, cross-file tracer) — it keeps the pre-slice
    data-only behavior. Unknown/future events also stay data-only until
    someone designs their copy.

    THE WORDING IS NOT HERE (todo 287). Both backend surfaces — this tray and
    the email subject/body in
    ``apps/core/services/notification_service.py::send_forum_reply_notification``
    — read ``apps/forum_host/notification_copy.py``. Edit copy there; this
    function owns only the rendering concerns that are specific to push (title
    truncation, the actor default). The web bell
    (``web/src/components/layout/NotificationBell.tsx``) is still a third,
    independent home because the frontend cannot import a Python table — see
    that module's docstring.
    """
    from .constants import PUSH_TITLE_TOPIC_MAX_CHARS
    from .notification_copy import push_content

    topic_title = str(data.get("topic_title") or "").strip()
    if len(topic_title) > PUSH_TITLE_TOPIC_MAX_CHARS:
        topic_title = topic_title[: PUSH_TITLE_TOPIC_MAX_CHARS - 1] + "…"
    actor = str(data.get("actor_name") or "").strip() or "Someone"
    # A coalesced reply (todo 624) carries how many replies it folds.
    count = int(data["count"]) if str(data.get("count") or "").isdigit() else 1

    return push_content(event, topic_title, actor, count)


def _forum_collapse_key(event: str) -> str:
    """Per EVENT TYPE, not per post (see docs/rules/celery.md)."""
    return f"forum-{event}"


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_forum_push(
    self,
    event: str,
    recipient_user_id: int,
    data: dict,
    token: str | None = None,
    handed_off: bool = False,
):
    """Send one forum FCM push to every device of one account (todo 621).

    Args:
        event: one of "reply_added", "moderation_decided", "topic_created",
               "mention" (todo 253 slice 4, H4 — dispatched from both
               reply_added and topic_created's mention handling, not a
               signal name of its own).
        recipient_user_id: pk of the User whose devices to look up.
        data: dict of string key/value pairs to include in the FCM data payload.
              All values are coerced to strings (FCM requirement).
        token: one device only. Set when an earlier send reached some of the
              account's devices and this one failed transiently, so a retry
              never re-sends to the devices that already have it. Skipped if
              the token is no longer this account's.
        handed_off: set by ``send_forum_push_batch`` when it hands a push it
              already started to this task's retries (todo 624): never held
              for quiet hours, since the batch has finished its outbox row.

    A transient failure retries this task only when no device got the push;
    otherwise each failed device is handed to its own retry (``token=``).
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from apps.core.push_devices import device_tokens_for_users
    from django.contrib.auth import get_user_model
    from wagtail_forum.models import ForumProfile

    User = get_user_model()

    if not is_firebase_available():
        # Only when the member has a device: no page for a deployment that
        # runs without FCM on purpose (todo 623 review).
        report_push_unconfigured(
            "FCM",
            f"forum {event} pushes",
            has_work=lambda: bool(device_tokens_for_users([recipient_user_id])),
        )
        return

    # Every read before the first send (audit 2026-11-21 L8): a transient DB
    # error here retries the task. Nothing has been sent yet, so the retry
    # cannot duplicate a push.
    try:
        try:
            user = User.objects.get(pk=recipient_user_id)
        except User.DoesNotExist:
            logger.warning(
                "[FCM] forum push skipped — user %s not found", recipient_user_id
            )
            return

        if getattr(user, "forum_notifications", True) is not True:
            logger.debug(
                "[FCM] forum push skipped — user %s has forum_notifications=False",
                recipient_user_id,
            )
            return

        profile = ForumProfile.for_user(user)
        if not wants_channel(profile.notification_preferences, event, "push"):
            logger.debug(
                "[FCM] forum push skipped — user %s opted out of push for %s",
                recipient_user_id,
                event,
            )
            return
        # Send-time recheck (todo 619), on the first run and on every retry: the
        # account, the content and the actor may have changed since enqueue.
        check = recheck(
            event,
            [user.pk],
            data,
            "push",
            users=[user],
            overrides_by_user={user.pk: profile.notification_preferences},
        )
        if check.suppressed:
            logger.debug(
                "[FCM] forum push skipped — user %s no longer eligible (%s)",
                recipient_user_id,
                check.suppressed[user.pk],
            )
            return
        try:
            held = _hold_single_push(event, user.pk, data, token, handed_off)
        except OperationalError as exc:
            # The hold could not be written. Retried, not sent: a send now would
            # land inside the member's quiet hours (review round 2, PR #1132).
            raise self.retry(
                exc=exc, countdown=self.default_retry_delay * (2**self.request.retries)
            ) from exc
        if held:
            return
        tokens = device_tokens_for_users([recipient_user_id]).get(recipient_user_id, [])
        if token is not None:
            tokens = [t for t in tokens if t == token]
        if not tokens:
            logger.debug(
                "[FCM] forum push skipped — user %s has no FCM token", recipient_user_id
            )
            return

    except OperationalError as exc:
        raise self.retry(
            exc=exc, countdown=self.default_retry_delay * (2**self.request.retries)
        ) from exc

    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot send forum push")
        return

    # Coerce all values to strings — FCM data payloads must be str:str. The
    # host's recheck keys stay on the server (todo 619).
    str_data = {k: str(v) for k, v in client_payload(data).items()}
    str_data["event"] = event

    content = _notification_content(event, data)

    transient: list[tuple[str, Exception]] = []
    for device_token in tokens:
        try:
            response = core_fcm.send_fcm_message(
                fcm, device_token, str_data, content, _forum_collapse_key(event)
            )
            logger.info(
                "[FCM] forum.%s sent to user=%s: %s", event, recipient_user_id, response
            )
        except Exception as exc:
            if core_fcm.is_permanent_fcm_error(exc):
                # e.g. the device token is stale — retrying can never succeed.
                if core_fcm.is_dead_fcm_token_error(exc):
                    # Forget that device only (todos 457, 621).
                    core_fcm.clear_dead_fcm_token(recipient_user_id, device_token)
                # A credentials error keeps the token and logs at ERROR: it is
                # the server's setup, not this device (todo 566).
                logger.log(
                    _permanent_failure_level(exc),
                    "[FCM] forum.%s send failed permanently (user=%s, task_id=%s):"
                    " %s — not retrying",
                    event,
                    recipient_user_id,
                    self.request.id,
                    exc,
                )
                continue
            transient.append((device_token, exc))

    if not transient:
        return
    if len(transient) < len(tokens):
        # Some devices got it, or failed for good: retry only the ones that
        # failed transiently, each on its own (todo 621), so no device that
        # has the push gets it twice and no dropped one is tried again.
        for device_token, device_exc in transient:
            logger.warning(
                "[FCM] forum.%s send failed on one device (user=%s, task_id=%s):"
                " %s — retrying that device",
                event,
                recipient_user_id,
                self.request.id,
                device_exc,
            )
            # Guarded as in send_forum_push_batch (todo 650 #2): a broker that
            # refuses one hand-off must not escape and drop the devices after
            # it. Only the type is logged: a broker error can carry its URL.
            try:
                send_forum_push.delay(
                    event, recipient_user_id, data, token=device_token
                )
            except Exception as enqueue_exc:
                logger.error(
                    "[FCM] forum.%s device retry could not be enqueued (user=%s,"
                    " task_id=%s): %s — that device misses this push",
                    event,
                    recipient_user_id,
                    self.request.id,
                    type(enqueue_exc).__name__,
                )
        return
    last_exc = transient[-1][1]
    logger.warning(
        "[FCM] forum.%s send failed (user=%s, task_id=%s): %s — retrying",
        event,
        recipient_user_id,
        self.request.id,
        last_exc,
    )
    # Every device failed transiently: retry the task. Exponential backoff:
    # 30s, 60s, 120s across max_retries=3. A ``token=`` retry keeps its
    # token, which rides in the request kwargs.
    raise self.retry(
        exc=last_exc, countdown=self.default_retry_delay * (2**self.request.retries)
    )


def _hold_single_push(event, user_id, data, token, handed_off) -> bool:
    """Quiet hours for the one push sent through ``send_forum_push``: the
    accepted answer (todo 624). Inside the member's window it becomes a held
    outbox row, released by reconciliation through ``send_forum_push_batch``
    when the window ends. A batch's hand-off and a one-device retry are not
    held: the batch owns that row, and some devices already have the push.
    A whole-account retry is held like a first run (nobody got it yet), so a
    retry after a failed hold write still honours quiet hours."""
    from apps.core import delivery

    if event != "answer_accepted" or token is not None or handed_off:
        return False
    release = pacing.quiet_release_for(user_id)
    if release is None:
        return False
    from apps.core.models import DeliveryIntent

    subject_key = str(data.get("post_id", ""))
    batch_id = delivery.record_batch(
        delivery.Kind.FORUM_PUSH,
        event,
        [user_id],
        data,
        subject_key=subject_key,
        due_at=release,
        reason=delivery.HOLD_QUIET_HOURS,
    )
    if not DeliveryIntent.objects.filter(batch_id=batch_id).exists():
        # The row is unique per (kind, event, post, recipient), so the insert
        # was a no-op: an earlier accept of this answer (or a redelivery of
        # this task) owns it. Still pending, that row is the held push.
        # Claimed, a batch is sending it right now; finished, a re-accept
        # after the first one went out. Either way holding would drop this
        # push: send it now instead.
        if not DeliveryIntent.objects.filter(
            kind=delivery.Kind.FORUM_PUSH,
            event=str(event),
            subject_key=subject_key,
            recipient_id=user_id,
            status=delivery.Status.PENDING,
        ).exists():
            return False
    logger.info("[FCM] forum.%s push for user=%s held for quiet hours", event, user_id)
    return True


@shared_task(
    autoretry_for=(OperationalError,),
    # The BACKOFF FACTOR (30s/60s/120s jittered ceiling), not a bool — True
    # meant factor 1, ~1s/2s/4s (audit 2026-09-04 M8; see the sibling
    # sync_blog_page_chunks and constants.NOTIFICATION_BATCH_RETRY_DELAY).
    retry_backoff=constants.NOTIFICATION_BATCH_RETRY_DELAY,
    max_retries=constants.NOTIFICATION_BATCH_MAX_RETRIES,
    # Sized to one chunk of recipients (todo 727), not the global 90 s/120 s.
    soft_time_limit=constants.NOTIFICATION_BATCH_SOFT_TIME_LIMIT,
    time_limit=constants.NOTIFICATION_BATCH_TIME_LIMIT,
    ignore_result=True,  # side-effect only; every call site enqueues and moves on
)
def send_forum_push_batch(
    event: str,
    recipient_user_ids: list[int],
    data: dict,
    requeued: bool = False,
    batch_id: str | None = None,
):
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
        requeued: True on the one follow-up batch a credentials stop enqueues
            (todo 606); that batch never re-enqueues again.
        batch_id: the outbox rows ``dispatch`` wrote (todo 624), or None. With
            it, only the recipients this run claims are sent to, quiet hours
            and reply coalescing hold what they should (``pacing``), and each
            recipient's outcome is recorded. A transient failure is still
            handed to ``send_forum_push`` and its retries; that row is done.
    """
    from apps.core import delivery
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from apps.core.push_devices import device_tokens_for_users
    from wagtail_forum.models import ForumProfile

    kind = delivery.Kind.FORUM_PUSH
    if not recipient_user_ids:
        return

    if not is_firebase_available():
        report_push_unconfigured(
            "FCM",
            f"forum {event} pushes",
            has_work=lambda: bool(device_tokens_for_users(recipient_user_ids)),
        )
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "channel_off")
        return

    fcm = get_fcm_client()
    if fcm is None:
        logger.error("[FCM] FCM client unavailable — cannot send forum push")
        # Backed off like a transient failure (terminal at the attempt cap),
        # not left pending for reconciliation to re-drive every interval.
        if batch_id:
            backed_off = delivery.claim_batch(kind, batch_id, recipient_user_ids)
            _record(delivery.mark_retry, list(backed_off.values()), "fcm_unavailable")
        return

    # One bulk fetch instead of N: the profile row carries the recipient's
    # preferences (forum_notifications, per-event push). A user with no
    # ForumProfile is skipped, as before. Devices come from one more bulk
    # read (todo 621): every device of the account, legacy token included.
    # Ordered, so which recipients a credentials stop leaves untried is
    # deterministic (todo 606).
    profiles = list(
        ForumProfile.objects.filter(user_id__in=recipient_user_ids)
        .select_related("user")
        .order_by("user_id")
    )
    tokens_by_user = device_tokens_for_users(p.user_id for p in profiles)
    # Send-time recheck (todo 619): forum_notifications, the per-event push
    # preference (todo 343), an active account, and for a dispatched payload
    # the content's visibility and blocks/mutes against its actor. Checked
    # here, where the profile rows are already in hand, in a constant number
    # of queries.
    ineligible = recheck(
        event,
        [p.user_id for p in profiles],
        data,
        "push",
        users=[p.user for p in profiles],
        overrides_by_user={p.user_id: p.notification_preferences for p in profiles},
    ).suppressed

    def wants_push(profile) -> bool:
        if profile.user_id in ineligible:
            return False
        return bool(tokens_by_user.get(profile.user_id))

    claimed: dict[int, int] | None = None
    if batch_id:
        # After every up-front read, as in the browser-push task.
        claimed = delivery.claim_batch(kind, batch_id, recipient_user_ids)
        by_user = {p.user_id: p for p in profiles}
        suppressed: dict[str, list[int]] = {}
        for pk, row in claimed.items():
            profile = by_user.get(pk)
            reason = ineligible.get(pk) if profile is not None else "no_destination"
            if reason is None and not wants_push(profile):
                reason = "no_destination"
            if reason is not None:
                suppressed.setdefault(reason, []).append(row)
        _record(delivery.mark_suppressed_by_reason, suppressed)
    paced = pacing.pace_claimed(
        send_forum_push_batch,
        kind,
        event,
        data,
        batch_id,
        claimed,
        [p.user for p in profiles if wants_push(p)],
        recipient_user_ids,
    )

    sent = 0
    credentials_failed: list[int] = []
    last_credentials_exc: Exception | None = None
    # The recipients a credentials stop left untried: only those this batch
    # would have sent to, so the count is not inflated by opted-out, muted or
    # tokenless profiles (todo 606).
    untried: list[int] | None = None
    outcomes: dict = {"sent": [], "handed_off": [], "failed": [], "credentials": []}
    # The soft time limit stops the batch instead of being swallowed as a send
    # failure: what was sent is recorded, the rest is released for
    # reconciliation, then the limit is re-raised (audit 2026-11-21 M3).
    time_limit_hit: SoftTimeLimitExceeded | None = None
    # The limit can also land outside a device send (it is a signal): the
    # recipients from there on with no recorded outcome go back too, and
    # everyone already pushed is still recorded below (Phase 6 review).
    index, folds_finished = 0, -1
    try:
        for index, send in enumerate(paced.sends):
            user = send.user
            send_data = pacing.folded_data(data, send)
            str_data = {k: str(v) for k, v in client_payload(send_data).items()}
            str_data["event"] = event
            content = _notification_content(event, send_data)
            devices = tokens_by_user[user.pk]
            user_sent = 0
            user_credentials_failed = False
            transient: list[str] = []
            for device_token in devices:
                try:
                    response = core_fcm.send_fcm_message(
                        fcm, device_token, str_data, content, _forum_collapse_key(event)
                    )
                    logger.info(
                        "[FCM] forum.%s sent to user=%s: %s", event, user.pk, response
                    )
                    user_sent += 1
                except SoftTimeLimitExceeded as exc:
                    time_limit_hit = exc
                    break
                except Exception as exc:
                    if core_fcm.is_fcm_credentials_error(exc):
                        # Not retried, token kept (todo 566). It can be the
                        # device's (a dev-build token, an APNs-only fault). One
                        # ERROR per batch, below.
                        user_credentials_failed = True
                        last_credentials_exc = exc
                        continue
                    if core_fcm.is_permanent_fcm_error(exc):
                        if core_fcm.is_dead_fcm_token_error(exc):
                            # That device only (todos 457, 621).
                            core_fcm.clear_dead_fcm_token(user.pk, device_token)
                        logger.log(
                            _permanent_failure_level(exc),
                            "[FCM] forum.%s send failed permanently (user=%s): %s"
                            " — not retrying",
                            event,
                            user.pk,
                            exc,
                        )
                        continue
                    logger.warning(
                        "[FCM] forum.%s send failed (user=%s): %s — re-enqueuing single",
                        event,
                        user.pk,
                        exc,
                    )
                    transient.append(device_token)
            sent += user_sent
            if transient:
                # Hand off to the retry-capable single-recipient task rather than
                # retrying (and re-sending) the whole batch. When every device of
                # the account failed transiently it re-sends to all of them;
                # otherwise each failed device retries alone, so a device that
                # has the push never gets it twice (todo 621).
                # Guarded (todo 643 #1), as the credentials re-enqueue is: a
                # broker that refuses the hand-off (kombu's OperationalError) must
                # not abort the batch before the rest of it is tried and the
                # credentials ERROR below is logged. Only the exception's type is
                # logged: a broker message can carry its host or URL (#2).
                try:
                    # ``send_data``: a fold's retry is still the folded message
                    # (its folded rows are finished as covered below).
                    if len(transient) == len(devices):
                        # Marked so the single task never holds it for quiet
                        # hours; only the accepted answer is held there, so only
                        # it carries the flag (other events keep the message
                        # shape a worker from before it can still run).
                        flag = (
                            {"handed_off": True} if event == "answer_accepted" else {}
                        )
                        send_forum_push.delay(event, user.pk, send_data, **flag)
                    else:
                        for device_token in transient:
                            send_forum_push.delay(
                                event, user.pk, send_data, token=device_token
                            )
                except SoftTimeLimitExceeded:
                    # Not a broker failure: the outer guard releases this row
                    # instead of recording a hand-off that never happened
                    # (close review round 2).
                    raise
                except Exception as exc:
                    logger.error(
                        "[FCM] forum.%s re-enqueue single failed (user=%s): %s — "
                        "%s device(s) dropped",
                        event,
                        user.pk,
                        type(exc).__name__,
                        len(transient),
                    )
            # The outbox outcome (todo 624): a push on any device, or a hand-off
            # to send_forum_push's retries, finishes the row.
            delivered = bool(user_sent or transient)
            if send.row is not None:
                if time_limit_hit and not delivered:
                    # Cut off before any device had it: not a failure, re-driven.
                    _record(delivery.release, [send.row])
                elif user_sent:
                    outcomes["sent"].append(send.row)
                elif delivered:
                    # Handed off, not yet delivered: finished here (the single
                    # task owns the retries) but marked so reply coalescing does
                    # not anchor its window on a push that may never arrive.
                    outcomes["handed_off"].append(send.row)
                elif user_credentials_failed:
                    outcomes["credentials"].append(send.row)
                else:
                    outcomes["failed"].append(send.row)
            pacing.finish_folds(send, delivered)
            folds_finished = index
            if time_limit_hit:
                later = paced.sends[index + 1 :]
                _record(
                    delivery.release,
                    [s.row for s in later if s.row]
                    + [pk for s in later for pk in s.folded],
                )
                break
            if user_credentials_failed and not user_sent:
                # Counted per recipient, at the recipient boundary: stop only
                # when this many have failed and no send has worked yet, which is
                # the server's setup (owner decision 2026-10-11, todo 593 round 3).
                credentials_failed.append(user.pk)
                if (
                    not sent
                    and len(credentials_failed)
                    >= core_fcm.FCM_CREDENTIALS_STOP_FAILURES
                ):
                    untried = [later.user.pk for later in paced.sends[index + 1 :]]
                    untried_rows = [
                        later.row for later in paced.sends[index + 1 :] if later.row
                    ]
                    # With the rows each untried send had claimed for its fold,
                    # so the follow-up batch can fold them again.
                    untried_rows += [
                        pk for later in paced.sends[index + 1 :] for pk in later.folded
                    ]
                    # Handed back for the follow-up batch below or, failing
                    # that, reconciliation.
                    _record(delivery.release, untried_rows)
                    break
    except SoftTimeLimitExceeded as exc:
        time_limit_hit = exc
        recorded = {row for rows in outcomes.values() for row in rows}
        rest = paced.sends[index:]
        _record(
            delivery.release,
            [s.row for s in rest if s.row and s.row not in recorded]
            + [
                pk
                for n, s in enumerate(rest)
                if n or folds_finished != index
                for pk in s.folded
            ],
        )
    _record(delivery.mark_sent, outcomes["sent"])
    _record(delivery.mark_sent, outcomes["handed_off"], delivery.HANDED_OFF)
    _record(delivery.mark_failed, outcomes["failed"], "permanent")
    _record(delivery.mark_failed, outcomes["credentials"], "fcm_credentials")
    if time_limit_hit:
        logger.warning(
            "[FCM] forum.%s batch hit the soft time limit after %d send(s); "
            "the rest are released for reconciliation",
            event,
            sent,
        )
        raise time_limit_hit
    stop_note = ""
    if untried is not None:
        stop_note = (
            f"; batch stopped with no successful send, "
            f"{len(untried)} recipient(s) not tried"
        )
        if untried and not requeued:
            # Once only (owner decision 2026-10-11, todo 606): the stop can be
            # a few bad devices at the head of the batch, so the untried
            # recipients get one more batch. The users that already failed
            # are not in it. A follow-up that stops again drops its untried
            # recipients, so a real outage cannot loop.
            # Guarded (todo 631): a broker that refuses the message (kombu's
            # OperationalError, which autoretry_for does not cover) must not
            # fail the task before the ERROR below names the stop, and the
            # recipients it drops are counted there.
            try:
                requeue_kwargs: dict = {"requeued": True}
                if batch_id:
                    requeue_kwargs["batch_id"] = batch_id
                send_forum_push_batch.apply_async(
                    args=(event, untried, data),
                    kwargs=requeue_kwargs,
                    countdown=constants.FORUM_PUSH_REQUEUE_DELAY,
                )
            except Exception as exc:
                # The type only (todo 643 #2): a broker error's message can
                # carry its host or URL, which would reach the logs and Sentry.
                stop_note += (
                    f", re-enqueue failed ({type(exc).__name__}), "
                    f"{len(untried)} recipient(s) dropped"
                )
            else:
                stop_note += (
                    f", re-enqueued once in {constants.FORUM_PUSH_REQUEUE_DELAY}s"
                )
        elif untried:
            stop_note += ", dropped (this batch was already the re-enqueue)"
    if credentials_failed:
        logger.log(
            logging.ERROR,
            "[FCM] forum.%s send failed permanently on a Firebase credentials "
            "error for %s recipient(s) (users=%s): %s — not retrying, tokens "
            "kept%s",
            event,
            len(credentials_failed),
            credentials_failed,
            last_credentials_exc,
            stop_note,
        )


# The forum events with an email arm (todo 624 adds all but replies).
FORUM_EMAIL_EVENTS = frozenset({"reply_added", "mention", "quote", "answer_accepted"})
# The events whose recipient falls back to the reply email (one merged email).
REPLY_FALLBACK_EVENTS = frozenset({"mention", "quote"})


def _web_topic_path(topic_id: str | int | None, post_id: str | int | None) -> str:
    """The web app's link for a forum event: the topic, at the post."""
    from wagtail_forum.models import Topic

    topic = (
        Topic.objects.select_related("board").filter(pk=topic_id).first()
        if topic_id and str(topic_id).isdigit()
        else None
    )
    if topic is None:
        return "/forum"
    path = topic.get_absolute_url()
    return f"{path}#post-{post_id}" if str(post_id or "").isdigit() else path


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=constants.NOTIFICATION_BATCH_RETRY_DELAY,  # factor, see above
    max_retries=constants.NOTIFICATION_BATCH_MAX_RETRIES,
    # Sized to one chunk of recipients (todo 727), not the global 90 s/120 s.
    soft_time_limit=constants.NOTIFICATION_BATCH_SOFT_TIME_LIMIT,
    time_limit=constants.NOTIFICATION_BATCH_TIME_LIMIT,
    ignore_result=True,  # side-effect only; every call site enqueues and moves on
)
def send_forum_web_push_batch(
    event: str,
    recipient_user_ids: list[int],
    data: dict,
    batch_id: str | None = None,
):
    """Browser (Web Push) delivery of a forum event (todo 413).

    Its own task, enqueued beside the FCM push, so FCM's retries and its
    batch-to-single hand-off can never resend a browser notification. Same
    gates as FCM: ``forum_notifications`` and the per-event "push" preference,
    plus the send-time recheck (todo 619). Only events with tray copy are
    shown; a data-only event (e.g. moderation_decided) has nothing to render.
    A gone subscription (404/410) is deactivated by NotificationService.
    autoretry covers only the up-front fetch, which runs before any send.

    ``batch_id`` names the outbox rows ``dispatch`` wrote (todo 619). With
    it, only the recipients this run claims are sent to, and each one's
    outcome is recorded: a recipient that got the notification on at least
    one browser is done; one whose every browser failed transiently is
    retried by reconciliation with backoff; one with no browser left, or
    whose browsers all refused it for good, is finished. Without it (a
    message from before the outbox) nothing is recorded and a failed send
    is only logged, as before.

    Sends stay sequential inside a task (owner decision 2026-10-11, todo
    456): one shared session and one bulk ``last_used`` UPDATE, no thread
    pool. The recipients are chunked at enqueue, ``NOTIFICATION_BATCH_CHUNK_SIZE``
    per task (owner decision 2026-11-22, todo 727, which replaces that
    decision's "no chunked subtasks").
    """
    from apps.core import delivery
    from apps.users.models import PushSubscription
    from apps.users.services import (
        NotificationService,
        web_push_enabled,
        web_push_session,
    )
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from wagtail_forum.models import ForumProfile

    kind = delivery.Kind.FORUM_WEB_PUSH
    if not recipient_user_ids:
        return
    if not web_push_enabled():
        # Only when a recipient has a browser subscription (todo 623 review).
        report_push_unconfigured(
            "Web push (VAPID)",
            f"forum {event} pushes",
            has_work=lambda: PushSubscription.objects.filter(
                user_id__in=recipient_user_ids, is_active=True
            ).exists(),
        )
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "channel_off")
        return
    if _notification_content(event, data) is None:
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "no_tray_copy")
        return

    # A recipient with no ForumProfile row (e.g. a mentioned member who never
    # posted) has default preferences, so it wants the push: default a missing
    # row to None, as send_forum_email_batch does (PR #852 review).
    overrides_by_user = dict(
        ForumProfile.objects.filter(user_id__in=recipient_user_ids).values_list(
            "user_id", "notification_preferences"
        )
    )
    check = recheck(
        event,
        recipient_user_ids,
        data,
        "push",
        users=list(get_user_model().objects.filter(pk__in=recipient_user_ids)),
        overrides_by_user=overrides_by_user,
    )
    wanted = [user.pk for user in check.eligible]
    subscriptions = (
        list(
            PushSubscription.objects.filter(
                user_id__in=wanted, is_active=True
            ).select_related("user")
        )
        if wanted
        else []
    )
    # Claimed last, after every up-front read, so the OperationalError
    # autoretry can never find this run's own claim in its way.
    claimed = None
    if batch_id:
        claimed = delivery.claim_batch(kind, batch_id, recipient_user_ids)
        subscriptions = [s for s in subscriptions if s.user_id in claimed]
        with_browser = {s.user_id for s in subscriptions}
        suppressed: dict[str, list[int]] = {}
        for pk, row in claimed.items():
            reason = check.suppressed.get(pk)
            if reason is None and pk not in with_browser:
                reason = "no_destination"
            if reason is not None:
                suppressed.setdefault(reason, []).append(row)
        _record(delivery.mark_suppressed_by_reason, suppressed)
    # Quiet hours and reply coalescing (todo 624): a held recipient is not
    # sent to now; a fold's message covers its later replies.
    browsers = {s.user_id for s in subscriptions}
    with_browser_users = [user for user in check.eligible if user.pk in browsers]
    paced = pacing.pace_claimed(
        send_forum_web_push_batch,
        kind,
        event,
        data,
        batch_id,
        claimed,
        with_browser_users,
        recipient_user_ids,
    )
    sends = {send.user.pk: send for send in paced.sends}
    subscriptions = [s for s in subscriptions if s.user_id in sends]
    if not subscriptions:
        return
    rendered: dict = {}
    for pk, send in sends.items():
        send_data = pacing.folded_data(data, send)
        content = _notification_content(event, send_data)
        assert content is not None  # the event passed the copy check above
        title, body = content
        url = _web_topic_path(send_data.get("topic_id"), send_data.get("post_id"))
        tag = (
            f"forum-{event}-"
            f"{send_data.get('post_id') or send_data.get('topic_id') or ''}"
        )
        rendered[pk] = (title, body, url, tag)

    # One session for the whole batch, so every send to a push service reuses
    # its pooled TLS connection, with redirects off (todo 456 items 3 and 6).
    # last_used is written once for every row sent, not once per send.
    sent = []
    delivered_users: set[int] = set()
    transient_users: set[int] = set()
    # The soft time limit stops the batch: what was sent is recorded, everyone
    # else is released for reconciliation, then it is re-raised (audit M3).
    time_limit_hit: SoftTimeLimitExceeded | None = None
    with web_push_session() as session:
        try:
            for subscription in subscriptions:
                title, body, url, tag = rendered[subscription.user_id]
                if NotificationService.send_web_push_notification(
                    subscription,
                    title=title,
                    body=body,
                    icon="/favicon.svg",
                    badge="/favicon.svg",
                    data={"url": url, "event": event},
                    tag=tag,
                    requests_session=session,
                    mark_used=False,
                ):
                    sent.append(subscription.pk)
                    delivered_users.add(subscription.user_id)
                elif subscription.is_active:
                    # Still active, so not a 404/410: worth another attempt.
                    transient_users.add(subscription.user_id)
        except SoftTimeLimitExceeded as exc:
            time_limit_hit = exc
    # The limit can also land in this bookkeeping (it is a signal): the
    # outcomes below are still written before it is re-raised (Phase 6 review).
    try:
        if sent:
            # Never let this bookkeeping raise: an OperationalError here would
            # autoretry the task and send every notification again.
            try:
                PushSubscription.objects.filter(pk__in=sent).update(
                    last_used=timezone.now()
                )
            except OperationalError:
                logger.warning(
                    "[WEB_PUSH] Could not record last_used for %d sent subscription(s)",
                    len(sent),
                )
        for pk, send in sends.items():
            pacing.finish_folds(send, pk in delivered_users)
    except SoftTimeLimitExceeded as exc:
        time_limit_hit = time_limit_hit or exc
    if claimed is not None and time_limit_hit:
        retry = transient_users - delivered_users
        cut_off = {s.user_id for s in subscriptions} - delivered_users - retry
        _record(delivery.mark_sent, [claimed[pk] for pk in delivered_users])
        _record(delivery.mark_retry, [claimed[pk] for pk in retry], "web_push_failed")
        _record(delivery.release, [claimed[pk] for pk in cut_off])
    elif claimed is not None:
        attempted = {s.user_id for s in subscriptions}
        retry = transient_users - delivered_users
        _record(delivery.mark_sent, [claimed[pk] for pk in delivered_users])
        _record(delivery.mark_retry, [claimed[pk] for pk in retry], "web_push_failed")
        _record(
            delivery.mark_failed,
            [claimed[pk] for pk in attempted - delivered_users - retry],
            "subscription_gone",
        )
        if retry:
            logger.warning(
                "[WEB_PUSH] forum.%s: %d recipient(s) failed on every browser; "
                "retrying with backoff",
                event,
                len(retry),
            )
    if time_limit_hit:
        logger.warning(
            "[WEB_PUSH] forum.%s batch hit the soft time limit after %d send(s); "
            "the rest are released for reconciliation",
            event,
            len(sent),
        )
        raise time_limit_hit


def recipient_chunks(recipient_ids) -> list[list[int]]:
    """``recipient_ids`` in lists of at most ``NOTIFICATION_BATCH_CHUNK_SIZE``
    (todo 727): one batch task per list, so a task's work and its time limits
    are sized to a chunk whatever the topic's follower count."""
    ids = list(recipient_ids)
    size = constants.NOTIFICATION_BATCH_CHUNK_SIZE
    return [ids[start : start + size] for start in range(0, len(ids), size)]


def _record(mark, *args):
    """Run one outbox bookkeeping write without letting it raise into a task
    that has already sent (todo 619): an OperationalError here would trigger
    the task's autoretry. A row left claimed is re-driven after its lease,
    the documented at-least-once window."""
    if not args[0]:
        return
    try:
        mark(*args)
    except OperationalError as exc:
        logger.error(
            "[DELIVERY] could not record a delivery outcome: %s", type(exc).__name__
        )


def _finish_unclaimed_batch(kind, batch_id, recipient_ids, reason):
    """A batch whose channel cannot run at all is finished, not left pending
    for reconciliation to re-drive until it expires."""
    from apps.core import delivery

    if not batch_id:
        return
    claimed = delivery.claim_batch(kind, batch_id, recipient_ids)
    _record(delivery.mark_suppressed, list(claimed.values()), reason)


def redrive_forum_deliveries(rows) -> None:
    """Reconciliation's redriver for forum email and browser push (todo 619):
    re-enqueue each batch's due recipients to the task that owns the
    channel, with the same batch id, so the task claims, rechecks and sends
    exactly as it would have the first time."""
    from apps.core import delivery

    tasks = {
        delivery.Kind.FORUM_EMAIL: send_forum_email_batch,
        delivery.Kind.FORUM_WEB_PUSH: send_forum_web_push_batch,
        delivery.Kind.FORUM_PUSH: send_forum_push_batch,
    }
    groups: dict = {}
    folding: set = set()
    for row in sorted(rows, key=lambda row: (row.created_at, row.pk)):
        if row.event in pacing.COALESCED_EVENTS:
            # One coalesced reply per member, topic and channel (todo 624):
            # the oldest folds the rest, which stay pending for it.
            key = (row.kind, row.recipient_id, str(row.payload.get("topic_id")))
            if key in folding:
                continue
            folding.add(key)
        groups.setdefault((row.kind, str(row.batch_id), row.event), []).append(row)
    for (kind, batch_id, event), group in groups.items():
        # Chunked like the first enqueue (todo 727). Not guarded per chunk: a
        # broker error must reach reconcile(), which logs it; every row is
        # still pending and due again after the redrive interval.
        for chunk in recipient_chunks([row.recipient_id for row in group]):
            tasks[kind].delay(event, chunk, group[0].payload, batch_id=batch_id)


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=constants.NOTIFICATION_BATCH_RETRY_DELAY,  # factor, see above
    max_retries=constants.NOTIFICATION_BATCH_MAX_RETRIES,
    # Sized to one chunk of recipients (todo 727), not the global 90 s/120 s.
    soft_time_limit=constants.NOTIFICATION_BATCH_SOFT_TIME_LIMIT,
    time_limit=constants.NOTIFICATION_BATCH_TIME_LIMIT,
    ignore_result=True,  # side-effect only; every call site enqueues and moves on
)
def send_forum_email_batch(
    event: str,
    recipient_user_ids: list[int],
    data: dict,
    batch_id: str | None = None,
):
    """Send forum reply-notification emails to many recipients from a SINGLE
    enqueue (todo 268), replacing the per-recipient send_forum_email fan-out.

    The Post and all recipient Users are fetched ONCE up front, then the loop
    only calls NotificationService — whose send path
    (EmailService.send_email()) swallows every send/render failure and returns a
    bool, so a send failure never raises. The one exception is a Warning
    (RemovedInDjango70Warning under pytest.ini's deprecation gate, todos 454
    and 537): it is re-raised on purpose to fail the test run, and it is not
    an OperationalError, so it can never trigger the retry.

    This ordering is load-bearing: email has no collapse-key dedup, so
    autoretry_for=(OperationalError,) must be able to fire ONLY before any
    email is sent, or a transient-DB retry would double-email everyone. All
    OperationalError-raising DB access happens in the up-front fetch and the
    claim; the send loop's only DB access is the per-recipient outcome write,
    which is guarded (``_record``) and never raises.

    Send-time recheck (todo 619): every run, first or retried, drops a
    recipient who is no longer eligible (``eligibility.recheck``: inactive,
    opted out, no address, and for a dispatched payload a hidden post, a
    block/mute against its author, or an unfollowed topic).

    Outbox (todo 619): with ``batch_id`` (the rows ``dispatch`` wrote), only
    the recipients this run claims are emailed, one outcome is recorded per
    recipient right after its send, and a transient SMTP failure goes back
    to the outbox with backoff for reconciliation to re-drive — to that
    recipient alone. An opt-out, a missing address or a permanent rejection
    is finished, never retried. Without ``batch_id`` (a message from before
    the outbox) nothing is recorded and a failed send is only logged.

    Important-event email (todo 624, owner decision 2026-10-12): mentions,
    quotes and accepted answers have an optional email too, off by default.
    A mentioned or quoted subscriber gets ONE email: the mention (or quote)
    email when that cell is on, else the reply email when they follow the
    topic and want reply email, else none. Each email's unsubscribe link
    turns off the cell that let it through.

    Quiet hours and reply coalescing (todo 624, ``pacing``) hold a claimed
    recipient's row instead of sending; a coalesced reply email covers every
    later reply on the topic still waiting for that member.

    Args:
        event: "reply_added", "mention", "quote" or "answer_accepted".
        recipient_user_ids: pks of the Users to email.
        data: the shared payload dict — carries "post_id" (str). The reply Post
              is fetched here (once for the batch) so push's data stays minimal
              and the email reflects the post at send time.
        batch_id: the outbox batch to claim from, or None.
    """
    from apps.core import delivery
    from apps.core.services.email_service import EmailOutcome

    kind = delivery.Kind.FORUM_EMAIL
    if event not in FORUM_EMAIL_EVENTS:
        logger.debug(
            "[EMAIL] forum email skipped — event=%s not implemented yet", event
        )
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "no_email_arm")
        return

    if not recipient_user_ids:
        return

    from apps.core.services.notification_service import NotificationService
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from wagtail_forum.api.serializers import forum_display_name
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
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "content_missing")
        return
    except Post.DoesNotExist:
        logger.warning("[EMAIL] forum email skipped — post %s not found", post_id)
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "content_missing")
        return

    # Materialize up front so a transient OperationalError can only fire here,
    # before any email is sent (see the docstring's retry-safety note).
    users = list(User.objects.filter(pk__in=recipient_user_ids))
    # Per-event email preference (todo 343): one bulk fetch; a user with no
    # profile row has no overrides and gets the defaults.
    from wagtail_forum.models import ForumProfile

    overrides_by_user = dict(
        ForumProfile.objects.filter(user_id__in=recipient_user_ids).values_list(
            "user_id", "notification_preferences"
        )
    )
    check = recheck(
        event,
        [user.pk for user in users],
        data,
        "email",
        users=users,
        overrides_by_user=overrides_by_user,
    )
    # One merged email (todo 624): a mentioned or quoted member whose email
    # cell for this event is off still gets the reply email they asked for,
    # if they follow the topic (the reply recheck checks that).
    via_reply: set[int] = set()
    fallback = [pk for pk, why in check.suppressed.items() if why == REASON_PREFERENCE]
    if event in REPLY_FALLBACK_EVENTS and fallback:
        reply_check = recheck(
            "reply_added",
            fallback,
            data,
            "email",
            users=[user for user in users if user.pk in set(fallback)],
            overrides_by_user=overrides_by_user,
        )
        # Read-before-send for the event itself: the reply recheck looks at
        # REPLY bell rows, and a mentioned or quoted member has only the
        # MENTION or QUOTE row, which they may have read already.
        read = already_read_ids(
            event, reply_check.post, [user.pk for user in reply_check.eligible]
        )
        for user in reply_check.eligible:
            if user.pk in read:
                check.suppressed[user.pk] = REASON_READ
                continue
            check.suppressed.pop(user.pk, None)
            check.eligible.append(user)
            via_reply.add(user.pk)
    for pk, reason in check.suppressed.items():
        if reason == "no_destination":
            # A clear skip log at this layer for a user with no email on
            # file. (Belt-and-suspenders: since todo 267,
            # EmailService.send_email() also returns False rather than a
            # phantom True for a 0-recipient send.)
            logger.warning(
                "[EMAIL] forum email skipped — user %s has no email on file", pk
            )
        else:
            logger.debug(
                "[EMAIL] forum email skipped — user %s not eligible for %s (%s)",
                pk,
                event,
                reason,
            )

    claimed = None
    if batch_id:
        # After every up-front read: the autoretry above can never meet
        # this run's own claim. Recipients someone else holds, or that
        # already have it, are not ours to send.
        claimed = delivery.claim_batch(kind, batch_id, recipient_user_ids)
        eligible_pks = {user.pk for user in check.eligible}
        suppressed: dict[str, list[int]] = {}
        for pk, row in claimed.items():
            reason = check.suppressed.get(pk)
            if reason is None and pk not in eligible_pks:
                reason = "recipient_missing"
            if reason is not None:
                suppressed.setdefault(reason, []).append(row)
        _record(delivery.mark_suppressed_by_reason, suppressed)

    paced = pacing.pace_claimed(
        send_forum_email_batch,
        kind,
        event,
        data,
        batch_id,
        claimed,
        check.eligible,
        recipient_user_ids,
    )

    topic = post.topic
    # The web app's thread route, at the reply's own anchor (ThreadDetailPage
    # renders id="post-<id>", as _web_topic_path links for push). The bare
    # topic URL stays the fallback link. rstrip: a SITE_URL ending in "/"
    # would otherwise build "//forum/..." (todo 622).
    # `or ""`: an unset SITE_URL must not fail the whole batch with an
    # AttributeError a retry cannot fix (todo 639; email_service guards alike).
    site_url = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    topic_url = f"{site_url}{topic.get_absolute_url()}"
    service = NotificationService()
    # The accepted answer's email names who accepted it, not the post's
    # author (the recipient): dispatch puts the acceptor in actor_name, and
    # "Someone" stands in when there is none. The excerpt keeps its real
    # author (the recipient's own answer), never the acceptor.
    actor_override = (
        (str(data.get("actor_name") or "") or "Someone")
        if event == "answer_accepted"
        else None
    )

    for index, send in enumerate(paced.sends):
        user = send.user
        shown = send.latest or post
        post_url = f"{topic_url}#post-{shown.pk}"
        # The forum name, never the legal name (audit 2026-11-21 H1).
        author_name = forum_display_name(shown.author) if shown.author else "[deleted]"
        excerpt = plain_text_excerpt(shown.body, FORUM_EMAIL_EXCERPT_MAX_CHARS)
        service.email_service.last_outcome = None
        try:
            if event == "reply_added" or user.pk in via_reply:
                sent = service.send_forum_reply_notification(
                    user=user,
                    topic_title=topic.title,
                    reply_author=author_name,
                    reply_excerpt=excerpt,
                    topic_url=topic_url,
                    post_url=post_url,
                    count=send.count,
                )
            else:
                sent = service.send_forum_event_notification(
                    user=user,
                    event=event,
                    topic_title=topic.title,
                    actor_name=actor_override or author_name,
                    post_excerpt=excerpt,
                    topic_url=topic_url,
                    post_url=post_url,
                    author_name=author_name,
                )
        except SoftTimeLimitExceeded:
            # The deadline, not a failed send (audit 2026-11-21 M3). Every
            # outcome so far is already recorded; this recipient (SMTP may
            # have accepted it: at-least-once) and the rest are released for
            # reconciliation, then the limit is re-raised.
            later = paced.sends[index:]
            pacing.finish_folds(send, False)
            _record(
                delivery.release,
                [s.row for s in later if s.row]
                + [pk for s in later[1:] for pk in s.folded],
            )
            logger.warning(
                "[EMAIL] forum.%s batch hit the soft time limit; %d recipient(s) "
                "released for reconciliation",
                event,
                len(later),
            )
            raise
        logger.info("[EMAIL] forum.%s email to user=%s: sent=%s", event, user.pk, sent)
        # The outcome is recorded before the fold bookkeeping, so a soft limit
        # landing there (it is a signal) cannot leave a sent row claimed for a
        # resend after the lease (Phase 6 review).
        if send.row is not None:
            rows = [send.row]
            if sent:
                _record(delivery.mark_sent, rows)
            else:
                # A False that is not a transport failure is never retried. A
                # send that never reached send_email (no copy for the event)
                # says PERMANENT itself (todo 652); an outcome still unset
                # means an error escaped send_email before it sent (a database
                # read), worth a retry.
                outcome = service.email_service.last_outcome or EmailOutcome.TRANSIENT
                if outcome == EmailOutcome.SUPPRESSED:
                    # A provider suppression (bounce, complaint) is not an
                    # opt-out: recorded as such, as the account tasks do (625).
                    reason = (
                        service.email_service.last_suppression_reason
                        or "preference_off"
                    )
                    _record(delivery.mark_suppressed, rows, reason)
                elif outcome == EmailOutcome.PERMANENT:
                    _record(delivery.mark_failed, rows, "permanent")
                else:
                    _record(delivery.mark_retry, rows, "smtp_transient")
        pacing.finish_folds(send, bool(sent))


def _permanent_embedding_errors() -> tuple[type[BaseException], ...]:
    """The embedding provider's errors that a retry cannot fix (todo 732,
    audit 2026-11-21 L12): a bad or revoked key, a missing key, no access,
    and a request the provider rejects as malformed.

    Both families are listed because ``any_llm`` raises the OpenAI SDK's own
    classes unless its unified exceptions are switched on, and its own when
    they are. Named one by one, never ``openai.APIStatusError``: that base
    also covers 429 and 5xx, which stay on the retry path with timeouts and
    connection errors. Imported here, not at module import: this module is
    loaded by every web process, which never needs the SDK."""
    errors: list[type[BaseException]] = []
    try:
        import openai

        errors += [
            openai.AuthenticationError,  # 401
            openai.PermissionDeniedError,  # 403
            openai.BadRequestError,  # 400
            openai.NotFoundError,  # 404 (no such model)
            openai.UnprocessableEntityError,  # 422
        ]
    except ImportError:  # pragma: no cover - the SDK is a hard dependency
        pass
    try:
        from any_llm import exceptions as any_llm_errors

        errors += [
            any_llm_errors.AuthenticationError,
            any_llm_errors.MissingApiKeyError,
            any_llm_errors.InvalidRequestError,
            any_llm_errors.ModelNotFoundError,
            any_llm_errors.ContextLengthExceededError,
            any_llm_errors.UnsupportedParameterError,
        ]
    except ImportError:  # pragma: no cover - the SDK is a hard dependency
        pass
    return tuple(errors)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    # The BACKOFF FACTOR, not a bool: True would mean factor 1 (~1s/2s/4s
    # jittered) and default_retry_delay is never read on the autoretry path.
    retry_backoff=constants.RAG_INDEX_RETRY_DELAY,
    max_retries=constants.RAG_INDEX_MAX_RETRIES,
    acks_late=True,
    ignore_result=True,  # side-effect only; nothing reads the result
)
def sync_blog_page_chunks(self, page_id: int) -> None:
    """Re-chunk + re-embed ONE blog page into the ``BlogChunks`` index, or
    purge it (todo 289 / M13). Enqueued (post-commit) by the page-lifecycle
    receivers in ``signals.py`` on publish / unpublish / delete.

    Idempotent (purge-then-add on the page's own key prefix, with the page's
    live/public state re-checked INSIDE the swap transaction so a run whose
    embed straddled a concurrent unpublish cannot add the page back), so
    ``acks_late`` and ``autoretry_for=(Exception,)`` are safe: a retry after a
    provider or DB blip redoes exactly one page. A chunking failure is a
    PERMANENT error (malformed content_blocks) and is logged, not retried.
    So is a provider error no retry can fix (todo 732): a bad or revoked key
    or a 4xx request error (``_permanent_embedding_errors``) is logged once
    at ERROR with the page id and the task ends, the existing chunks kept.
    It is caught here, not listed in ``dont_autoretry_for``: that would
    re-raise it, and Celery's own failure trace would log it a second time.
    Timeouts, connection errors, 429, 5xx and ``SoftTimeLimitExceeded`` are
    not in that list and are retried as before.
    Per-page work goes through the transformer and the storage provider
    DIRECTLY, not ``index.update()`` — that ends in ``post_index_update``,
    which deletes and re-registers a ``ModelSourceIndex`` row for EVERY object
    in the source queryset on every call.

    Embeds first (network), then swaps the rows in one transaction, so the old
    chunks keep serving until the new ones are ready and a failed embed leaves
    the store as it was. ``CachedEmbeddingTransformer`` makes unchanged chunks
    free. When the feature is off or the page is no longer live+public, only
    the purge runs: deleting is free, embedding is not.
    """
    from apps.blog.models import BlogPostPage
    from django.db import transaction
    from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding

    from .vector_indexes import BlogChunks, _index_name, rag_enabled

    stale = PgVectorEmbedding.objects.filter(
        index_name=_index_name(BlogChunks),
        document_key__startswith=f"blog.BlogPostPage:{page_id}:",
    )
    live_public = BlogPostPage.objects.live().public().filter(pk=page_id)
    page = live_public.first()
    if page is None or not rag_enabled():
        deleted, _ = stale.delete()
        logger.info(
            "[CELERY] blog page %s: purged %d chunk(s), nothing to embed (%s)",
            page_id,
            deleted,
            "page not live/public" if page is None else "feature off",
        )
        return

    index = BlogChunks()
    try:
        documents = list(index.sources[0].objects_to_documents(page))
    except Exception:
        # Deterministic on this content — retrying cannot help. Keep the
        # existing rows (stale content beats none) and make it visible.
        logger.exception(
            "[CELERY] blog page %s: chunking failed; existing chunks kept", page_id
        )
        return
    try:
        embedded = index.embedding_transformer.embed_documents(
            documents, batch_size=100
        )
    except _permanent_embedding_errors() as exc:
        # The class name only: a provider's auth message can quote part of
        # the key it rejected.
        logger.error(
            "[ERROR] blog page %s: the embedding provider refused the request "
            "(%s); not retrying, existing chunks kept",
            page_id,
            type(exc).__name__,
        )
        return
    with transaction.atomic():
        stale.delete()
        # Re-checked here, not just above: the embed is a network round-trip
        # during which an unpublish/delete (and its own purge) may have landed.
        if embedded and rag_enabled() and live_public.exists():
            index.storage_provider.add(embedded)
        else:
            embedded = []
    logger.info("[CELERY] blog page %s: indexed %d chunk(s)", page_id, len(embedded))


@shared_task(
    bind=True,
    max_retries=constants.SUMMARY_MAX_RETRIES,
    default_retry_delay=constants.SUMMARY_RETRY_DELAY,
    ignore_result=True,  # side-effect only (writes the cache); nothing reads it
)
def generate_topic_summary(self, topic_id: int) -> None:
    """Generate + cache an AI summary for a forum topic (todo 255 slice 3 / H14).

    Enqueued by ``TopicSummaryView`` on a cache miss. Bounded by the Celery soft
    time limit (there is no request/atomic path here, unlike the spam backend,
    so no thread-pool timeout wrapper is needed). A transient provider error
    retries with exponential backoff; a hit global AI budget degrades to a no-op
    (a cost decision, not an outage — retrying would only burn the budget
    further). Idempotent: a racing task that already cached this exact thread
    state is a no-op.
    """
    from apps.blog.services.ai_cache_service import AICacheService
    from apps.blog.services.ai_rate_limiter import AIRateLimiter
    from apps.blog.wagtail_ai_v3_integration import generate_ai_text
    from django.core.cache import cache
    from django.utils import timezone
    from wagtail_forum.api.views import _visible_boards
    from wagtail_forum.models import Topic

    from .summary import _pending_lock_key, build_summary_source

    # Defense in depth: the same board-visibility guard the endpoint enforces —
    # a restricted-board (PageViewRestriction) topic is never summarized even if
    # a task were somehow enqueued for one.
    topic = Topic.objects.filter(
        pk=topic_id, live=True, board__in=_visible_boards()
    ).first()
    if topic is None:
        logger.info("[CELERY] topic %s missing/unpublished; skipping summary", topic_id)
        return

    # Deliberately NOT block-filtered (todo 284/M9): build_summary_source's
    # own docstring in summary.py records why (shared, content-hash-keyed
    # LLM cache — per-viewer filtering would fragment a cost-governed cache).
    content, post_count = build_summary_source(topic)
    if post_count < constants.SUMMARY_MIN_POSTS:
        return

    if AICacheService.get_cached_response(constants.SUMMARY_CACHE_FEATURE, content):
        # A racing task already produced the summary for this exact thread state.
        return

    # Peek, then charge only a call that returned (audit 2026-11-21 M4):
    # check_global_limit billed every attempt, so a retried outage spent three
    # budget slots for no summary.
    if not AIRateLimiter.peek_budget(
        constants.SUMMARY_BUDGET_CACHE_KEY, constants.SUMMARY_BUDGET_LIMIT
    ):
        logger.info(
            "[PERF] topic summary skipped for %s: summary AI budget exhausted",
            topic_id,
        )
        # A terminal exit frees the pending lock, so the long worst-case TTL
        # never blocks a later poll's fresh attempt (M4).
        cache.delete(_pending_lock_key(content))
        return

    prompt = constants.SUMMARY_PROMPT_TEMPLATE.format(content=content)
    try:
        summary = generate_ai_text(prompt, alias=constants.SUMMARY_ALIAS)
    except Exception as exc:
        logger.warning(
            "[ERROR] topic summary generation failed for %s: %s", topic_id, exc
        )
        if self.request.retries >= self.max_retries:
            cache.delete(_pending_lock_key(content))  # the last attempt
        raise self.retry(
            exc=exc,
            countdown=self.default_retry_delay * (2**self.request.retries),
        ) from exc

    # Charged before the emptiness check: an empty completion still reached
    # the provider and was billed (the compose-assist rule).
    AIRateLimiter.consume_budget(
        constants.SUMMARY_BUDGET_CACHE_KEY, constants.SUMMARY_BUDGET_LIMIT
    )

    if not summary or not summary.strip():
        # An empty completion is a transient provider glitch, never a real
        # summary — caching it would serve blank for the whole 30-day TTL. Treat
        # it like any transient failure: retry with backoff, never cache.
        logger.warning("[ERROR] topic summary empty for %s; retrying", topic_id)
        if self.request.retries >= self.max_retries:
            cache.delete(_pending_lock_key(content))  # the last attempt
        raise self.retry(
            exc=ValueError("empty summary"),
            countdown=self.default_retry_delay * (2**self.request.retries),
        )

    AICacheService.set_cached_response(
        constants.SUMMARY_CACHE_FEATURE,
        content,
        {
            "summary": summary,
            "post_count": post_count,
            "generated_at": timezone.now().isoformat(),
        },
    )
    logger.info(
        "[CACHE] cached AI summary for topic %s (%s posts)", topic_id, post_count
    )
