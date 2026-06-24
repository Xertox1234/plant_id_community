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

from unittest.mock import MagicMock, patch

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from apps.users import oauth_views
from apps.users.oauth_adapters import CustomSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase

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

        result = oauth_views._find_or_create_user(
            "google", {"email": "real@example.com"}
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
        sociallogin = self._sociallogin(email="real@example.com", verified=True)

        self.adapter.pre_social_login(self.request, sociallogin)

        sociallogin.connect.assert_called_once_with(self.request, existing)
