"""Celery tasks for forum push (Issue 14) and email (todo 253 slice 2, H1)
notifications.

Fired by forum_host/notifications.py dispatch() via .delay() so that:
- The publish transaction is never held open waiting for FCM/SMTP.
- A failed delivery never rolls back a moderation decision.
- Tasks are retried automatically by Celery on their respective transient
  error classes (FCM send errors for push; OperationalError for email).
"""

import logging

from apps.core import fcm as core_fcm
from celery import shared_task
from django.db import OperationalError
from wagtail_forum.preferences import wants_channel

from . import constants
from .eligibility import client_payload, recheck

logger = logging.getLogger("forum_host.tasks")


# Sized for a cohort, not a single object: the global 90 s/120 s limits are
# for the per-post tasks below. A digest run costs a few queries + one SMTP
# round-trip per due member; ~1,500 members fit in 25 minutes at 1 s each.
DIGEST_SOFT_TIME_LIMIT = 25 * 60
DIGEST_TIME_LIMIT = 30 * 60
DIGEST_CONTINUATION_DELAY = 60


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=60,  # seconds; a transient DB blip retries in 1/2/4 min
    max_retries=3,
    soft_time_limit=DIGEST_SOFT_TIME_LIMIT,
    time_limit=DIGEST_TIME_LIMIT,
    ignore_result=True,
)
def send_forum_weekly_digest(self, recovery: int = 0):
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
    """
    from io import StringIO

    from apps.core.delivery import schedule_weekly_recovery
    from celery.exceptions import SoftTimeLimitExceeded
    from django.core.management import call_command

    logger.info("[EMAIL] forum weekly digest: starting (task=%s)", self.request.id)
    out = StringIO()
    try:
        call_command("send_forum_digest", frequency="weekly", stdout=out)
    except SoftTimeLimitExceeded:
        logger.warning(
            "[EMAIL] forum weekly digest hit the soft time limit (task=%s); "
            "re-enqueuing to finish the members still due",
            self.request.id,
        )
        # A continuation keeps its run's recovery count (todo 619).
        extra = {"kwargs": {"recovery": recovery}} if recovery else {}
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
    schedule_weekly_recovery(
        send_forum_weekly_digest, out.getvalue(), recovery, "forum weekly digest"
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

    return push_content(event, topic_title, actor)


def _forum_collapse_key(event: str) -> str:
    """Per EVENT TYPE, not per post (see docs/rules/celery.md)."""
    return f"forum-{event}"


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_forum_push(
    self, event: str, recipient_user_id: int, data: dict, token: str | None = None
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

    A transient failure retries this task only when no device got the push;
    otherwise each failed device is handed to its own retry (``token=``).
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from apps.core.push_devices import device_tokens_for_users
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
    tokens = device_tokens_for_users([recipient_user_id]).get(recipient_user_id, [])
    if token is not None:
        tokens = [t for t in tokens if t == token]
    if not tokens:
        logger.debug(
            "[FCM] forum push skipped — user %s has no FCM token", recipient_user_id
        )
        return

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
        for device_token, exc in transient:
            logger.warning(
                "[FCM] forum.%s send failed on one device (user=%s, task_id=%s):"
                " %s — retrying that device",
                event,
                recipient_user_id,
                self.request.id,
                exc,
            )
            send_forum_push.delay(event, recipient_user_id, data, token=device_token)
        return
    exc = transient[-1][1]
    logger.warning(
        "[FCM] forum.%s send failed (user=%s, task_id=%s): %s — retrying",
        event,
        recipient_user_id,
        self.request.id,
        exc,
    )
    # Every device failed transiently: retry the task. Exponential backoff:
    # 30s, 60s, 120s across max_retries=3. A ``token=`` retry keeps its
    # token, which rides in the request kwargs.
    raise self.retry(
        exc=exc, countdown=self.default_retry_delay * (2**self.request.retries)
    )


@shared_task(
    autoretry_for=(OperationalError,),
    # The BACKOFF FACTOR (30s/60s/120s jittered ceiling), not a bool — True
    # meant factor 1, ~1s/2s/4s (audit 2026-09-04 M8; see the sibling
    # sync_blog_page_chunks and constants.NOTIFICATION_BATCH_RETRY_DELAY).
    retry_backoff=constants.NOTIFICATION_BATCH_RETRY_DELAY,
    max_retries=constants.NOTIFICATION_BATCH_MAX_RETRIES,
    ignore_result=True,  # side-effect only; every call site is a bare .delay()
)
def send_forum_push_batch(
    event: str, recipient_user_ids: list[int], data: dict, requeued: bool = False
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
    """
    from apps.core.firebase_config import get_fcm_client, is_firebase_available
    from apps.core.push_devices import device_tokens_for_users
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

    str_data = {k: str(v) for k, v in client_payload(data).items()}
    str_data["event"] = event
    content = _notification_content(event, data)

    sent = 0
    credentials_failed: list[int] = []
    last_credentials_exc: Exception | None = None
    # The recipients a credentials stop left untried: only those this batch
    # would have sent to, so the count is not inflated by opted-out, muted or
    # tokenless profiles (todo 606).
    untried: list[int] | None = None
    for index, profile in enumerate(profiles):
        user = profile.user
        if not wants_push(profile):
            continue
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
                if len(transient) == len(devices):
                    send_forum_push.delay(event, user.pk, data)
                else:
                    for device_token in transient:
                        send_forum_push.delay(event, user.pk, data, token=device_token)
            except Exception as exc:
                logger.error(
                    "[FCM] forum.%s re-enqueue single failed (user=%s): %s — "
                    "%s device(s) dropped",
                    event,
                    user.pk,
                    type(exc).__name__,
                    len(transient),
                )
        if user_credentials_failed and not user_sent:
            # Counted per recipient, at the recipient boundary: stop only
            # when this many have failed and no send has worked yet, which is
            # the server's setup (owner decision 2026-10-11, todo 593 round 3).
            credentials_failed.append(user.pk)
            if (
                not sent
                and len(credentials_failed) >= core_fcm.FCM_CREDENTIALS_STOP_FAILURES
            ):
                untried = [p.user_id for p in profiles[index + 1 :] if wants_push(p)]
                break
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
                send_forum_push_batch.apply_async(
                    args=(event, untried, data),
                    kwargs={"requeued": True},
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


def _web_topic_path(topic_id: str | int | None, post_id: str | int | None) -> str:
    """The web app's link for a forum event: the topic, at the post."""
    from wagtail_forum.models import Topic

    topic = (
        Topic.objects.select_related("board").filter(pk=topic_id).first()
        if str(topic_id or "").isdigit()
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
    ignore_result=True,  # side-effect only; every call site is a bare .delay()
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

    Sends stay sequential in this one task (owner decision 2026-10-11, todo
    456): one shared session and one bulk ``last_used`` UPDATE, no chunked
    subtasks or thread pool until a topic's fan-out proves it needs them.
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
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "channel_off")
        return
    content = _notification_content(event, data)
    if content is None:
        _finish_unclaimed_batch(kind, batch_id, recipient_user_ids, "no_tray_copy")
        return
    title, body = content

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
        suppressed = {}
        for pk, row in claimed.items():
            reason = check.suppressed.get(pk)
            if reason is None and pk not in with_browser:
                reason = "no_destination"
            if reason is not None:
                suppressed.setdefault(reason, []).append(row)
        _record(delivery.mark_suppressed_by_reason, suppressed)
    if not subscriptions:
        return
    url = _web_topic_path(data.get("topic_id"), data.get("post_id"))
    tag = f"forum-{event}-{data.get('post_id') or data.get('topic_id') or ''}"

    # One session for the whole batch, so every send to a push service reuses
    # its pooled TLS connection, with redirects off (todo 456 items 3 and 6).
    # last_used is written once for every row sent, not once per send.
    sent = []
    delivered_users: set[int] = set()
    transient_users: set[int] = set()
    with web_push_session() as session:
        for subscription in subscriptions:
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
    if claimed is not None:
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
    }
    groups: dict = {}
    for row in rows:
        groups.setdefault((row.kind, str(row.batch_id), row.event), []).append(row)
    for (kind, batch_id, event), group in groups.items():
        tasks[kind].delay(
            event,
            [row.recipient_id for row in group],
            group[0].payload,
            batch_id=batch_id,
        )


