"""Account mail recovery (todo 619): verification and lockout mail.

Verification: a broker failure after the allowance is charged leaves a
durable outbox row; reconciliation sends it without another request and
without charging another slot, and the five-per-window bound still holds.
A failed send retries with backoff and stops.

Lockout: the mail is queued, never sent on the login request; a broker or
SMTP failure changes nothing about the lockout itself.
"""

import smtplib
from datetime import timedelta
from unittest.mock import patch

from apps.core import delivery
from apps.core.constants import ACCOUNT_LOCKOUT_THRESHOLD, LOCKOUT_STATUS_KEY
from apps.core.models import DeliveryIntent
from apps.core.security import SecurityMonitor
from apps.users import tasks
from apps.users.constants import ACCOUNT_MAIL_MAX_RETRIES, VERIFICATION_EMAIL_CAP
from apps.users.email_verification import send_verification_email
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status
RESEND_URL = "/api/v1/auth/verify-email/resend/"
LOGIN_URL = "/api/v1/auth/login/"
PASSWORD = "TestPassword123!"  # pragma: allowlist secret
WRONG_PASSWORD = "WrongPassword123!"  # pragma: allowlist secret
BROKER_DOWN = ConnectionError("broker down")


def _make_due():
    DeliveryIntent.objects.filter(status=Status.PENDING).update(
        next_attempt_at=timezone.now() - timedelta(seconds=1)
    )


class VerificationRecoveryTest(TestCase):
    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", email="ada@example.com", password=PASSWORD
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _resend(self, *, broker_down=False):
        cache.clear()  # the hourly rate limit is not what is under test
        if broker_down:
            with (
                patch.object(
                    tasks.send_verification_email_task, "delay", side_effect=BROKER_DOWN
                ),
                self.captureOnCommitCallbacks(execute=True),
            ):
                return self.client.post(RESEND_URL)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(RESEND_URL)

    def test_a_broker_failure_is_recovered_by_reconciliation(self):
        response = self._resend(broker_down=True)
        self.assertTrue(response.data["sent"])
        self.assertEqual(mail.outbox, [])
        intent = DeliveryIntent.objects.get(kind=Kind.VERIFICATION_EMAIL)
        self.assertEqual(
            (intent.recipient_id, intent.status), (self.user.pk, "pending")
        )

        _make_due()
        delivery.reconcile()  # .delay runs the task in process (conftest)

        self.assertEqual([m.to for m in mail.outbox], [["ada@example.com"]])
        intent.refresh_from_db()
        self.assertEqual(intent.status, Status.SENT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_emails_sent, 1)  # not charged again

    def test_recovery_keeps_the_five_per_window_bound(self):
        """Every request while the broker is down is charged; they share one
        pending row and recover as ONE mail; the sixth request is still
        refused; reconciliation charges nothing."""
        for _ in range(VERIFICATION_EMAIL_CAP):
            self.assertTrue(self._resend(broker_down=True).data["sent"])
        self.assertTrue(self._resend(broker_down=True).data["limit_reached"])
        self.assertEqual(
            DeliveryIntent.objects.filter(kind=Kind.VERIFICATION_EMAIL).count(), 1
        )

        _make_due()
        delivery.reconcile()
        _make_due()
        delivery.reconcile()  # a second pass finds nothing to send

        self.assertEqual(len(mail.outbox), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_emails_sent, VERIFICATION_EMAIL_CAP)
        self.assertTrue(self._resend().data["limit_reached"])
        self.assertEqual(len(mail.outbox), 1)

    def test_a_duplicate_task_sends_nothing(self):
        self.assertTrue(self._resend().data["sent"])
        self.assertEqual(len(mail.outbox), 1)

        # A re-drive that raced the first enqueue arrives after it was sent.
        tasks.send_verification_email_task.apply(args=(self.user.pk,))

        self.assertEqual(len(mail.outbox), 1)

    def test_a_transient_failure_retries_and_then_stops(self):
        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=smtplib.SMTPServerDisconnected("dropped"),
        ) as smtp:
            self.assertTrue(self._resend().data["sent"])

        # The first attempt plus ACCOUNT_MAIL_MAX_RETRIES (eager retries).
        self.assertEqual(smtp.call_count, ACCOUNT_MAIL_MAX_RETRIES + 1)
        intent = DeliveryIntent.objects.get(kind=Kind.VERIFICATION_EMAIL)
        self.assertEqual(intent.status, Status.FAILED)
        _make_due()
        with patch.object(tasks.send_verification_email_task, "delay") as redrive:
            delivery.reconcile()
        redrive.assert_not_called()  # terminal: never re-driven

    def test_a_retry_after_success_elsewhere_sends_nothing(self):
        """A transient failure, then the address is verified before the
        retry: the retry rechecks and finishes the row without sending."""
        from apps.users.email_verification import mark_email_verified

        with patch.object(tasks.send_verification_email_task, "delay"):
            with self.captureOnCommitCallbacks(execute=True):
                send_verification_email(self.user)
        intent = DeliveryIntent.objects.get(kind=Kind.VERIFICATION_EMAIL)
        mark_email_verified(self.user)

        tasks.send_verification_email_task.apply(args=(self.user.pk,))

        self.assertEqual(mail.outbox, [])
        intent.refresh_from_db()
        self.assertEqual(
            (intent.status, intent.last_error), (Status.SUPPRESSED, "not_needed")
        )


class LockoutMailIsQueuedTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="locked", email="locked@example.com", password=PASSWORD
        )

    def _lock(self):
        for _ in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username="locked", ip_address="192.168.1.100"
            )

    def test_the_login_request_never_sends_mail_itself(self):
        with patch.object(tasks.send_lockout_email_task, "delay") as delay:
            with patch("apps.core.security.send_mail") as inline_send:
                self._lock()

        delay.assert_called_once_with(self.user.pk)
        inline_send.assert_not_called()
        self.assertEqual(mail.outbox, [])
        is_locked, _ = SecurityMonitor.is_account_locked("locked")
        self.assertTrue(is_locked)

    @override_settings(RATELIMIT_ENABLE=False)
    def test_a_slow_or_failing_smtp_server_never_reaches_the_login_response(self):
        client = APIClient()
        csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        with (
            patch.object(tasks.send_lockout_email_task, "delay") as delay,
            patch(
                "apps.core.security.send_mail",
                side_effect=AssertionError("SMTP on the request"),
            ),
        ):
            for _ in range(ACCOUNT_LOCKOUT_THRESHOLD):
                response = client.post(
                    LOGIN_URL,
                    {"username": "locked", "password": WRONG_PASSWORD},
                    HTTP_X_CSRFTOKEN=csrf,
                )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "ACCOUNT_LOCKED")
        delay.assert_called_once_with(self.user.pk)

    def test_a_broker_failure_keeps_the_lockout_and_records_the_mail(self):
        with (
            patch.object(
                tasks.send_lockout_email_task, "delay", side_effect=BROKER_DOWN
            ),
            self.assertLogs("apps.core.security", "ERROR") as logs,
        ):
            self._lock()

        is_locked, _ = SecurityMonitor.is_account_locked("locked")
        self.assertTrue(is_locked)
        self.assertTrue(
            any("Could not queue the lockout email" in line for line in logs.output)
        )
        self.assertFalse(any("broker down" in line for line in logs.output))
        intent = DeliveryIntent.objects.get(kind=Kind.LOCKOUT_EMAIL)
        self.assertEqual(intent.payload, {})  # no IPs at rest

        _make_due()
        delivery.reconcile()  # the task runs in process (conftest)

        self.assertEqual([m.to for m in mail.outbox], [["locked@example.com"]])
        self.assertIn("192.168.1.100", mail.outbox[0].body)
        intent.refresh_from_db()
        self.assertEqual(intent.status, Status.SENT)

    def test_a_send_failure_retries_then_gives_up_without_unlocking(self):
        with (
            patch(
                "apps.core.security.send_mail",
                side_effect=smtplib.SMTPServerDisconnected("dropped"),
            ) as smtp,
            self.assertLogs("apps.users.tasks", "ERROR") as logs,
        ):
            self._lock()

        self.assertEqual(smtp.call_count, ACCOUNT_MAIL_MAX_RETRIES + 1)
        self.assertIn("giving up", logs.output[-1])
        is_locked, _ = SecurityMonitor.is_account_locked("locked")
        self.assertTrue(is_locked)

    def test_a_lockout_that_is_over_sends_nothing(self):
        with patch.object(tasks.send_lockout_email_task, "delay"):
            self._lock()
        cache.delete(LOCKOUT_STATUS_KEY.format(username="locked"))

        tasks.send_lockout_email_task.apply(args=(self.user.pk,))

        self.assertEqual(mail.outbox, [])
