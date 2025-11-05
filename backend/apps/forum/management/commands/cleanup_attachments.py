"""
Management command to clean up soft-deleted attachments.

Permanently deletes attachments that have been soft-deleted for 30+ days.
This frees up storage space while preserving recent deletions for restoration.

Usage:
    python manage.py cleanup_attachments [--dry-run] [--days=30]

Schedule via cron:
    0 2 * * 0  /path/to/venv/bin/python /path/to/manage.py cleanup_attachments
    (Runs every Sunday at 2 AM)
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone
from django.db import transaction

from apps.forum.models import Attachment
from apps.forum.constants import ATTACHMENT_CLEANUP_DAYS, ATTACHMENT_CLEANUP_BATCH_SIZE

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = f'Permanently delete attachments that have been soft-deleted for {ATTACHMENT_CLEANUP_DAYS}+ days'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--days',
            type=int,
            default=ATTACHMENT_CLEANUP_DAYS,
            help=f'Delete attachments soft-deleted for this many days (default: {ATTACHMENT_CLEANUP_DAYS})'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=ATTACHMENT_CLEANUP_BATCH_SIZE,
            help=f'Number of attachments to delete per batch (default: {ATTACHMENT_CLEANUP_BATCH_SIZE})'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)

        # Find attachments to delete
        attachments_to_delete = Attachment.objects.filter(
            is_active=False,
            deleted_at__lte=cutoff_date
        ).select_related('post')

        total_count = attachments_to_delete.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'No attachments found that were deleted more than {days} days ago'
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would permanently delete {total_count} attachments'
                )
            )
            for attachment in attachments_to_delete[:10]:  # Show first 10
                self.stdout.write(
                    f'  - {attachment.original_filename} (deleted {attachment.deleted_at})'
                )
            if total_count > 10:
                self.stdout.write(f'  ... and {total_count - 10} more')
            return

        # Perform deletion in batches
        deleted_count = 0
        failed_count = 0

        self.stdout.write(
            f'Permanently deleting {total_count} attachments in batches of {batch_size}...'
        )

        while True:
            batch = list(attachments_to_delete[:batch_size])
            if not batch:
                break

            for attachment in batch:
                try:
                    with transaction.atomic():
                        filename = attachment.original_filename
                        attachment.hard_delete()
                        deleted_count += 1
                        if deleted_count % 10 == 0:
                            self.stdout.write(f'  Deleted {deleted_count}/{total_count}...')
                        logger.info(f'[CLEANUP] Hard-deleted attachment: {filename}')
                except Exception as e:
                    failed_count += 1
                    logger.error(f'[CLEANUP] Failed to delete attachment {attachment.id}: {e}')

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Cleanup complete:\n'
                f'  - Successfully deleted: {deleted_count} attachments\n'
                f'  - Failed: {failed_count} attachments\n'
                f'  - Cutoff date: {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")}'
            )
        )

        if failed_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {failed_count} attachments failed to delete. Check logs for details.'
                )
            )
