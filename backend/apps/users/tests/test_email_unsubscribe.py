"""Signed email unsubscribe links (todo 408).

The old link was ``/api/auth/unsubscribe/?user=<uuid>``: anyone holding (or
guessing) a user's UUID could POST it and switch off their email, and every
render path 500'd on templates that never existed. A link now carries a
``django.core.signing`` token scoped to ONE user and ONE list, and expires.

These pin the security property first — a forged, expired, foreign-salt or
unknown-list token changes nothing — then the happy path, then the email that
carries the link.
"""

import re
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from apps.core.services.email_service import EmailService, EmailType
from apps.core.services.notification_service import NotificationService
from apps.users.constants import RATE_LIMIT_EMAIL_UNSUBSCRIBE
from apps.users.email_unsubscribe import (
    UNSUBSCRIBE_MAX_AGE,
    UNSUBSCRIBE_SALT,
    UnsubscribeTokenExpired,
    UnsubscribeTokenInvalid,
    make_token,
    read_token,
)
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile
from wagtail_forum.preferences import wants_channel

User = get_user_model()

SITE = "https://houseplant-md.test"
LIST = "forum_reply"


def _reply_email_on(user) -> bool:
    overrides = (
        ForumProfile.objects.filter(user=user)
        .values_list("notification_preferences", flat=True)
        .first()
    )
    return wants_channel(overrides, "reply_added", "email")


def _reply_push_on(user) -> bool:
    overrides = (
        ForumProfile.objects.filter(user=user)
        .values_list("notification_preferences", flat=True)
        .first()
    )
    return wants_channel(overrides, "reply_added", "push")


def _later(delta):
    """Patch the signer's clock forward by *delta* (TimestampSigner reads
    time.time() in django.core.signing)."""
    import time

    real = time.time()
    return mock.patch(
        "django.core.signing.time.time", return_value=real + delta.total_seconds()
    )


class UnsubscribeTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="unsub", email="unsub@example.com"
        )

    def test_round_trip_names_the_user_and_list(self):
        user, list_id = read_token(make_token(self.user, LIST))
        self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(list_id, LIST)

    def test_tampered_token_is_invalid(self):
        token = make_token(self.user, LIST)
        forged = token[:-1] + ("A" if token[-1] != "A" else "B")
        with self.assertRaises(UnsubscribeTokenInvalid):
            read_token(forged)

    def test_token_for_a_different_user_cannot_be_rewritten(self):
        # Swap the UUID inside a genuine token's payload: the signature no
        # longer matches, so the victim is not reachable from the attacker's
        # own link.
        victim = User.objects.create_user(username="victim", email="v@example.com")
        token = make_token(self.user, LIST)
        payload, _, rest = token.partition(":")
        decoded = signing.b64_decode(payload.encode()).decode()
        swapped = decoded.replace(str(self.user.uuid), str(victim.uuid))
        forged = signing.b64_encode(swapped.encode()).decode() + ":" + rest
        with self.assertRaises(UnsubscribeTokenInvalid):
            read_token(forged)

    def test_token_signed_under_another_salt_is_invalid(self):
        # Same SECRET_KEY, different purpose: a signed value minted for some
        # other feature must not double as an unsubscribe link.
        # The unsalted case is the one that catches a dropped salt: without
        # it, any signing.dumps() anywhere in the codebase would mint links.
        payload = {"u": str(self.user.uuid), "l": LIST}
        for other in (
            signing.dumps(payload),
            signing.dumps(payload, salt="some.other.purpose"),
        ):
            with self.assertRaises(UnsubscribeTokenInvalid):
                read_token(other)

    def test_unknown_list_is_invalid(self):
        token = signing.dumps(
            {"u": str(self.user.uuid), "l": "everything"}, salt=UNSUBSCRIBE_SALT
        )
        with self.assertRaises(UnsubscribeTokenInvalid):
            read_token(token)

    def test_deleted_or_inactive_user_is_invalid(self):
        token = make_token(self.user, LIST)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(UnsubscribeTokenInvalid):
            read_token(token)
        self.user.delete()
        with self.assertRaises(UnsubscribeTokenInvalid):
            read_token(token)

    def test_expired_token_is_rejected_as_expired(self):
        token = make_token(self.user, LIST)
        with _later(UNSUBSCRIBE_MAX_AGE + timedelta(minutes=1)):
            with self.assertRaises(UnsubscribeTokenExpired):
                read_token(token)

    def test_token_inside_its_lifetime_still_works(self):
        token = make_token(self.user, LIST)
        with _later(UNSUBSCRIBE_MAX_AGE - timedelta(minutes=1)):
            user, _ = read_token(token)
        self.assertEqual(user.pk, self.user.pk)

    def test_expired_is_a_kind_of_invalid(self):
        # Callers that only care "can this link act?" catch the base class.
        self.assertTrue(issubclass(UnsubscribeTokenExpired, UnsubscribeTokenInvalid))


