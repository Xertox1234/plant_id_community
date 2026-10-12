"""Todo 573 item 6: a failed garden notification logs its traceback."""

from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, PropertyMock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ..signals import notify_event_rsvp_updated


class NotificationFailureLoggingTest(SimpleTestCase):
    def test_a_failed_rsvp_notification_logs_the_traceback(self):
        instance = MagicMock(status="going")
        type(instance).event = PropertyMock(side_effect=RuntimeError("boom"))

        with self.assertLogs("apps.garden_calendar.signals", level="ERROR") as logs:
            notify_event_rsvp_updated(EventAttendeeStub, instance, created=True)

        record = logs.records[0]
        self.assertEqual(
            record.getMessage(), "[NOTIFY] Failed to send RSVP notification: boom"
        )
        # Lazy %-args, not an f-string: the template is the greppable part.
        self.assertEqual(record.msg, "[NOTIFY] Failed to send RSVP notification: %s")
        self.assertIsNotNone(record.exc_info)


class EventAttendeeStub:
    """Stands in for the sender; the receiver never reads it."""


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
