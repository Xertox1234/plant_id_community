"""Todo 573 item 6: a failed garden notification logs its traceback."""

from unittest.mock import MagicMock, PropertyMock

from django.test import SimpleTestCase

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
