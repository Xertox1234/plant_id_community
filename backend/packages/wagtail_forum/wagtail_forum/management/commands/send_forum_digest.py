"""Send the forum digest to every opted-in member (todo 340).

The host schedules this (cron / Celery beat); the package never imports
Celery. Idempotent per member: `last_digest_sent_at` makes a re-run inside
the window a no-op, and a member with nothing new gets no email.

    manage.py send_forum_digest --frequency weekly [--dry-run] [--window-days N]

`--dry-run` builds every digest and prints the recipient/due/empty counts
without sending or writing anything — run it against production data before
the first real send.
"""

import logging

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...conf import get_setting
from ...digest import build_digest, digest_recipients, is_due, send_digest, since_for
from ...models import DigestFrequency, ForumProfile

logger = logging.getLogger("wagtail_forum")

# A run holds this cache lock while it iterates; an overlapping fire (beat
# re-firing after a worker restart, two containers during a deploy) sees it
# and exits. Released in `finally`, so a continuation after a killed run can
# take over; sized so a crashed holder cannot block the next real run.
RUN_LOCK_SECONDS = 2 * 60 * 60


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

        lock_key = f"wagtail_forum:digest-run:{frequency}"
        if not dry_run and not cache.add(lock_key, now.isoformat(), RUN_LOCK_SECONDS):
            self.stdout.write(
                f"[EMAIL] digest frequency={frequency}: another run holds the lock — exiting"
            )
            return
        try:
            totals = self._run(frequency, dry_run, window_days, now)
        finally:
            if not dry_run:
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
            # Claim the member atomically BEFORE sending (conditional UPDATE on
            # the marker we read): belt to the run lock's braces — two runs
            # racing on the same row can only both succeed if the marker is
            # unchanged, and only one UPDATE matches. Reverted on a failed send
            # so the member is due again next time.
            previous = profile.last_digest_sent_at
            claimed = ForumProfile.objects.filter(
                pk=profile.pk, last_digest_sent_at=previous
            ).update(last_digest_sent_at=now)
            if not claimed:
                continue
            if send_digest(digest):
                totals["sent"] += 1
            else:
                ForumProfile.objects.filter(pk=profile.pk).update(
                    last_digest_sent_at=previous
                )
                totals["failed"] += 1
        return totals
