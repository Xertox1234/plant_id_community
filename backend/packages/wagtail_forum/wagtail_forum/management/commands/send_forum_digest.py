"""Send the forum digest to every opted-in member (todo 340).

The host schedules this (cron / Celery beat); the package never imports
Celery. Idempotent per member: `last_digest_sent_at` makes a re-run inside
the window a no-op, and a member with nothing new gets no email.

    manage.py send_forum_digest --frequency weekly [--dry-run] [--window-days N]

`--dry-run` builds every digest and prints the recipient/due/empty counts
without sending or writing anything — run it against production data before
the first real send.

Quiet hours (todo 728, owner decision 2026-11-21): a due member whose
quiet window covers the run is skipped and stays due, exactly like the other
optional forum email. Nothing is written for them, so the claim below is
untouched. The host runs the command again with `--quiet-hours-only` every
hour for the day after the main run; the first of those runs after the
member's window ends sends their digest, and `last_digest_sent_at` then
keeps every later run from sending another.
`--held-at` gives those runs the main run's time, and they then consider only
members a run held: each hold leaves a cache marker for 26 hours, and a member
whose quiet window covered the main run's time counts as held even if the
marker was lost. Without it, a member with quiet hours on whom no run held
(nothing new at the time) would be mailed by the first hourly run after
something new appeared.

Overlap safety is a cache run lock held for `DIGEST_RUN_LOCK_SECONDS`, plus a
conditional per-member claim. The claim and the send share one transaction,
so the claim is durable only once the email has been handed over (todo 548,
mirroring send_blog_newsletter after todo 534).
"""

import logging
from datetime import datetime
from uuid import uuid4

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ...conf import get_setting
from ...digest import (
    DIGEST_SUPPRESSED,
    build_digest,
    digest_recipients,
    is_due,
    mailable_accounts,
    send_digest,
    since_for,
)
from ...models import DigestFrequency, ForumProfile
from ...quiet_hours import profile_release

logger = logging.getLogger("wagtail_forum")


# A hold outlives the day of hourly follow-up runs (the last one fires 24.5
# hours after the main run) and is long gone before the next weekly run.
HELD_MARKER_SECONDS = 26 * 60 * 60


def _held_key(frequency: str, user_id: int) -> str:
    return f"wagtail_forum:digest-held:{frequency}:{user_id}"


def _mark_held(frequency: str, user_id: int) -> None:
    """Remember that a run held this member's digest for quiet hours, so a
    follow-up run sends to them whichever run it was (a late main run, a
    continuation or a recovery run can hold a member whose window opened
    after the main run's start). Never raises: without the marker the
    follow-up falls back to the window test at ``--held-at``."""
    try:
        cache.set(_held_key(frequency, user_id), True, HELD_MARKER_SECONDS)
    except Exception:
        logger.warning("[EMAIL] forum digest: could not record a quiet-hours hold")


def _was_held(frequency: str, user_id: int) -> bool:
    try:
        return bool(cache.get(_held_key(frequency, user_id)))
    except Exception:
        return False


