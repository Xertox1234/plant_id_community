"""Newsletter confirmation recovery (todo 619).

A failed confirmation send is retried with bounded backoff (a skip never
is); a signup whose enqueue the broker refused still answers 202 and is
recovered by reconciliation, with the address never stored in the outbox.
"""

import smtplib
from datetime import timedelta
from unittest import mock

from apps.blog.constants import (
    NEWSLETTER_CONFIRMATION_MAX_RETRIES,
    NEWSLETTER_CONFIRMATION_RETRY_DELAY,
)
from apps.blog.models import BlogNewsletter
from apps.blog.tasks import send_newsletter_confirmation
from apps.core import delivery
from apps.core.models import DeliveryIntent
from celery.exceptions import Retry
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

SITE = "https://web.example"
SEND = "django.core.mail.EmailMultiAlternatives.send"
Status = DeliveryIntent.Status


def _run(retries, email="reader@example.com", intent_id=None):
    """One attempt with Celery's request context, so the countdown passed to
    ``retry`` can be pinned (``.apply()`` ignores it, docs/rules/celery.md)."""
    task = send_newsletter_confirmation
    task.push_request(retries=retries)
    try:
        return task.run(email, intent_id=intent_id)
    finally:
        task.pop_request()


@override_settings(SITE_URL=SITE)
class ConfirmationRetryTest(TestCase):
    def test_a_failed_send_retries_with_backoff(self):
        for attempt in range(NEWSLETTER_CONFIRMATION_MAX_RETRIES):
            with (
                self.subTest(attempt=attempt),
                mock.patch(SEND, side_effect=smtplib.SMTPServerDisconnected("x")),
                mock.patch.object(
                    send_newsletter_confirmation, "retry", side_effect=Retry()
                ) as retry,
            ):
                with self.assertRaises(Retry):
                    _run(attempt)
                self.assertEqual(
                    retry.call_args.kwargs["countdown"],
                    NEWSLETTER_CONFIRMATION_RETRY_DELAY * 2**attempt,
                )

    def test_the_retry_sends_once_the_server_is_back(self):
        with mock.patch(SEND, side_effect=[ConnectionError("down"), 1]) as smtp:
            send_newsletter_confirmation.apply(args=["reader@example.com"])
        # Eager retries: the failure gave the stamp back, so the retry was
        # not throttled, and it sent once.
        self.assertEqual(smtp.call_count, 2)
        self.assertIsNotNone(
            BlogNewsletter.objects.get(email="reader@example.com").confirmation_sent_at
        )

    def test_the_last_failure_is_logged_and_dropped(self):
        with (
            mock.patch(SEND, side_effect=ConnectionError("down")),
            mock.patch.object(send_newsletter_confirmation, "retry") as retry,
            self.assertLogs("apps.blog.tasks", "ERROR") as logs,
        ):
            _run(NEWSLETTER_CONFIRMATION_MAX_RETRIES)
        retry.assert_not_called()
        self.assertIn("giving up", logs.output[0])
        self.assertNotIn("reader@example.com", logs.output[0])

    def test_a_skip_is_never_retried(self):
        BlogNewsletter.objects.create(
            email="reader@example.com", confirmed_at=timezone.now()
        )
        with mock.patch.object(send_newsletter_confirmation, "retry") as retry:
            _run(0)
        retry.assert_not_called()
        self.assertEqual(mail.outbox, [])


@override_settings(SITE_URL=SITE)
class SignupBrokerFailureTest(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("v1:blog:newsletter-subscribe")

    def test_a_refused_enqueue_still_answers_202_and_is_recovered(self):
        with (
            mock.patch.object(
                send_newsletter_confirmation,
                "delay",
                side_effect=ConnectionError("broker down"),
            ),
            # Outside the capture: its callbacks run as it exits.
            self.assertLogs("apps.blog.newsletter_views", "ERROR") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = APIClient().post(
                self.url, {"email": "Reader@Example.com"}, format="json"
            )
        self.assertEqual(response.status_code, 202)
        self.assertFalse(any("broker down" in line for line in logs.output))
        self.assertFalse(any("example.com" in line.lower() for line in logs.output))
        subscriber = BlogNewsletter.objects.get(email="reader@example.com")
        intent = DeliveryIntent.objects.get(
            kind=DeliveryIntent.Kind.NEWSLETTER_CONFIRMATION
        )
        # The outbox names the subscriber by pk, never by address.
        self.assertEqual(intent.subject_key, str(subscriber.pk))
        self.assertNotIn("example.com", str(intent.payload))
        self.assertEqual(mail.outbox, [])

        DeliveryIntent.objects.update(
            next_attempt_at=timezone.now() - timedelta(seconds=1)
        )
        with mock.patch.object(
            send_newsletter_confirmation,
            "delay",
            side_effect=lambda *a, **kw: send_newsletter_confirmation.apply(
                args=a, kwargs=kw
            ),
        ):
            delivery.reconcile()

        self.assertEqual([m.to for m in mail.outbox], [["reader@example.com"]])
        intent.refresh_from_db()
        self.assertEqual(intent.status, Status.SENT)

    def test_a_reader_who_subscribed_meanwhile_gets_nothing_more(self):
        with (
            mock.patch.object(
                send_newsletter_confirmation,
                "delay",
                side_effect=ConnectionError("broker down"),
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            APIClient().post(self.url, {"email": "reader@example.com"}, format="json")
        BlogNewsletter.objects.filter(email="reader@example.com").update(
            confirmed_at=timezone.now(), is_active=True
        )
        intent = DeliveryIntent.objects.get()

        send_newsletter_confirmation.apply(
            args=["reader@example.com"], kwargs={"intent_id": intent.pk}
        )

        self.assertEqual(mail.outbox, [])
        intent.refresh_from_db()
        self.assertEqual(intent.status, Status.SUPPRESSED)
