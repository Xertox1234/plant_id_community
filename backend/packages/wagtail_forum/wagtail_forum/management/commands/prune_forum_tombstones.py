"""Management command: prune old TopicDeletedLog tombstone rows.

Run periodically (e.g. daily via Celery beat or cron) to prevent the
tombstone table growing unboundedly. Rows older than
WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS (default 30) are removed;
any client that has not synced within that window must perform a full
resync to recover missed deletions.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete TopicDeletedLog tombstone rows older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Override the retention window in days "
                "(default: WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS setting)."
            ),
        )

    def handle(self, *args, **options):
        from wagtail_forum.conf import get_setting
        from wagtail_forum.models.tombstones import TopicDeletedLog

        days = options["days"]
        if days is None:
            days = get_setting("SYNC_TOMBSTONE_RETENTION_DAYS")

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = TopicDeletedLog.objects.filter(deleted_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {deleted} tombstone row(s) older than {days} day(s)."
            )
        )
