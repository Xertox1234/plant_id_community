"""Management command: run the nightly privacy prune once (Plan B task 8).

The same work as the ``privacy-retention-prune`` beat task
(``apps.users.retention.run_privacy_prune``). ``--dry-run`` counts what each
part would do and deletes, erases and queues nothing.
"""

from typing import Any

from apps.users.retention import run_privacy_prune
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Delete email records, blog views and audit rows past retention, "
        "release held forum posts, re-queue stalled deletions and prune "
        "orphaned Firebase logins, expired sessions and unreachable "
        "conversations."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count what would change; change nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options["dry_run"]
        counts = run_privacy_prune(dry_run=dry_run)
        verb = "would" if dry_run else "did"
        retention = " ".join(f"{k}={v}" for k, v in counts["retention"].items())
        self.stdout.write(f"retention ({verb} delete): {retention}")
        self.stdout.write(f"held posts ({verb} erase): {counts['held_posts']}")
        self.stdout.write(
            f"stale deletions ({verb} re-queue): {counts['stale_deletions']}"
        )
        self.stdout.write(
            f"orphaned Firebase logins ({verb} delete): "
            f"{counts['orphan_firebase_logins']}"
        )
        self.stdout.write(f"expired sessions ({verb} delete): {counts['sessions']}")
        self.stdout.write(
            f"unreachable conversations ({verb} delete): {counts['conversations']}"
        )
