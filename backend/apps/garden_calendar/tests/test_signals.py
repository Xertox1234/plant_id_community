"""Garden calendar signals module tests."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone


class ExpiredWeatherAlertCommandTest(TestCase):
    """Todo 593 #5: the expired-alert cleanup was a ``Command`` class inside
    signals.py, which manage.py never discovers. It is a real command now."""

    def _alert(self, expires_at):
        from ..models import WeatherAlert

        now = timezone.now()
        return WeatherAlert.objects.create(
            alert_type="frost",
            severity="low",
            zip_code="12345",
            title="Frost",
            message="Cold night",
            start_datetime=now,
            expires_at=expires_at,
        )

    def test_the_command_deactivates_only_expired_alerts(self):
        now = timezone.now()
        expired = self._alert(now - timedelta(hours=1))
        current = self._alert(now + timedelta(hours=1))
        out = StringIO()

        call_command("deactivate_expired_weather_alerts", stdout=out)

        expired.refresh_from_db()
        current.refresh_from_db()
        self.assertFalse(expired.is_active)
        self.assertTrue(current.is_active)
        self.assertIn("Deactivated 1 expired", out.getvalue())

    def test_signals_holds_no_command(self):
        from .. import signals

        self.assertFalse(hasattr(signals, "Command"))
