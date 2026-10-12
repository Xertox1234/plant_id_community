"""Deactivate weather alerts whose ``expires_at`` has passed.

Moved out of ``signals.py``, where a ``Command`` class sat that manage.py never
discovers (todo 593 #5). Not scheduled anywhere yet: run it from cron or
Celery beat when weather alerts go live.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import WeatherAlert


class Command(BaseCommand):
    help = "Deactivate expired weather alerts"

    def handle(self, *args, **options):
        count = WeatherAlert.objects.filter(
            expires_at__lt=timezone.now(), is_active=True
        ).update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(f"[GARDEN] Deactivated {count} expired weather alerts")
        )
