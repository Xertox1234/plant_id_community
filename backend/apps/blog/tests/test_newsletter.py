"""Blog newsletter double opt-in and signed-link unsubscribe (todo 409)."""

import re
import time
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

from apps.blog import newsletter
from apps.blog.constants import (
    NEWSLETTER_CONFIRM_MAX_AGE_SECONDS,
    NEWSLETTER_CONFIRMATION_RESEND_SECONDS,
)
from apps.blog.models import BlogNewsletter
from apps.blog.newsletter_views import SUBSCRIBE_DETAIL
from apps.blog.tasks import send_newsletter_confirmation
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

SITE = "https://web.example"
API = "https://api.example"


def _later(seconds):
    """Move the signer's clock forward (TimestampSigner reads time.time())."""
    return mock.patch(
        "django.core.signing.time.time", return_value=time.time() + seconds
    )


def _token_from(message):
    url = re.search(r"https://\S+/newsletter/confirm\?\S+", message.body).group(0)
    return parse_qs(urlparse(url).query)["token"][0]


def _subscriber(email="reader@example.com", **fields):
    return BlogNewsletter.objects.create(email=email, **fields)


@override_settings(SITE_URL=SITE)
class SubscribeEndpointTests(TestCase):
    """AC1: no answer from signup depends on the address's state."""

    def setUp(self):
        cache.clear()  # the per-IP rate limiter counts in the cache
        self.client = APIClient()
        self.url = reverse("v1:blog:newsletter-subscribe")

    def _subscribe(self, email):
        with mock.patch.object(send_newsletter_confirmation, "delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, {"email": email}, format="json")
        return response, delay

    def test_every_address_state_gets_the_same_answer(self):
        now = timezone.now()
        states = {
            "unknown@example.com": None,
            "pending@example.com": {"confirmation_sent_at": now},
            "confirmed@example.com": {"confirmed_at": now},
            "left@example.com": {
                "confirmed_at": now,
                "is_active": False,
                "unsubscribed_at": now,
            },
        }
        for email, fields in states.items():
            if fields is not None:
                _subscriber(email, **fields)
        before = list(BlogNewsletter.objects.order_by("pk").values())

        answers = set()
        for email in states:
            response, delay = self._subscribe(email)
            answers.add((response.status_code, response.content))
            delay.assert_called_once_with(email)

        self.assertEqual(
            answers, {(202, f'{{"detail":"{SUBSCRIBE_DETAIL}"}}'.encode())}
        )
        # The request itself touches no row: the task decides, so the
        # response time cannot tell the states apart either.
        self.assertEqual(list(BlogNewsletter.objects.order_by("pk").values()), before)

    def test_an_invalid_address_is_a_400_and_queues_nothing(self):
        response, delay = self._subscribe("not-an-address")
        self.assertEqual(response.status_code, 400)
        delay.assert_not_called()

    def test_a_form_post_is_refused(self):
        # Another site's hidden HTML form cannot sign addresses up.
        with mock.patch.object(send_newsletter_confirmation, "delay") as delay:
            response = self.client.post(self.url, {"email": "victim@example.com"})
        self.assertEqual(response.status_code, 415)
        delay.assert_not_called()

    def test_signup_is_rate_limited_per_ip(self):
        statuses = [
            self._subscribe(f"r{i}@example.com")[0].status_code for i in range(11)
        ]
        self.assertEqual(statuses, [202] * 10 + [429])

    def test_the_old_listing_and_delete_routes_are_gone(self):
        row = _subscriber(confirmed_at=timezone.now())
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.delete(f"{self.url}{row.pk}/").status_code, 404)

    def test_unsubscribe_by_bare_email_no_longer_works(self):
        row = _subscriber(confirmed_at=timezone.now())
        response = self.client.post(
            reverse("v1:blog:newsletter-unsubscribe"),
            {"email": row.email},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid")
        row.refresh_from_db()
        self.assertTrue(row.is_subscribed)


@override_settings(SITE_URL=SITE)
class RequestConfirmationTests(TestCase):
    """AC2: the task mails a link; only the link subscribes."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_a_new_address_is_stored_unconfirmed_and_mailed_a_link(self):
        self.assertTrue(newsletter.request_confirmation("  Reader@Example.COM "))
        row = BlogNewsletter.objects.get()
        self.assertEqual(row.email, "reader@example.com")
        self.assertFalse(row.is_subscribed)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reader@example.com"])
        self.assertIn(f"{SITE}/newsletter/confirm?token=", mail.outbox[0].body)

    def test_the_link_confirms_by_post_only(self):
        newsletter.request_confirmation("reader@example.com")
        token = _token_from(mail.outbox[0])
        url = reverse("v1:blog:newsletter-confirm")

        self.assertEqual(self.client.get(url, {"token": token}).status_code, 405)
        self.assertFalse(BlogNewsletter.objects.get().is_subscribed)

        response = self.client.post(url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"subscribed": True})
        self.assertTrue(BlogNewsletter.objects.get().is_subscribed)
        # Idempotent: a second click is still a success.
        response = self.client.post(url, {"token": token}, format="json")
        self.assertEqual(response.json(), {"subscribed": True})

    def test_no_email_to_an_address_already_subscribed(self):
        _subscriber(confirmed_at=timezone.now())
        self.assertFalse(newsletter.request_confirmation("reader@example.com"))
        self.assertEqual(mail.outbox, [])

    def test_a_resend_inside_the_window_is_skipped(self):
        newsletter.request_confirmation("reader@example.com")
        self.assertFalse(newsletter.request_confirmation("reader@example.com"))
        self.assertEqual(len(mail.outbox), 1)

    def test_a_resend_after_the_window_voids_the_older_link(self):
        newsletter.request_confirmation("reader@example.com")
        old = _token_from(mail.outbox[0])
        BlogNewsletter.objects.update(
            confirmation_sent_at=timezone.now()
            - timedelta(seconds=NEWSLETTER_CONFIRMATION_RESEND_SECONDS + 1)
        )
        self.assertTrue(newsletter.request_confirmation("reader@example.com"))
        new = _token_from(mail.outbox[1])

        with self.assertRaises(newsletter.NewsletterTokenInvalid):
            newsletter.confirm(old)
        newsletter.confirm(new)
        self.assertTrue(BlogNewsletter.objects.get().is_subscribed)

    def test_a_used_confirm_link_cannot_undo_an_unsubscribe(self):
        newsletter.request_confirmation("reader@example.com")
        token = _token_from(mail.outbox[0])
        newsletter.confirm(token)
        newsletter.unsubscribe(
            newsletter.make_unsubscribe_token(BlogNewsletter.objects.get())
        )
        response = self.client.post(
            reverse("v1:blog:newsletter-confirm"), {"token": token}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid")
        self.assertFalse(BlogNewsletter.objects.get().is_subscribed)

    def test_an_unsubscribed_address_must_confirm_again(self):
        now = timezone.now()
        _subscriber(confirmed_at=now, is_active=False, unsubscribed_at=now)
        self.assertTrue(newsletter.request_confirmation("reader@example.com"))
        self.assertFalse(BlogNewsletter.objects.get().is_subscribed)

        newsletter.confirm(_token_from(mail.outbox[0]))
        row = BlogNewsletter.objects.get()
        self.assertTrue(row.is_subscribed)
        self.assertIsNone(row.unsubscribed_at)

    def test_a_failed_send_does_not_start_the_throttle(self):
        with mock.patch.object(
            newsletter.EmailMultiAlternatives, "send", side_effect=OSError("smtp")
        ):
            self.assertFalse(newsletter.request_confirmation("reader@example.com"))
        self.assertIsNone(BlogNewsletter.objects.get().confirmation_sent_at)
        self.assertTrue(newsletter.request_confirmation("reader@example.com"))

    def test_a_failure_building_the_link_does_not_start_the_throttle(self):
        with mock.patch.object(newsletter, "confirm_url", side_effect=ValueError):
            self.assertFalse(newsletter.request_confirmation("reader@example.com"))
        self.assertIsNone(BlogNewsletter.objects.get().confirmation_sent_at)

    def test_a_row_from_the_old_endpoint_is_not_subscribed(self):
        # Single opt-in rows: active, never confirmed. Never mailed a newsletter.
        self.assertFalse(_subscriber(is_active=True).is_subscribed)

    def test_the_task_runs_the_decision(self):
        send_newsletter_confirmation.apply(args=["reader@example.com"])
        self.assertEqual(len(mail.outbox), 1)


@override_settings(SITE_URL=SITE)
class TokenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.row = _subscriber(confirmation_sent_at=timezone.now())

    def _post(self, name, token):
        return self.client.post(reverse(name), {"token": token}, format="json")

    def test_an_expired_confirm_link_says_so(self):
        token = newsletter.make_confirm_token(self.row)
        with _later(NEWSLETTER_CONFIRM_MAX_AGE_SECONDS + 60):
            response = self._post("v1:blog:newsletter-confirm", token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "expired")

    def test_tokens_do_not_cross_purposes(self):
        confirm = newsletter.make_confirm_token(self.row)
        unsubscribe = newsletter.make_unsubscribe_token(self.row)
        self.assertEqual(
            self._post("v1:blog:newsletter-unsubscribe", confirm).status_code, 400
        )
        self.assertEqual(
            self._post("v1:blog:newsletter-confirm", unsubscribe).status_code, 400
        )
        self.row.refresh_from_db()
        self.assertTrue(self.row.is_active)
        self.assertIsNone(self.row.confirmed_at)

    def test_malformed_tokens_are_invalid(self):
        for body in ({"token": ""}, {"token": "garbage"}, {}, ["not", "an", "object"]):
            response = self.client.post(
                reverse("v1:blog:newsletter-confirm"), body, format="json"
            )
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()["code"], "invalid", body)

    def test_a_deleted_subscriber_is_just_invalid(self):
        token = newsletter.make_unsubscribe_token(self.row)
        self.row.delete()
        response = self._post("v1:blog:newsletter-unsubscribe", token)
        self.assertEqual(response.json()["code"], "invalid")

    def test_unsubscribe_link(self):
        self.row.confirmed_at = timezone.now()
        self.row.save()
        token = newsletter.make_unsubscribe_token(self.row)
        response = self._post("v1:blog:newsletter-unsubscribe", token)
        self.assertEqual(response.json(), {"subscribed": False})
        self.row.refresh_from_db()
        self.assertFalse(self.row.is_subscribed)
        self.assertIsNotNone(self.row.unsubscribed_at)
        # Idempotent.
        response = self._post("v1:blog:newsletter-unsubscribe", token)
        self.assertEqual(response.json(), {"subscribed": False})

    def test_the_token_endpoints_are_rate_limited_per_ip(self):
        for name in ("v1:blog:newsletter-confirm", "v1:blog:newsletter-unsubscribe"):
            statuses = [self._post(name, "garbage").status_code for _ in range(31)]
            self.assertEqual(statuses, [400] * 30 + [429], name)

    def test_one_click_post_unsubscribes_and_get_only_redirects(self):
        self.row.confirmed_at = timezone.now()
        self.row.save()
        token = newsletter.make_unsubscribe_token(self.row)
        url = reverse("v1:blog:newsletter-unsubscribe-one-click")

        response = self.client.get(url, {"token": token})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith(f"{SITE}/newsletter/unsubscribe?token=")
        )
        self.row.refresh_from_db()
        self.assertTrue(self.row.is_subscribed)

        response = self.client.post(f"{url}?token={token}")
        self.assertEqual(response.status_code, 200)
        self.row.refresh_from_db()
        self.assertFalse(self.row.is_subscribed)

    @override_settings(API_PUBLIC_URL=API)
    def test_headers_offer_one_click_on_the_api(self):
        headers = newsletter.unsubscribe_headers(self.row)
        self.assertTrue(
            headers["List-Unsubscribe"].startswith(
                f"<{API}/api/v1/blog/newsletter/unsubscribe/one-click/?token="
            )
        )
        self.assertEqual(headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    @override_settings(API_PUBLIC_URL="")
    def test_headers_fall_back_to_the_web_page(self):
        headers = newsletter.unsubscribe_headers(self.row)
        self.assertEqual(set(headers), {"List-Unsubscribe"})
        self.assertIn(
            f"<{SITE}/newsletter/unsubscribe?token=", headers["List-Unsubscribe"]
        )
