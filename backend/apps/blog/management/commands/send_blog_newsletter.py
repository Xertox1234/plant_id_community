"""Send the weekly blog newsletter to confirmed subscribers (todo 409).

    manage.py send_blog_newsletter [--dry-run]

The beat entry `blog-weekly-newsletter` runs this through
`apps.blog.tasks.send_blog_weekly_newsletter`. Safe to run twice: a run lock
makes an overlapping run exit, and each subscriber is claimed through
`last_sent_at` before their email goes out, so nobody is due again that week.
The claim and the send share one transaction, so the claim is durable only
once the email has been handed over (todo 534).

The run also deletes signups that never confirmed once their link has
expired (`newsletter_digest.stale_unconfirmed`).

`--dry-run` builds every email and prints the counts, including how many
rows the prune would delete. It sends nothing and writes nothing.
"""

import logging

from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import OperationalError, transaction
from django.utils import timezone

from ... import newsletter_digest
from ...constants import NEWSLETTER_RUN_LOCK_SECONDS
from ...models import BlogNewsletter

logger = logging.getLogger(__name__)

LOCK_KEY = "blog:newsletter-run"


class Command(BaseCommand):
    help = "Send the weekly blog newsletter to confirmed subscribers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build every email and report counts; send nothing, write nothing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        if not dry_run:
            locked = cache.add(LOCK_KEY, now.isoformat(), NEWSLETTER_RUN_LOCK_SECONDS)
            if locked is False:
                self.stdout.write(
                    "[EMAIL] newsletter: another run holds the lock, exiting"
                )
                return
            if locked is None:
                # The cache swallows a Redis outage (IGNORE_EXCEPTIONS) and
                # answers None, where a held lock answers False. Waiting a
                # week for Redis would skip every reader, and the lock is
                # only a shortcut: each row's claim is what stops a second
                # send, so an overlapping run cannot mail anyone twice.
                logger.warning(
                    "[EMAIL] newsletter: the run lock is unavailable "
                    "(cache down?), sending without it"
                )
        try:
            totals = self._send(now, dry_run)
            if dry_run:
                totals["pruned"] = newsletter_digest.stale_unconfirmed(now).count()
            else:
                totals["pruned"] = newsletter_digest.prune_stale_unconfirmed(now)
        finally:
            if not dry_run:
                cache.delete(LOCK_KEY)

        label = "would send" if dry_run else "sent"
        self.stdout.write(
            f"[EMAIL] newsletter recipients={totals['recipients']} due={totals['due']} "
            f"empty={totals['empty']} {label}={totals['sent']} failed={totals['failed']} "
            f"{'would prune' if dry_run else 'pruned'}={totals['pruned']}"
            + (" (dry run: nothing sent, nothing written)" if dry_run else "")
        )

    def _send(self, now, dry_run):
        totals = {"recipients": 0, "due": 0, "empty": 0, "sent": 0, "failed": 0}
        for subscriber in newsletter_digest.recipients().iterator(chunk_size=200):
            totals["recipients"] += 1
            if not newsletter_digest.is_due(subscriber, now):
                continue
            totals["due"] += 1
            try:
                posts = newsletter_digest.new_posts(
                    newsletter_digest.since_for(subscriber), now
                )
            except (SoftTimeLimitExceeded, OperationalError):
                # The run stops: the soft limit hands over to the continuation,
                # and a database outage to the task's retry. Nothing has been
                # claimed yet, so neither repeats an email.
                raise
            except Exception:
                # One bad row must not end the run for everyone after it; it
                # stays unclaimed, so it is due again next time.
                logger.exception(
                    "[EMAIL] newsletter build failed for subscriber=%s", subscriber.pk
                )
                totals["failed"] += 1
                continue
            if not posts:
                # Nothing new: leave last_sent_at alone so next week's email
                # still starts from the same point.
                totals["empty"] += 1
                continue
            if dry_run:
                self.stdout.write(
                    f"[EMAIL] dry-run: subscriber={subscriber.pk} posts={len(posts)}"
                )
                totals["sent"] += 1
                continue
            sent = self._send_one(subscriber, posts, now)
            if sent:
                totals["sent"] += 1
            elif sent is False:
                totals["failed"] += 1
        return totals

    def _send_one(self, subscriber, posts, now) -> bool | None:
        """True sent, False failed, None not ours to send any more."""
        # Claim the row before sending, on the marker we read. A second run
        # racing on it cannot also match: its UPDATE waits on our row lock,
        # then finds the marker changed. The row must still be subscribed: it
        # may have unsubscribed since its chunk was read.
        #
        # The claim commits only after the send returns. Anything that stops
        # the send gives the row back with the rollback: a failed send, the
        # soft time limit, a database error, and a hard kill too, since the
        # server rolls back the dead connection's transaction. No separate
        # release can fail and leave the row stamped with nothing sent.
        #
        # The price is a small window after `message.send()` has handed the
        # mail over and before the commit: the soft time limit, a kill or a
        # failed commit landing there gives the row back too, and the reader
        # is mailed those posts again (by the continuation, the retry, or
        # next week's run). That window is milliseconds against an SMTP
        # round-trip; a lost week is worse than a rare repeat. The forum
        # digest has the same property.
        previous = subscriber.last_sent_at
        with transaction.atomic():
            claimed = BlogNewsletter.objects.filter(
                pk=subscriber.pk,
                last_sent_at=previous,
                is_active=True,
                confirmed_at__isnull=False,
            ).update(last_sent_at=now)
            if not claimed:
                return None
            sent = newsletter_digest.send(subscriber, posts)
            if not sent:
                # Nothing went out: undo the claim so the row stays due.
                transaction.set_rollback(True)
        return sent