class UnsubscribeEndpointTests(TestCase):
    def setUp(self):
        cache.clear()  # the per-IP rate limiter's counter lives in the cache
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="reader", email="reader@example.com"
        )
        self.check_url = reverse("v1:users:email_unsubscribe_check")
        self.unsub_url = reverse("v1:users:email_unsubscribe")

    def _assert_nothing_changed(self):
        self.user.refresh_from_db()
        self.assertTrue(_reply_email_on(self.user))
        self.assertTrue(_reply_push_on(self.user))
        self.assertTrue(self.user.email_notifications)
        self.assertTrue(self.user.forum_notifications)

    def test_routes_live_under_v1(self):
        self.assertTrue(self.check_url.startswith("/api/v1/auth/"))
        self.assertTrue(self.unsub_url.startswith("/api/v1/auth/"))

    def test_check_describes_the_list_without_changing_it(self):
        token = make_token(self.user, LIST)
        response = self.client.post(self.check_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["list"], LIST)
        self.assertTrue(response.data["subscribed"])
        self.assertTrue(response.data["label"])
        self._assert_nothing_changed()

    def test_unsubscribe_turns_off_only_reply_email(self):
        token = make_token(self.user, LIST)
        response = self.client.post(self.unsub_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.data["subscribed"])
        self.user.refresh_from_db()
        self.assertFalse(_reply_email_on(self.user))
        # Push is a separate choice on the Settings grid — an EMAIL link must
        # not silence the phone too, and the account-wide switches (which no
        # web UI can turn back on) stay untouched.
        self.assertTrue(_reply_push_on(self.user))
        self.assertTrue(self.user.email_notifications)
        self.assertTrue(self.user.forum_notifications)

    def test_digest_link_turns_the_weekly_digest_off(self):
        # Todo 416: the digest's link (minted by digest_unsubscribe, the
        # WAGTAILFORUM_DIGEST_UNSUBSCRIBE callable) turns the digest off,
        # which the Settings page's "Email digest" select can turn back on.
        from apps.users.email_unsubscribe import digest_unsubscribe
        from wagtail_forum.models import DigestFrequency, ForumProfile

        profile = ForumProfile.for_user(self.user)
        profile.digest_frequency = DigestFrequency.WEEKLY
        profile.save(update_fields=["digest_frequency"])
        token = parse_qs(urlsplit(digest_unsubscribe(self.user)["url"]).query)["token"][
            0
        ]

        check = self.client.post(self.check_url, {"token": token}, format="json")
        self.assertEqual(check.data["list"], "forum_digest")
        self.assertTrue(check.data["subscribed"])

        response = self.client.post(self.unsub_url, {"token": token}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.data["subscribed"])
        profile.refresh_from_db()
        self.assertEqual(profile.digest_frequency, DigestFrequency.OFF)
        self._assert_nothing_changed()  # reply email/push and account switches

    def test_unsubscribe_is_idempotent(self):
        token = make_token(self.user, LIST)
        self.client.post(self.unsub_url, {"token": token}, format="json")
        again = self.client.post(self.unsub_url, {"token": token}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.data["subscribed"])
        self.assertFalse(_reply_email_on(self.user))

    def test_unsubscribe_keeps_other_stored_preferences(self):
        profile = ForumProfile.for_user(self.user)
        profile.notification_preferences = {"mention": {"push": False}}
        profile.save(update_fields=["notification_preferences"])
        token = make_token(self.user, LIST)
        self.client.post(self.unsub_url, {"token": token}, format="json")
        profile.refresh_from_db()
        self.assertEqual(
            profile.notification_preferences,
            {"mention": {"push": False}, "reply": {"email": False}},
        )

    def test_forged_token_changes_nothing(self):
        token = make_token(self.user, LIST)
        forged = token[:-1] + ("A" if token[-1] != "A" else "B")
        for url in (self.check_url, self.unsub_url):
            response = self.client.post(url, {"token": forged}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], "invalid")
        self._assert_nothing_changed()

    def test_expired_token_changes_nothing(self):
        token = make_token(self.user, LIST)
        with _later(UNSUBSCRIBE_MAX_AGE + timedelta(days=1)):
            for url in (self.check_url, self.unsub_url):
                response = self.client.post(url, {"token": token}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], "expired")
        self._assert_nothing_changed()

    def test_missing_or_non_string_token_is_invalid(self):
        for body in ({}, {"token": ""}, {"token": 123}, {"token": ["x"]}):
            response = self.client.post(self.unsub_url, body, format="json")
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.data["code"], "invalid")
        self._assert_nothing_changed()

    def test_removed_session_preference_views_have_no_route(self):
        # Todo 415: `email_preferences` rendered a template that does not
        # exist and `ajax_update_preference` had no client. Both are gone.
        for name in ("email_preferences", "ajax_update_preference"):
            with self.assertRaises(NoReverseMatch):
                reverse(f"v1:users:{name}")

    def test_non_object_json_body_is_invalid_not_a_500(self):
        # Todo 417: DRF parses a JSON array or bare string to a list/str, and
        # `.get("token")` on it raised AttributeError → 500, with no token.
        for url in (self.check_url, self.unsub_url):
            for body in ([], ["token"], "x", 7):
                response = self.client.post(url, body, format="json")
                self.assertEqual(response.status_code, 400, (url, body))
                self.assertEqual(response.data["code"], "invalid", (url, body))
        self._assert_nothing_changed()

    def test_the_old_bare_uuid_link_no_longer_works(self):
        # The pre-408 link: ?user=<uuid>, no token. Both verbs.
        legacy = f"{self.unsub_url}?user={self.user.uuid}&type=forum_reply"
        self.assertEqual(self.client.get(legacy).status_code, 405)
        response = self.client.post(legacy, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self._assert_nothing_changed()

    def test_signed_in_session_does_not_choose_the_target(self):
        # The token alone names the account: a signed-in visitor holding
        # someone else's link unsubscribes THAT account, and their own
        # session never redirects the action onto themselves.
        other = User.objects.create_user(username="other", email="o@example.com")
        self.client.force_authenticate(other)
        token = make_token(self.user, LIST)
        self.client.post(self.unsub_url, {"token": token}, format="json")
        self.assertFalse(_reply_email_on(self.user))
        self.assertTrue(_reply_email_on(other))

    def test_probing_is_rate_limited_per_ip(self):
        limit = int(RATE_LIMIT_EMAIL_UNSUBSCRIBE.split("/")[0])
        for _ in range(limit):
            self.client.post(self.check_url, {"token": "x"}, format="json")
        response = self.client.post(self.check_url, {"token": "x"}, format="json")
        self.assertEqual(response.status_code, 429)

    def test_get_is_not_allowed(self):
        # Mail scanners prefetch GET links; only a POST may act.
        token = make_token(self.user, LIST)
        response = self.client.get(self.unsub_url, {"token": token})
        self.assertEqual(response.status_code, 405)
        self._assert_nothing_changed()


@override_settings(SITE_URL=SITE)
class UnsubscribeLinkInEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="mailed", email="mailed@example.com"
        )

    def _send_forum_reply(self):
        sent = NotificationService().send_forum_reply_notification(
            user=self.user,
            topic_title="Yellow leaves",
            reply_author="fern",
            reply_excerpt="Try less water.",
            topic_url=f"{SITE}/forum/1-help/2-yellow-leaves",
        )
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0]

    def _unsubscribe_urls(self, message):
        html = message.alternatives[0][0]
        bodies = message.body + html
        return set(
            re.findall(re.escape(SITE) + r"/unsubscribe\?token=[^\s\"<&]+", bodies)
        )

    def test_forum_reply_email_carries_a_working_signed_link(self):
        message = self._send_forum_reply()
        urls = self._unsubscribe_urls(message)
        self.assertEqual(len(urls), 1, urls)
        (url,) = urls
        token = parse_qs(urlsplit(url).query)["token"][0]
        user, list_id = read_token(token)
        self.assertEqual((user.pk, list_id), (self.user.pk, LIST))
        # The link actually works end to end.
        response = APIClient().post(
            reverse("v1:users:email_unsubscribe"), {"token": token}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(_reply_email_on(self.user))

    def test_no_bare_uuid_link_in_the_email(self):
        message = self._send_forum_reply()
        html = message.alternatives[0][0]
        for body in (message.body, html):
            self.assertNotIn("?user=", body)
            self.assertNotIn("/api/auth/unsubscribe", body)

    def test_list_unsubscribe_header_points_at_the_same_link(self):
        message = self._send_forum_reply()
        (url,) = self._unsubscribe_urls(message)
        self.assertEqual(message.extra_headers["List-Unsubscribe"], f"<{url}>")

    def test_without_api_public_url_there_is_no_one_click_header(self):
        with self.settings(API_PUBLIC_URL=""):
            message = self._send_forum_reply()
        self.assertNotIn("List-Unsubscribe-Post", message.extra_headers)

    def test_one_click_header_accepts_a_bare_post(self):
        # Todo 416 / RFC 8058: with API_PUBLIC_URL set, the header names this
        # API's endpoint, and a mail provider's cookie-less, CSRF-less POST of
        # `List-Unsubscribe=One-Click` to it unsubscribes.
        with self.settings(API_PUBLIC_URL="https://api.example"):
            message = self._send_forum_reply()
        self.assertEqual(
            message.extra_headers["List-Unsubscribe-Post"],
            "List-Unsubscribe=One-Click",
        )
        header = message.extra_headers["List-Unsubscribe"]
        self.assertTrue(header.startswith("<https://api.example/api/v1/auth/"))
        url = header[1:-1]
        # The body still links the web page (a human's click is a GET).
        self.assertEqual(len(self._unsubscribe_urls(message)), 1)

        cache.clear()  # the unsubscribe rate limit counts per IP
        parts = urlsplit(url)
        response = Client(enforce_csrf_checks=True).post(
            f"{parts.path}?{parts.query}",
            data="List-Unsubscribe=One-Click",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(_reply_email_on(self.user))

    def test_one_click_rejects_a_forged_token(self):
        cache.clear()
        response = Client(enforce_csrf_checks=True).post(
            reverse("v1:users:email_unsubscribe_one_click") + "?token=forged",
            data="List-Unsubscribe=One-Click",
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(_reply_email_on(self.user))

    def test_digest_callable_carries_one_click_headers(self):
        from apps.users.email_unsubscribe import digest_unsubscribe

        with self.settings(API_PUBLIC_URL="https://api.example"):
            links = digest_unsubscribe(self.user)
        self.assertIn("/unsubscribe?token=", links["url"])
        self.assertEqual(
            links["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click"
        )
        token = parse_qs(urlsplit(links["headers"]["List-Unsubscribe"][1:-1]).query)[
            "token"
        ][0]
        self.assertEqual(read_token(token)[1], "forum_digest")

    def test_reply_email_offers_unfollow_not_a_dead_fragment(self):
        # Todo 416: the SPA topic page reads only #post-<id>, so a
        # #unsubscribe fragment did nothing.
        html = self._send_forum_reply().alternatives[0][0]
        self.assertNotIn("#unsubscribe", html)
        self.assertIn("Unfollow this topic", html)

    def test_preferences_link_is_the_web_settings_page(self):
        message = self._send_forum_reply()
        self.assertIn(f"{SITE}/settings", message.body)
        self.assertNotIn("#!/", message.body)

    def test_an_email_type_without_a_list_gets_no_unsubscribe_link(self):
        # A link must only be offered where it can do something; the welcome
        # email has no list to leave.
        EmailService().send_email(
            email_type=EmailType.NEWSLETTER,
            recipient=self.user,
            subject="Welcome",
            template_name="welcome_email",
        )
        message = mail.outbox[0]
        self.assertNotIn("List-Unsubscribe", message.extra_headers)
        self.assertNotIn("/unsubscribe?token=", message.body)