@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=constants.NOTIFICATION_BATCH_RETRY_DELAY,  # factor, see above
    max_retries=constants.NOTIFICATION_BATCH_MAX_RETRIES,
    ignore_result=True,  # side-effect only; every call site is a bare .delay()
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

    Args:
        event: only "reply_added" is wired (todo 253 slice 2, H1); mention/
               moderation/digest are later slices.
        recipient_user_ids: pks of the Users to email.
        data: the shared payload dict — carries "post_id" (str). The reply Post
              is fetched here (once for the batch) so push's data stays minimal
              and the email reflects the post at send time.
        batch_id: the outbox batch to claim from, or None.
    """
    from apps.core import delivery
    from apps.core.services.email_service import EmailOutcome

    kind = delivery.Kind.FORUM_EMAIL
    if event != "reply_added":
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
        suppressed = {}
        for pk, row in claimed.items():
            reason = check.suppressed.get(pk)
            if reason is None and pk not in eligible_pks:
                reason = "recipient_missing"
            if reason is not None:
                suppressed.setdefault(reason, []).append(row)
        _record(delivery.mark_suppressed_by_reason, suppressed)

    topic = post.topic
    # The web app's thread route, at the reply's own anchor (ThreadDetailPage
    # renders id="post-<id>", as _web_topic_path links for push). The bare
    # topic URL stays the fallback link. rstrip: a SITE_URL ending in "/"
    # would otherwise build "//forum/..." (todo 622).
    # `or ""`: an unset SITE_URL must not fail the whole batch with an
    # AttributeError a retry cannot fix (todo 639; email_service guards alike).
    site_url = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    topic_url = f"{site_url}{topic.get_absolute_url()}"
    post_url = f"{topic_url}#post-{post.pk}"
    author_name = post.author.display_name if post.author else "[deleted]"
    excerpt = plain_text_excerpt(post.body, FORUM_EMAIL_EXCERPT_MAX_CHARS)
    service = NotificationService()

    for user in check.eligible:
        if claimed is not None and user.pk not in claimed:
            continue
        service.email_service.last_outcome = None
        sent = service.send_forum_reply_notification(
            user=user,
            topic_title=topic.title,
            reply_author=author_name,
            reply_excerpt=excerpt,
            topic_url=topic_url,
            post_url=post_url,
        )
        logger.info("[EMAIL] forum.%s email to user=%s: sent=%s", event, user.pk, sent)
        if claimed is None:
            continue
        row = [claimed[user.pk]]
        if sent:
            _record(delivery.mark_sent, row)
            continue
        # A False that is not a transport failure is never retried.
        outcome = service.email_service.last_outcome or EmailOutcome.TRANSIENT
        if outcome == EmailOutcome.SUPPRESSED:
            _record(delivery.mark_suppressed, row, "preference_off")
        elif outcome == EmailOutcome.PERMANENT:
            _record(delivery.mark_failed, row, "permanent")
        else:
            _record(delivery.mark_retry, row, "smtp_transient")


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
    embedded = index.embedding_transformer.embed_documents(documents, batch_size=100)
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
    from django.utils import timezone
    from wagtail_forum.api.views import _visible_boards
    from wagtail_forum.models import Topic

    from .summary import build_summary_source

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

    if not AIRateLimiter.check_global_limit():
        logger.info(
            "[PERF] topic summary skipped for %s: global AI budget exhausted",
            topic_id,
        )
        return

    prompt = constants.SUMMARY_PROMPT_TEMPLATE.format(content=content)
    try:
        summary = generate_ai_text(prompt, alias=constants.SUMMARY_ALIAS)
    except Exception as exc:
        logger.warning(
            "[ERROR] topic summary generation failed for %s: %s", topic_id, exc
        )
        raise self.retry(
            exc=exc,
            countdown=self.default_retry_delay * (2**self.request.retries),
        )

    if not summary or not summary.strip():
        # An empty completion is a transient provider glitch, never a real
        # summary — caching it would serve blank for the whole 30-day TTL. Treat
        # it like any transient failure: retry with backoff, never cache.
        logger.warning("[ERROR] topic summary empty for %s; retrying", topic_id)
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
