"""Send the forum digest to every opted-in member (todo 340).

The host schedules this (cron / Celery beat); the package never imports
Celery. Idempotent per member: `last_digest_sent_at` makes a re-run inside
the window a no-op, and a member with nothing new gets no email.

    manage.py send_forum_digest --frequency weekly [--dry-run] [--window-days N]

`--dry-run` builds every digest and prints the recipient/due/empty counts
without sending or writing anything — run it against production data before
the first real send.

Overlap safety is a cache run lock held for `DIGEST_RUN_LOCK_SECONDS`, plus a
conditional per-member claim. The claim and the send share one transaction,
so the claim is durable only once the email has been handed over (todo 548,
mirroring send_blog_newsletter after todo 534).
"""

import logging
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ...conf import get_setting
from ...digest import build_digest, digest_recipients, is_due, send_digest, since_for
from ...models import DigestFrequency, ForumProfile

logger = logging.getLogger("wagtail_forum")


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

    def handle(self, *args, **options):
        frequency = options["frequency"]
        dry_run = options["dry_run"]
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
            totals = self._run(frequency, dry_run, window_days, now)
        finally:
            # Release only a lock this run took. After an outage (add
            # answered None) the cache may recover mid-run and another fire
            # may take the lock; deleting it here would let a third fire
            # start (todo 585). The same goes for a run that outlived
            # DIGEST_RUN_LOCK_SECONDS (a manual run with no hard time limit):
            # its key expired and another fire may hold it now, so delete
            # only while the key still holds this run's token (todo 605).
            # Read-then-delete is not atomic, but the gap is one round-trip
            # against a TTL of minutes, and the per-member claim still stops
            # a double send.
            if holds_lock and cache.get(lock_key) == lock_token:
                cache.delete(lock_key)

        label = "would send" if dry_run else "sent"
        self.stdout.write(
            f"[EMAIL] digest frequency={frequency} window_days={window_days} "
            f"recipients={totals['recipients']} due={totals['due']} "
            f"empty={totals['empty']} {label}={totals['sent']} failed={totals['failed']}"
            + (" (dry run — nothing sent, nothing written)" if dry_run else "")
        )

    def _run(self, frequency, dry_run, window_days, now):
        totals = {"recipients": 0, "due": 0, "empty": 0, "sent": 0, "failed": 0}
        for profile in digest_recipients(frequency).iterator(chunk_size=200):
            totals["recipients"] += 1
            if not is_due(profile, now, window_days):
                continue
            totals["due"] += 1
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
            if sent:
                totals["sent"] += 1
            else:
                totals["failed"] += 1
        return totals

    def _send_one(self, profile, digest, now, frequency) -> bool | None:
        """True sent, False failed, None not ours to send any more."""
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
        # 605): the recipient query was read up to a 200-row chunk ago, and a
        # member who has since opted out, been deactivated or cleared their
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
        active_account = (
            get_user_model()
            .objects.filter(pk=profile.user_id, is_active=True)
            .exclude(email="")
        )
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
            sent = bool(send_digest(digest))
            if not sent:
                # Nothing went out: undo the claim so the member stays due.
                transaction.set_rollback(True)
        return sent
