"""One-time backfill: re-sanitize all existing forum post content."""

import logging

from apps.forum_integration.sanitization import sanitize_forum_html
from django.core.management.base import BaseCommand
from django.db import transaction
from machina.apps.forum_conversation.models import Post

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sanitize existing Post.content with the forum HTML allowlist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        changed = 0
        scanned = 0
        # Atomic: a crash mid-run rolls back every sanitized post, so the table is
        # never left half-cleaned with no way to tell where it stopped (todo 114).
        with transaction.atomic():
            for post in Post.objects.all().iterator():
                scanned += 1
                cleaned = sanitize_forum_html(post.content or "")
                if cleaned != (post.content or ""):
                    changed += 1
                    if not dry_run:
                        post.content = cleaned
                        post.save(update_fields=["content"])
            if dry_run:
                # Defense-in-depth: discard anything written so --dry-run can never
                # commit, even if a future change introduces an errant save.
                transaction.set_rollback(True)
        verb = "would change" if dry_run else "changed"
        self.stdout.write(
            self.style.SUCCESS(f"[forum] scanned {scanned}, {verb} {changed} posts")
        )
        logger.info(
            "[FORUM] sanitize_forum_content: scanned=%d, %s=%d", scanned, verb, changed
        )
