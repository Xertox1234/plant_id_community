"""Count delivery-outbox rows by kind and outcome (todo 623).

Read-only. The outcomes are ``apps.core.notification_ops.Outcome``:
``accepted`` is the provider taking the message, not delivery; delivered,
bounced and complained come only from the email provider's webhook and are
on ``EmailNotification``, not here. Rows are kept
``DELIVERY_RETENTION_DAYS`` after they finish, so a window longer than that
undercounts finished rows.

    manage.py delivery_outcomes            # last 24 hours
    manage.py delivery_outcomes --hours 168
"""

from datetime import timedelta

from apps.core.notification_ops import SEND_OUTCOMES, outbox_outcome_counts
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Count delivery-outbox rows by kind and outcome (read-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Rows created in the last N hours (default 24).",
        )

    def handle(self, *args, **options):
        hours = max(1, options["hours"])
        totals = outbox_outcome_counts(since=timezone.now() - timedelta(hours=hours))
        self.stdout.write(f"[OUTCOME] outbox rows created in the last {hours}h")
        if not totals:
            self.stdout.write("[OUTCOME] none")
            return
        for kind in sorted(totals):
            counts = totals[kind]
            parts = " ".join(f"{o}={counts.get(o, 0)}" for o in SEND_OUTCOMES)
            self.stdout.write(f"[OUTCOME] kind={kind} {parts}")
