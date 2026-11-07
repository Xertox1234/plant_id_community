"""
Tests for the Google OAuth verified-email guard (web flow).

Matching — or creating — a Django account by an email the provider has NOT
verified is an account-takeover vector. These tests pin the guard in both
reachable code paths:

1. The custom ``oauth_views`` flow (``/api/auth/oauth/google/callback/``), which
   does its own token exchange and calls ``_find_or_create_user``.
2. The django-allauth flow (``/accounts/...``), whose ``pre_social_login`` adapter
   auto-links a social login to an existing local account by email.
"""

import time
from unittest.mock import MagicMock, patch

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from apps.users import oauth_views
from apps.users.constants import LEGAL_POLICY_VERSION
from apps.users.email_verification import mark_email_verified
from apps.users.oauth_adapters import CustomSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


def _response(status_code=200, json_data=None):
    """Build a minimal stand-in for a ``requests`` Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class HandleGoogleCallbackVerifiedEmailTest(TestCase):
    """The guard lives in ``_handle_google_callback``: it strips the email from
    the returned profile when Google reports it as unverified, which makes the
    downstream ``_find_or_create_user`` fail closed (no match, no create)."""

    def setUp(self):
        self.request = RequestFactory().get("/api/auth/oauth/google/callback/")

    @patch("requests.get")
    @patch("requests.post")
    def test_unverified_email_is_stripped_from_profile(self, mock_post, mock_get):
        mock_post.return_value = _response(200, {"access_token": "tok"})
        mock_get.return_value = _response(
            200,
            {
                "email": "victim@example.com",
                "verified_email": False,
                "given_name": "V",
            },
        )

        profile = oauth_views._handle_google_callback(self.request, code="abc")

        # Profile still returned (other fields intact) but the unverified email
        # is removed so no account can be matched or created from it.
        self.assertIsNotNone(profile)
        self.assertNotIn("email", profile)
        self.assertEqual(profile.get("given_name"), "V")

    @patch("requests.get")
    @patch("requests.post")
    def test_missing_verified_flag_is_treated_as_unverified(self, mock_post, mock_get):
        # Fail closed: a profile with no verified flag at all must not be trusted.
        mock_post.return_value = _response(200, {"access_token": "tok"})
        mock_get.return_value = _response(200, {"email": "victim@example.com"})

        profile = oauth_views._handle_google_callback(self.request, code="abc")

        self.assertNotIn("email", profile)

    @patch("requests.get")
    @patch("requests.post")
    def test_verified_email_is_preserved(self, mock_post, mock_get):
        # The intended auto-link behaviour is untouched for verified emails.
        mock_post.return_value = _response(200, {"access_token": "tok"})
        mock_get.return_value = _response(
            200, {"email": "real@example.com", "verified_email": True}
        )

        profile = oauth_views._handle_google_callback(self.request, code="abc")

        self.assertEqual(profile["email"], "real@example.com")

    @patch("requests.get")
    @patch("requests.post")
    def test_oidc_email_verified_claim_is_honoured(self, mock_post, mock_get):
        # OIDC userinfo uses `email_verified` rather than v2's `verified_email`.
        mock_post.return_value = _response(200, {"access_token": "tok"})
        mock_get.return_value = _response(
            200, {"email": "real@example.com", "email_verified": True}
        )

        profile = oauth_views._handle_google_callback(self.request, code="abc")

        self.assertEqual(profile["email"], "real@example.com")


class FindOrCreateUserGuardTest(TestCase):
    """Security property: once the email has been stripped (unverified), the
    existing account is neither matched nor mutated, and no user is created."""

    def test_stripped_email_does_not_match_existing_account(self):
        existing = User.objects.create_user(
            username="victim", email="victim@example.com"
        )
        before = User.objects.count()

        # Profile as it would arrive after the guard removed the email.
        result = oauth_views._find_or_create_user("google", {"given_name": "V"})

        self.assertIsNone(result)
        self.assertEqual(User.objects.count(), before)
        existing.refresh_from_db()
        self.assertEqual(existing.email, "victim@example.com")

    def test_verified_email_matches_existing_account(self):
        existing = User.objects.create_user(username="real", email="real@example.com")
        mark_email_verified(existing)  # it proved its email (todo 446)

        result = oauth_views._find_or_create_user(
            "google", {"email": "real@example.com", "id": "g-real"}
        )

        self.assertEqual(result, existing)


class PreSocialLoginVerifiedEmailTest(TestCase):
    """The allauth adapter must not auto-link an unverified social email to an
    existing local account."""

    def setUp(self):
        self.adapter = CustomSocialAccountAdapter()
        self.request = RequestFactory().get("/accounts/google/login/callback/")

    def _sociallogin(self, *, email, verified):
        sociallogin = MagicMock()
        sociallogin.account.provider = "google"
        sociallogin.account.extra_data = {"email": email}
        sociallogin.is_existing = False
        sociallogin.email_addresses = [EmailAddress(email=email, verified=verified)]
        sociallogin.connect = MagicMock()
        return sociallogin

    def test_unverified_email_aborts_without_linking_or_creating(self):
        User.objects.create_user(username="victim", email="victim@example.com")
        before = User.objects.count()
        sociallogin = self._sociallogin(email="victim@example.com", verified=False)

        # The flow is aborted with a redirect — a bare return would let allauth's
        # auto-signup create a second account holding the victim's email.
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(self.request, sociallogin)

        self.assertIsInstance(ctx.exception.response, HttpResponseRedirect)
        self.assertIn("error=unverified_email", ctx.exception.response.url)
        sociallogin.connect.assert_not_called()
        self.assertEqual(User.objects.count(), before)

    def test_no_verified_email_record_aborts(self):
        # extra_data carries the email, but the provider enumerated no matching
        # verified EmailAddress — fail closed and abort the flow.
        User.objects.create_user(username="victim", email="victim@example.com")
        sociallogin = self._sociallogin(email="victim@example.com", verified=False)
        sociallogin.email_addresses = []

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, sociallogin)

        sociallogin.connect.assert_not_called()

    def test_verified_email_is_linked(self):
        existing = User.objects.create_user(username="real", email="real@example.com")
        mark_email_verified(existing)  # it proved its email (todo 446)
        sociallogin = self._sociallogin(email="real@example.com", verified=True)

        self.adapter.pre_social_login(self.request, sociallogin)

        sociallogin.connect.assert_called_once_with(self.request, existing)


_PROVIDER_SETTINGS = {
    "APP": {
        "client_id": "test-client-id",
        "secret": "test-secret",  # pragma: allowlist secret
    },
    "SCOPE": ["email"],
}
_GOOGLE_PROFILE = {
    "id": "g-new-1",
    "email": "newbie@example.com",
    "verified_email": True,
    "given_name": "New",
    "family_name": "Bie",
}
_GITHUB_PROFILE = {
    "id": 4242,
    "email": "octo@example.com",
    "name": "Octo Cat",
}


class WebOAuthConsentTest(TestCase):
    """Web OAuth sign-up waits for consent (Plan A task 4).

    A new account is created only when the sign-up page started the flow with
    ``?accepted_terms=1``, or when the user finishes on ``/signup/finish``.
    An existing account signs in without the flag and is never stamped.
    """

    def setUp(self):
        cache.clear()  # the oauth views are IP-keyed and rate limited

    def _seed_state(self, **extra):
        session = self.client.session
        session["oauth_state"] = "test-state"
        for key, value in extra.items():
            session[key] = value
        session.save()

    def _callback(self, provider="google", profile=None):
        handler = f"_handle_{provider}_callback"
        profile = dict(
            profile or (_GOOGLE_PROFILE if provider == "google" else _GITHUB_PROFILE)
        )
        with patch.object(oauth_views, handler, return_value=profile):
            return self.client.get(
                reverse("v1:users:oauth_callback", kwargs={"provider": provider}),
                {"code": "abc", "state": "test-state"},
            )

    def _seed_pending(self, *, age_seconds=0, profile=None):
        session = self.client.session
        session["oauth_pending_signup"] = {
            "provider": "google",
            "user_data": dict(profile or _GOOGLE_PROFILE),
            "created_at": int(time.time()) - age_seconds,
        }
        session.save()

    def _finish(self, body):
        return self.client.post(
            reverse("v1:users:oauth_finish_signup"),
            body,
            content_type="application/json",
        )

    def test_callback_new_user_without_consent_redirects_to_finish(self):
        self._seed_state()
        key_before = self.client.session.session_key

        response = self._callback()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("/signup/finish"))
        self.assertFalse(User.objects.filter(email="newbie@example.com").exists())
        pending = self.client.session["oauth_pending_signup"]
        self.assertEqual(pending["provider"], "google")
        self.assertEqual(pending["user_data"]["email"], "newbie@example.com")
        # The pending entry never lives under the pre-OAuth session key.
        self.assertNotEqual(self.client.session.session_key, key_before)

    def test_login_with_accepted_terms_then_callback_creates_user(self):
        with patch.object(
            oauth_views, "_provider_settings", return_value=_PROVIDER_SETTINGS
        ):
            login = self.client.get(
                reverse("v1:users:oauth_login", kwargs={"provider": "google"}),
                {"accepted_terms": "1"},
            )
        self.assertEqual(login.status_code, 200)
        self.assertIs(self.client.session["oauth_accepted_terms"], True)
        session = self.client.session
        session["oauth_state"] = "test-state"
        session.save()

        response = self._callback()

        self.assertEqual(response.status_code, 302)
        self.assertIn("success=true", response["Location"])
        user = User.objects.get(email="newbie@example.com")
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)
        self.assertIsNotNone(user.policy_accepted_at)
        self.assertNotIn("oauth_accepted_terms", self.client.session)

    def test_login_without_accepted_terms_clears_a_stale_flag(self):
        session = self.client.session
        session["oauth_accepted_terms"] = True
        session.save()
        with patch.object(
            oauth_views, "_provider_settings", return_value=_PROVIDER_SETTINGS
        ):
            self.client.get(
                reverse("v1:users:oauth_login", kwargs={"provider": "google"}),
                {"accepted_terms": "true"},  # only the exact "1" counts
            )

        self.assertNotIn("oauth_accepted_terms", self.client.session)

    def test_callback_existing_user_logs_in_without_consent(self):
        existing = User.objects.create_user(
            username="old_hand", email="newbie@example.com"
        )
        mark_email_verified(existing)
        self._seed_state()

        response = self._callback()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].endswith("/auth/google/callback?success=true")
        )
        self.assertIn("access_token", response.cookies)
        existing.refresh_from_db()
        self.assertIsNone(existing.policy_version_accepted)
        self.assertIsNone(existing.policy_accepted_at)
        self.assertNotIn("oauth_pending_signup", self.client.session)

    def test_finish_with_flag_creates_user_and_sets_cookies(self):
        self._seed_pending()

        response = self._finish({"accepted_terms": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        user = User.objects.get(email="newbie@example.com")
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)
        self.assertIsNotNone(user.policy_accepted_at)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertNotIn("oauth_pending_signup", self.client.session)

    def test_finish_without_flag_428_keeps_pending(self):
        self._seed_pending()

        for body in ({}, {"accepted_terms": "true"}, {"accepted_terms": 1}):
            response = self._finish(body)
            self.assertEqual(response.status_code, 428, body)
            self.assertEqual(response.json()["code"], "consent_required")

        self.assertFalse(User.objects.filter(email="newbie@example.com").exists())
        self.assertIn("oauth_pending_signup", self.client.session)

    def test_finish_expired_pending_refused(self):
        self._seed_pending(age_seconds=901)

        response = self._finish({"accepted_terms": True})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "error": "Your sign-up expired. Please sign in again.",
                "code": "signup_expired",
            },
        )
        self.assertFalse(User.objects.filter(email="newbie@example.com").exists())
        self.assertNotIn("oauth_pending_signup", self.client.session)

    def test_finish_without_csrf_token_is_refused_and_consumes_nothing(self):
        client = APIClient(enforce_csrf_checks=True)
        session = client.session
        session["oauth_pending_signup"] = {
            "provider": "google",
            "user_data": dict(_GOOGLE_PROFILE),
            "created_at": int(time.time()),
        }
        session.save()

        response = client.post(
            reverse("v1:users:oauth_finish_signup"),
            {"accepted_terms": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="newbie@example.com").exists())
        self.assertIn("oauth_pending_signup", client.session)

    def test_finish_with_csrf_token_succeeds(self):
        # Positive control for the 403 above: the same client with the token.
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        session = client.session
        session["oauth_pending_signup"] = {
            "provider": "google",
            "user_data": dict(_GOOGLE_PROFILE),
            "created_at": int(time.time()),
        }
        session.save()

        response = client.post(
            reverse("v1:users:oauth_finish_signup"),
            {"accepted_terms": True},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email="newbie@example.com").exists())

    def test_oauth_login_drops_a_parked_signup(self):
        for provider, query in (("google", {}), ("github", {"accepted_terms": "1"})):
            self._seed_pending()
            with patch.object(
                oauth_views, "_provider_settings", return_value=_PROVIDER_SETTINGS
            ):
                self.client.get(
                    reverse("v1:users:oauth_login", kwargs={"provider": provider}),
                    query,
                )

            self.assertNotIn("oauth_pending_signup", self.client.session, provider)

    def test_finish_without_pending_refused(self):
        response = self._finish({"accepted_terms": True})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "signup_expired")

    def test_pending_signup_stores_no_provider_tokens(self):
        self._seed_state()
        profile = {**_GOOGLE_PROFILE, "access_token": "leak", "picture": "x"}

        self._callback(profile=profile)

        stored = self.client.session["oauth_pending_signup"]["user_data"]
        self.assertNotIn("access_token", stored)
        self.assertNotIn("picture", stored)

    def test_github_callback_new_user_also_gated(self):
        self._seed_state()

        response = self._callback(provider="github")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("/signup/finish"))
        self.assertFalse(User.objects.filter(email="octo@example.com").exists())
        self.assertEqual(
            self.client.session["oauth_pending_signup"]["provider"], "github"
        )
