"""Management command: per-forum auto-pruning (todo 679; phpBB's prune).

For every forum with ``prune_enabled`` and a ``prune_days_since_last_post``,
unpublish its live topics whose last post (or, with no post, creation) is
older than that many days. Pinned topics and topics with a poll are spared
unless the forum's ``prune_pinned`` / ``prune_polls`` say otherwise.

Prune is a soft take-down, the moderator's own unpublish
(``UnpublishAction``), so counters, trust and live updates follow the same
``unpublished`` signal and a moderator can restore a topic from the admin.
Days since last post only: there is no days-since-viewed rule (owner
decision 2026-10-30). Runs nightly from the ``forum-prune-cron`` service.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.db.models.functions import Coalesce
from django.utils import timezone
from wagtail.actions.unpublish import UnpublishAction
from wagtail_forum.models import Forum, Poll, Topic

logger = logging.getLogger("wagtail_forum")


def prunable_topics(forum: Forum, now=None) -> QuerySet[Topic]:
    """The live topics of ``forum`` its prune settings would unpublish now."""
    if not forum.prune_enabled or not forum.prune_days_since_last_post:
        return Topic.objects.none()
    cutoff = (now or timezone.now()) - timedelta(days=forum.prune_days_since_last_post)
    qs = Topic.objects.filter(board=forum, live=True).annotate(
        last_activity=Coalesce("last_post_at", "created_at")
    )
    qs = qs.filter(last_activity__lt=cutoff)
    if not forum.prune_pinned:
        qs = qs.filter(is_pinned=False)
    if not forum.prune_polls:
        qs = qs.exclude(Exists(Poll.objects.filter(topic=OuterRef("pk"))))
    return qs.order_by("pk")


class Command(BaseCommand):
    help = "Unpublish topics past each forum's prune threshold (days since last post)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be pruned and change nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = bool(options["dry_run"])
        now = timezone.now()
        total = 0
        failed = 0
        forums = Forum.objects.filter(
            forum_type=Forum.FORUM,
            prune_enabled=True,
            prune_days_since_last_post__isnull=False,
        ).order_by("pk")
        for forum in forums:
            topics = list(prunable_topics(forum, now))
            pruned = len(topics)
            if not dry_run:
                for topic in topics:
                    # One topic that fails to unpublish is logged and skipped:
                    # the cron chains the nightly jobs with &&, so a crash here
                    # would also skip the token flush and the account expiry.
                    try:
                        with transaction.atomic():
                            UnpublishAction(topic).execute(skip_permission_checks=True)
                    except Exception:
                        logger.exception(
                            "[ERROR] prune failed for topic %s in forum %s",
                            topic.pk,
                            forum.slug,
                        )
                        failed += 1
                        pruned -= 1
            total += pruned
            line = (
                f"[PRUNE] forum {forum.slug}: {pruned} topic(s) "
                f"{'would be ' if dry_run else ''}unpublished "
                f"(no post for {forum.prune_days_since_last_post} day(s))"
            )
            logger.info(line)
            self.stdout.write(line)
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would prune' if dry_run else 'Pruned'} {total} topic(s)."
                + (f" {failed} failed (see the log)." if failed else "")
            )
        )
