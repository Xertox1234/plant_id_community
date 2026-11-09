"""The nightly privacy prune (Plan B task 8).

``run_privacy_prune`` is what the beat task (``privacy_retention_prune``) and
``manage.py privacy_prune`` both call. Its parts:

- ``prune_retention``: email records, blog page views and audit-log rows
  older than ``PRIVACY_RETENTION_DAYS``. ``apps.core.tasks`` already prunes
  email clicks and provider events (``prune_email_feedback``), so they are
  not touched here.
- ``release_held_posts``: forum posts an account deletion held for a report
  are erased once the report has left the moderation queue or the hold ran
  out.
- ``requeue_stale_deletions``: a deletion still pending after
  ``ACCOUNT_DELETE_STALE_HOURS`` is queued again (ruling R12).
- ``prune_orphan_firebase_users``: Firebase logins with no account behind
  them. Log-only unless ``settings.ORPHAN_FIREBASE_PRUNE_ENABLED``.
- ``prune_expired_sessions``: expired ``django.contrib.sessions`` rows, like
  ``manage.py clearsessions``.
- ``thin_deleted_accounts``: a finished ``self``/``staff`` deletion older
  than ``PRIVACY_RETENTION_DAYS`` loses its ``email_hash`` and ``user_id``.
  ``abuse``/``under_13`` rows keep their hash (the sign-up block needs it).
- ``prune_unreachable_conversations``: DM threads every member of which has
  been deleted (the deletion's own ``django`` step removes the ones it
  creates; this catches older ones and those a queued report held).

Every part takes ``dry_run``: it then counts what it would do and changes and
queues nothing. Every part is idempotent, so an overlapping or retried run
does no harm.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import sentry_sdk
from apps.core.firebase_config import initialize_firebase
from auditlog import get_logentry_model
from auditlog.context import disable_auditlog
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.functions import Lower
from django.utils import timezone

from .constants import (
    ACCOUNT_DELETE_STALE_HOURS,
    DELETED_ACCOUNT_STATUS_DONE,
    DELETED_ACCOUNT_STATUS_PENDING,
    ORPHAN_FIREBASE_DELETE_CAP,
    ORPHAN_FIREBASE_USER_DAYS,
    PRIVACY_PRUNE_BATCH,
    PRIVACY_RETENTION_DAYS,
    THINNED_DELETION_REASONS,
)
from .deletion import (
    delete_unreachable_conversations,
    erase_post,
    moderation_queue_statuses,
    unreachable_conversations,
)
from .models import DeletedAccount

logger = logging.getLogger(__name__)

# Uids and addresses looked up per query when matching Firebase logins.
_LOOKUP_CHUNK = 500


def run_privacy_prune(dry_run: bool = False) -> dict[str, Any]:
    """Run every part once; return their counts.

    Cheapest and most compliance-relevant first: the deletion re-queue, the
    held-post release, the orphan prune, then retention (the slowest, which
    can run into the time limit on a large backlog). Each part is isolated:
    a part that raises is logged and sent to Sentry, its count is ``-1``,
    and the next part still runs. Once every part has run, the first
    failure is re-raised, so the task (and the command) shows as failed and
    a database ``OperationalError`` still triggers the task's autoretry,
    which is safe because every part is idempotent. A soft time limit is
    re-raised at once: the hard kill follows within a minute.
    """
    now = timezone.now()
    parts: tuple[tuple[str, Callable[[], Any]], ...] = (
        ("stale_deletions", lambda: requeue_stale_deletions(now, dry_run=dry_run)),
        ("held_posts", lambda: release_held_posts(now, dry_run=dry_run)),
        (
            "orphan_firebase_logins",
            lambda: prune_orphan_firebase_users(now, dry_run=dry_run),
        ),
        ("retention", lambda: prune_retention(now, dry_run=dry_run)),
        ("sessions", lambda: prune_expired_sessions(now, dry_run=dry_run)),
        ("conversations", lambda: prune_unreachable_conversations(dry_run=dry_run)),
        ("deleted_accounts", lambda: thin_deleted_accounts(now, dry_run=dry_run)),
    )
    counts: dict[str, Any] = {}
    failures: list[Exception] = []
    for name, part in parts:
        try:
            counts[name] = part()
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            logger.error("[PRIVACY PRUNE] %s failed: %s", name, type(exc).__name__)
            sentry_sdk.capture_exception(exc)
            counts[name] = -1
            failures.append(exc)
    if failures:
        raise failures[0]
    return counts


# --- expired sessions ---------------------------------------------------------


def prune_expired_sessions(now: datetime | None = None, dry_run: bool = False) -> int:
    """Delete expired session rows via the configured ``SESSION_ENGINE``'s
    ``clear_expired`` (what ``manage.py clearsessions`` calls; a no-op for an
    engine that is not database-backed). Returns the number of expired rows
    counted just before the delete; in a dry run, the number it would delete.
    """
    from django.contrib.sessions.models import Session
    from django.utils.module_loading import import_string

    expired = Session.objects.filter(expire_date__lt=now or timezone.now())
    count = expired.count()
    if not dry_run:
        import_string(f"{settings.SESSION_ENGINE}.SessionStore").clear_expired()
    return count


# --- old deletion records -----------------------------------------------------


def thin_deleted_accounts(now: datetime | None = None, dry_run: bool = False) -> int:
    """Blank ``email_hash`` and NULL ``user_id`` on every finished ``self`` or
    ``staff`` deletion whose ``deleted_at`` is older than
    ``PRIVACY_RETENTION_DAYS``; the row stays with its ``reason``,
    ``deleted_at`` and ``policy_version``. Pending rows and ``abuse`` /
    ``under_13`` rows are never touched: their hash is what blocks the
    address from signing up again. Returns how many rows were thinned; in a
    dry run, how many would be. Idempotent: a thinned row no longer matches.
    """
    cutoff = (now or timezone.now()) - timedelta(days=PRIVACY_RETENTION_DAYS)
    due = DeletedAccount.objects.filter(
        status=DELETED_ACCOUNT_STATUS_DONE,
        reason__in=THINNED_DELETION_REASONS,
        deleted_at__lt=cutoff,
    ).filter(~Q(email_hash="") | Q(user_id__isnull=False))
    if dry_run:
        return int(due.count())
    thinned = int(due.update(email_hash="", user_id=None))
    if thinned:
        logger.info("[PRIVACY PRUNE] thinned %s old deletion records", thinned)
    return thinned


# --- unreachable conversations ----------------------------------------------


def prune_unreachable_conversations(dry_run: bool = False) -> int:
    """Delete conversations nobody can open any more, with their messages
    (``deletion.unreachable_conversations``). Returns how many were deleted;
    in a dry run, how many would be."""
    if dry_run:
        return int(unreachable_conversations().count())
    with disable_auditlog():
        deleted = delete_unreachable_conversations()
    if deleted:
        logger.info("[PRIVACY PRUNE] deleted %s unreachable conversations", deleted)
    return deleted


# --- retention ---------------------------------------------------------------


def prune_retention(
    now: datetime | None = None, dry_run: bool = False
) -> dict[str, int]:
    """Delete rows older than ``PRIVACY_RETENTION_DAYS``, in batches.

    Deleting an ``EmailNotification`` cascades to its ``EmailClick`` rows.
    Audit logging is off while deleting, so the prune writes no new rows.
    """
    from apps.blog.models import BlogPostView
    from apps.core.models import EmailNotification

    cutoff = (now or timezone.now()) - timedelta(days=PRIVACY_RETENTION_DAYS)
    expired: dict[str, QuerySet[Any]] = {
        "email_notifications": EmailNotification.objects.filter(created_at__lt=cutoff),
        "blog_post_views": BlogPostView.objects.filter(viewed_at__lt=cutoff),
        "audit_log_entries": get_logentry_model().objects.filter(timestamp__lt=cutoff),
    }
    if dry_run:
        return {name: rows.count() for name, rows in expired.items()}
    with disable_auditlog():
        return {name: _delete_in_batches(rows) for name, rows in expired.items()}


def _delete_in_batches(queryset: QuerySet[Any]) -> int:
    """Copied from ``apps.core.email_feedback``; counts the model's own rows
    only, not the rows its deletes cascade to."""
    model = queryset.model
    queryset = queryset.order_by()
    deleted = 0
    while True:
        pks = list(queryset.values_list("pk", flat=True)[:PRIVACY_PRUNE_BATCH])
        if not pks:
            return deleted
        _, per_model = model.objects.filter(pk__in=pks).delete()
        deleted += per_model.get(model._meta.label, 0)


# --- held forum posts -------------------------------------------------------


def release_held_posts(now: datetime | None = None, dry_run: bool = False) -> int:
    """Erase each held post whose hold is over: its ``erase_after`` has
    passed, or no report on it is still in the moderation queue. A post
    whose erase fails is logged and sent to Sentry and keeps its hold (the
    erase is atomic), and the others are still erased."""
    from wagtail_forum.models import Post, Report

    now = now or timezone.now()
    queued = Report.objects.filter(
        post=OuterRef("pk"), status__in=moderation_queue_statuses()
    )
    due = (
        Post.objects.filter(erase_after__isnull=False)
        .filter(Q(erase_after__lte=now) | ~Exists(queued))
        .order_by("pk")
    )
    if dry_run:
        return int(due.count())
    released = 0
    with disable_auditlog():
        for post in due:
            try:
                erase_post(post)
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:
                logger.error(
                    "[PRIVACY PRUNE] held post %s erase failed: %s",
                    post.pk,
                    type(exc).__name__,
                )
                sentry_sdk.capture_exception(exc)
                continue
            released += 1
    if released:
        logger.info("[PRIVACY PRUNE] released %s held forum posts", released)
    return released


# --- stalled deletions (ruling R12) ------------------------------------------


def requeue_stale_deletions(now: datetime | None = None, dry_run: bool = False) -> int:
    """Queue ``delete_account_task`` again for each deletion still pending
    ``ACCOUNT_DELETE_STALE_HOURS`` after it was requested. Safe while a job
    is still running: the job locks the record and skips recorded steps.
    A row whose enqueue fails (a broker error) is logged and sent to Sentry,
    and the rest are still queued; it is tried again the next night."""
    from .tasks import delete_account_task

    cutoff = (now or timezone.now()) - timedelta(hours=ACCOUNT_DELETE_STALE_HOURS)
    pks = list(
        DeletedAccount.objects.filter(
            status=DELETED_ACCOUNT_STATUS_PENDING, requested_at__lt=cutoff
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if dry_run:
        return len(pks)
    queued = []
    for pk in pks:
        try:
            delete_account_task.delay(pk)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            logger.error(
                "[ACCOUNT DELETE] re-queue of deletion %s failed: %s",
                pk,
                type(exc).__name__,
            )
            sentry_sdk.capture_exception(exc)
            continue
        queued.append(pk)
    if queued:
        logger.warning(
            "[ACCOUNT DELETE] re-queued %s stalled deletions: %s", len(queued), queued
        )
    return len(queued)


# --- orphaned Firebase logins -----------------------------------------------


def prune_orphan_firebase_users(
    now: datetime | None = None, dry_run: bool = False
) -> int:
    """Delete Firebase logins older than ``ORPHAN_FIREBASE_USER_DAYS`` that
    no account owns.

    A login is an orphan only when its uid is no ``User.firebase_uid`` and no
    pending ``DeletedAccount.firebase_uid`` (that job deletes it itself) AND
    its email, case-insensitively, is no ``User.email``: an account whose uid
    was never stored must not lose its login. A login with no email or no
    creation time is kept.

    More than ``ORPHAN_FIREBASE_DELETE_CAP`` orphans aborts the run (a
    ``[SECURITY]`` log and a Sentry message, nothing deleted). Unless
    ``settings.ORPHAN_FIREBASE_PRUNE_ENABLED`` is on, it runs as ``dry_run``:
    it logs the count and the uids and deletes nothing. Returns the number
    deleted, or in a dry run the number it would delete. Emails are never
    logged.
    """
    from firebase_admin import auth as firebase_auth
    from firebase_admin import exceptions as firebase_exceptions

    if not initialize_firebase():
        logger.info("[PRIVACY PRUNE] Firebase not configured; orphan check skipped")
        return 0
    now = now or timezone.now()
    cutoff_ms = int(
        (now - timedelta(days=ORPHAN_FIREBASE_USER_DAYS)).timestamp() * 1000
    )
    try:
        candidates = [
            (record.uid, record.email)
            for record in firebase_auth.list_users().iterate_all()
            if record.email
            and record.user_metadata is not None
            and record.user_metadata.creation_timestamp is not None
            and record.user_metadata.creation_timestamp < cutoff_ms
        ]
    except firebase_exceptions.FirebaseError as exc:
        logger.warning(
            "[PRIVACY PRUNE] listing Firebase users failed (%s); orphan check skipped",
            type(exc).__name__,
        )
        return 0
    orphans = _unowned(candidates)

    if len(orphans) > ORPHAN_FIREBASE_DELETE_CAP:
        logger.error(
            "[SECURITY] %s orphaned Firebase logins exceeds the cap of %s; "
            "nothing deleted",
            len(orphans),
            ORPHAN_FIREBASE_DELETE_CAP,
        )
        sentry_sdk.capture_message(
            f"Orphaned Firebase login prune aborted: {len(orphans)} over the "
            f"cap of {ORPHAN_FIREBASE_DELETE_CAP}",
            level="error",
        )
        return 0

    if dry_run or not settings.ORPHAN_FIREBASE_PRUNE_ENABLED:
        if orphans:
            logger.info(
                "[PRIVACY PRUNE] %s orphaned Firebase logins (not deleted): %s",
                len(orphans),
                orphans,
            )
        return len(orphans)

    deleted = 0
    for uid in orphans:
        try:
            firebase_auth.delete_user(uid)
        except firebase_auth.UserNotFoundError:
            pass  # already gone: done
        except firebase_exceptions.FirebaseError as exc:
            logger.warning(
                "[PRIVACY PRUNE] could not delete Firebase login %s (%s)",
                uid,
                type(exc).__name__,
            )
            continue
        deleted += 1
        logger.info("[PRIVACY PRUNE] deleted orphaned Firebase login %s", uid)
    return deleted


def _unowned(candidates: list[tuple[str, str]]) -> list[str]:
    """The uids of ``candidates`` (uid, email) that no account owns."""
    user_model = get_user_model()
    owned_uids: set[str | None] = set()
    owned_emails: set[str] = set()
    for start in range(0, len(candidates), _LOOKUP_CHUNK):
        chunk = candidates[start : start + _LOOKUP_CHUNK]
        uids = [uid for uid, _ in chunk]
        emails = [email.lower() for _, email in chunk]
        owned_uids.update(
            user_model._base_manager.filter(firebase_uid__in=uids).values_list(
                "firebase_uid", flat=True
            )
        )
        owned_uids.update(
            DeletedAccount.objects.filter(
                status=DELETED_ACCOUNT_STATUS_PENDING, firebase_uid__in=uids
            ).values_list("firebase_uid", flat=True)
        )
        owned_emails.update(
            user_model._base_manager.annotate(email_lower=Lower("email"))
            .filter(email_lower__in=emails)
            .values_list("email_lower", flat=True)
        )
    return [
        uid
        for uid, email in candidates
        if uid not in owned_uids and email.lower() not in owned_emails
    ]