class Command(BaseCommand):
    help = "Send the forum digest email to opted-in members."

    def add_arguments(self, parser):
        parser.add_argument(
            "--frequency",
            default=DigestFrequency.WEEKLY,
            choices=[c for c in DigestFrequency.values if c != DigestFrequency.OFF],
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build every digest and report counts; send nothing, write nothing.",
        )
        parser.add_argument(
            "--window-days",
            type=int,
            default=None,
            help="Activity window (default: WAGTAILFORUM_DIGEST_WINDOW_DAYS).",
        )

        parser.add_argument(
            "--quiet-hours-only",
            action="store_true",
            help=(
                "Consider only members with quiet hours on: the follow-up run "
                "for those an earlier run held."
            ),
        )

        parser.add_argument(
            "--held-at",
            help=(
                "With --quiet-hours-only: the earlier run's time (ISO 8601, "
                "with an offset). Only members whose quiet window covered "
                "that moment are considered, so a member that run did not "
                "hold is never mailed off the schedule."
            ),
        )

    def handle(self, *args, **options):
        frequency = options["frequency"]
        dry_run = options["dry_run"]
        quiet_only = options.get("quiet_hours_only", False)
        held_at = None
        if options.get("held_at"):
            if not quiet_only:
                raise CommandError("--held-at needs --quiet-hours-only")
            try:
                held_at = datetime.fromisoformat(options["held_at"])
            except ValueError as exc:
                raise CommandError("--held-at must be an ISO 8601 time") from exc
            if held_at.tzinfo is None:
                raise CommandError("--held-at must carry a UTC offset")
        window_days = options["window_days"] or get_setting("DIGEST_WINDOW_DAYS")
        if window_days < 2:
            raise CommandError("--window-days must be at least 2")
        now = timezone.now()

        # A run holds this cache lock while it iterates; an overlapping fire
        # (beat re-firing after a worker restart, two containers during a
        # deploy) sees it and exits. Released in `finally`, so a continuation
        # after a soft time limit can take over. Its TTL
        # (DIGEST_RUN_LOCK_SECONDS) is the host task's hard time limit plus a
        # margin, so a hard-killed holder blocks the next run for minutes,
        # not hours (todo 548). The value is this run's own token, so the
        # release below can tell its lock from a later fire's (todo 605).
        lock_key = f"wagtail_forum:digest-run:{frequency}"
        lock_token = f"{now.isoformat()}:{uuid4().hex}"
        holds_lock = False
        if not dry_run:
            locked = cache.add(
                lock_key, lock_token, get_setting("DIGEST_RUN_LOCK_SECONDS")
            )
            if locked is False:
                self.stdout.write(
                    f"[EMAIL] digest frequency={frequency}: another run holds the lock — exiting"
                )
                return
            holds_lock = locked is True
            if locked is None:
                # A cache with IGNORE_EXCEPTIONS (django-redis) swallows an
                # outage and answers None, where a held lock answers False.
                # Exiting would skip every member for a week, and the lock is
                # only a shortcut: each member's conditional claim is what
                # stops a second send, so an overlapping run cannot mail
                # anyone twice (todo 548).
                logger.warning(
                    "[EMAIL] digest frequency=%s: the run lock is unavailable "
                    "(cache down?), sending without it",
                    frequency,
                )
        try:
            totals = self._run(
                frequency, dry_run, window_days, now, quiet_only, held_at
            )
        finally:
            # Release only a lock this run took. After an outage (add
            # answered None) the cache may recover mid-run and another fire
            # may take the lock; deleting it here would let a third fire
            # start (todo 585). The same goes for a run that outlived
            # DIGEST_RUN_LOCK_SECONDS (a manual run with no hard time limit):
            # its key expired and another fire may hold it now, so delete
            # only while the key still holds this run's token (todo 605).
            #
            # A get that answers None falls back to a plain delete (todo 630,
            # owner decision 2026-10-12). Under IGNORE_EXCEPTIONS a Redis blip
            # makes the get answer None, and keeping the lock would block the
            # soft-time-limit continuation for the full TTL. If the key really
            # is gone, the delete is a no-op.
            #
            # Read-then-delete is not atomic, but the gap is one round-trip
            # against a TTL of minutes, and the per-member claim still stops
            # a double send. An atomic compare-and-delete needs a
            # backend-specific script, which this package cannot assume.
            if holds_lock:
                current = cache.get(lock_key)
                if current is None or current == lock_token:
                    cache.delete(lock_key)

        label = "would send" if dry_run else "sent"
        self.stdout.write(
            f"[EMAIL] digest frequency={frequency} window_days={window_days} "
            f"recipients={totals['recipients']} due={totals['due']} "
            f"empty={totals['empty']} {label}={totals['sent']} failed={totals['failed']} "
            f"suppressed={totals['suppressed']} held={totals['held']}"
            + (" (dry run — nothing sent, nothing written)" if dry_run else "")
        )

    def _run(
        self, frequency, dry_run, window_days, now, quiet_only=False, held_at=None
    ):
        totals = {
            "recipients": 0,
            "due": 0,
            "empty": 0,
            "sent": 0,
            "failed": 0,
            "suppressed": 0,
            "held": 0,
        }
        recipients = digest_recipients(frequency)
        if quiet_only:
            recipients = recipients.filter(quiet_hours_enabled=True)
        for profile in recipients.iterator(chunk_size=200):
            if held_at is not None and not (
                _was_held(frequency, profile.user_id)
                or profile_release(profile, held_at) is not None
            ):
                # The follow-up run is for members an earlier run held: each
                # hold leaves a cache marker (below). A member no run held
                # was read then (sent, or nothing new) and waits for the next
                # scheduled run, like every member without quiet hours. The
                # window test at ``held_at`` is the fallback for a marker
                # the cache lost.
                continue
            totals["recipients"] += 1
            if not is_due(profile, now, window_days):
                continue
            totals["due"] += 1
            # Quiet hours (todo 728): checked on the row already loaded and
            # against the clock as it is now, not the run's start (a run can
            # last minutes). Held, not failed: the member stays due, nothing
            # is written, and a later run sends once their window has ended.
            release = profile_release(profile, timezone.now())
            if release is not None:
                totals["held"] += 1
                if not dry_run:
                    _mark_held(frequency, profile.user_id)
                logger.debug(
                    "[EMAIL] forum digest held for quiet hours: user=%s until %s",
                    profile.user_id,
                    release.isoformat(),
                )
                continue
            try:
                digest = build_digest(
                    profile.user, since_for(profile, now, window_days), profile
                )
            except Exception as exc:
                if type(exc).__name__ == "SoftTimeLimitExceeded":
                    raise  # the run is being stopped, not this member
                # One member's bad data must not end the run for everyone
                # after them; the marker stays unset so they are due next time.
                logger.exception(
                    "[EMAIL] forum digest build failed for user=%s", profile.user_id
                )
                totals["failed"] += 1
                continue
            if digest.empty:
                totals["empty"] += 1
                continue
            if dry_run:
                self.stdout.write(
                    f"[EMAIL] dry-run: user={profile.user_id} watched={len(digest.watched)} "
                    f"trending={len(digest.trending)}"
                )
                totals["sent"] += 1
                continue
            sent = self._send_one(profile, digest, now, frequency)
            if sent is None:
                continue  # another run claimed them, or they opted out
            if sent == DIGEST_SUPPRESSED:
                # Not a failure: nothing to recover, the address is on the
                # host's suppression list (todo 625).
                totals["suppressed"] += 1
            elif sent:
                totals["sent"] += 1
            else:
                totals["failed"] += 1
        return totals

    def _send_one(self, profile, digest, now, frequency) -> bool | str | None:
        """True sent, False failed, DIGEST_SUPPRESSED dropped by the host's
        suppression backstop, None not ours to send any more."""
        # Claim the member before sending, on the marker we read: belt to the
        # run lock's braces. A second run racing on the row cannot also
        # match: its UPDATE waits on our row lock, then finds the marker
        # changed.
        #
        # The claim commits only after the send returns (todo 548). Anything
        # that stops the send gives the member back with the rollback: a
        # failed send, a soft time limit or a re-raised Warning (todo 537), a
        # database error, and a hard kill too (the task's hard time limit, a
        # deploy), since the server rolls back the dead connection's
        # transaction. No separate release can fail and leave the member
        # stamped with nothing sent.
        #
        # At-least-once on purpose, as in send_blog_newsletter (todo 541,
        # owner decision 2026-10-10): a soft limit, a kill or a failed commit
        # landing after SMTP accepted the mail rolls the claim back too, and
        # the member gets that digest again on the next run. That window is
        # milliseconds against an SMTP round-trip; skipping a member whose
        # digest never went out is worse than a rare repeat.
        #
        # The other cost, accepted as in send_blog_newsletter (todo 569): the
        # claim's row lock, its open transaction and a database connection
        # are held for the whole SMTP round-trip, up to EMAIL_TIMEOUT per
        # connect or operation. For that long, anything else that locks this
        # one ForumProfile row waits on it (a presence `last_seen` write, a
        # profile PATCH, a trust update). Other rows are not blocked, and the
        # wait ends when the send returns (todo 585).
        #
        # The claim rechecks every digest_recipients condition (todos 585,
        # 605, and the host's DIGEST_RECIPIENT_FILTER since 620): the
        # recipient query was read up to a 200-row chunk ago, and a member
        # who has since opted out, been deactivated or cleared their
        # email must not be mailed. The address is re-read after the claim,
        # so a member who changed it in that window (say, off a compromised
        # account) is mailed at the new one, never the one read with the
        # chunk.
        #
        # The UPDATE must stay on one table. A join (`user__is_active`) makes
        # Django rewrite it as `id IN (SELECT ... JOIN user ...)`, and then
        # PostgreSQL's recheck after waiting on a racing claim tests only that
        # stale subquery, not the marker: both runs claim and the member gets
        # two emails. `user_id__in` is a join-free subquery, so the marker
        # stays in the outer WHERE on the locked row.
        previous = profile.last_digest_sent_at
        active_account = mailable_accounts().filter(pk=profile.user_id)
        with transaction.atomic():
            claimed = ForumProfile.objects.filter(
                pk=profile.pk,
                last_digest_sent_at=previous,
                digest_frequency=frequency,
                user_id__in=active_account.values("pk"),
            ).update(last_digest_sent_at=now)
            if not claimed:
                return None
            email = active_account.values_list("email", flat=True).first()
            if not email:
                # Cleared or deactivated between the claim and this read.
                transaction.set_rollback(True)
                return None
            digest.user.email = email
            # A strict bool (todo 585): a falsy non-bool from a send is a
            # failure, never a silent "neither sent nor failed".
            result = send_digest(digest)
            sent = DIGEST_SUPPRESSED if result == DIGEST_SUPPRESSED else bool(result)
            if sent is not True:
                # Suppressed as well as failed: no stamp, so the member is
                # not recorded as sent a digest that never went out.
                # Nothing went out: undo the claim so the member stays due.
                transaction.set_rollback(True)
        return sent
