"""allauth's mounted ``/accounts/`` views, driven over HTTP (todo 447).

The web and mobile clients use the custom ``/api/v1/auth/`` endpoints, but
allauth's views stay mounted: its password reset is the only way the owner of a
squatted address can take it back. These tests pin what those views can and
cannot do to the email-verification closure from todo 446.
"""

import re
from unittest.mock import MagicMock
from urllib.parse import urlparse

from allauth.account import app_settings as allauth_settings
from allauth.account.models import EmailAddress
from allauth.account.signals import password_changed, password_set
from apps.users.email_verification import (
    VERIFY_SALT,
    is_email_verified,
    mark_email_verified,
)
from apps.users.oauth_adapters import CustomSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

PASSWORD = "TestPassword123!"  # pragma: allowlist secret
NEW_PASSWORD = "Another-Passw0rd-99"  # pragma: allowlist secret


class AllauthSettingsGuardTest(TestCase):
    """The key-alone-cannot-verify closure holds only while these stay put.
    Each one, changed, opens a way to verify or sign in without both halves
    (the inbox key AND a session for the key's account)."""

    def test_no_code_based_flows(self):
        # A code is a key without our salt or our session check.
        self.assertFalse(allauth_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED)
        self.assertFalse(allauth_settings.LOGIN_BY_CODE_ENABLED)
        self.assertFalse(allauth_settings.PASSWORD_RESET_BY_CODE_ENABLED)

    def test_allauth_keys_cannot_carry_ours(self):
        # Our keys are rejected by /accounts/confirm-email/ only because the
        # salts differ and allauth uses HMAC keys.
        self.assertNotEqual(allauth_settings.SALT, VERIFY_SALT)
        self.assertTrue(allauth_settings.EMAIL_CONFIRMATION_HMAC)
        self.assertFalse(allauth_settings.CONFIRM_EMAIL_ON_GET)

    def test_unverified_accounts_get_no_allauth_session(self):
        # MANDATORY is what stops allauth's login (and a reset) from giving an
        # unverified account a session, which /accounts/email/ would accept.
        self.assertEqual(allauth_settings.EMAIL_VERIFICATION, "mandatory")
        self.assertFalse(allauth_settings.LOGIN_ON_PASSWORD_RESET)
        self.assertFalse(allauth_settings.CHANGE_EMAIL)

    def test_headless_is_not_installed(self):
        # allauth.headless exposes its own verify/login endpoints.
        self.assertNotIn("allauth.headless", settings.INSTALLED_APPS)


class AllauthSignupClosedTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_accounts_signup_creates_nobody(self):
        response = Client().post(
            "/accounts/signup/",
            {
                "email": "side@example.com",
                "username": "sidedoor",
                "password1": NEW_PASSWORD,
                "password2": NEW_PASSWORD,
            },
        )

        self.assertFalse(User.objects.filter(username="sidedoor").exists())
        self.assertNotEqual(response.status_code, 302)

    def test_social_signup_is_unchanged(self):
        # allauth's social default defers to the (now closed) account adapter.
        request = RequestFactory().get("/accounts/google/login/callback/")

        self.assertTrue(
            CustomSocialAccountAdapter().is_open_for_signup(request, MagicMock())
        )


def _register(test, client, username, email):
    csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
    with test.captureOnCommitCallbacks(execute=True):
        response = client.post(
            "/api/v1/auth/register/",
            data={
                "username": username,
                "email": email,
                "password": PASSWORD,
                "confirmPassword": PASSWORD,
            },
            HTTP_X_CSRFTOKEN=csrf,
        )
    test.assertEqual(response.status_code, 201)
    return response.cookies["refresh_token"].value


def _refresh_status(refresh_token):
    client = Client()
    csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
    client.cookies["refresh_token"] = refresh_token
    return client.post("/api/v1/auth/token/refresh/", HTTP_X_CSRFTOKEN=csrf).status_code


class PasswordResetRevokesRefreshTokensTest(TestCase):
    """Finding 13, reproduced before the fix: the squatter's refresh token
    outlived the owner's reset and refreshed into the verified account."""

    def setUp(self):
        cache.clear()

    def test_reset_revokes_the_squatters_refresh_token(self):
        squatter_refresh = _register(self, Client(), "squatter", "owner@example.com")
        mail.outbox.clear()

        owner = Client()
        owner.post("/accounts/password/reset/", {"email": "owner@example.com"})
        link = re.search(
            r"https?://\S+/accounts/password/reset/key/\S+", mail.outbox[-1].body
        )
        response = owner.get(urlparse(link.group(0)).path, follow=True)
        owner.post(
            response.redirect_chain[-1][0],
            {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        self.assertTrue(
            User.objects.get(username="squatter").check_password(NEW_PASSWORD)
        )
        self.assertEqual(_refresh_status(squatter_refresh), 401)

    def test_change_and_set_revoke_every_refresh_token(self):
        user = User.objects.create_user("someone", "someone@example.com", PASSWORD)
        for signal in (password_changed, password_set):
            with self.subTest(signal=signal):
                tokens = [str(RefreshToken.for_user(user)) for _ in range(2)]

                signal.send(sender=User, request=None, user=user)

                for token in tokens:
                    self.assertEqual(_refresh_status(token), 401)
        self.assertEqual(
            OutstandingToken.objects.filter(
                user=user, blacklistedtoken__isnull=True
            ).count(),
            0,
        )


class AllauthEmailManagementTest(TestCase):
    """Finding 6: ``/accounts/email/`` could change ``User.email``, around
    todo 404's read-only profile field, by adding an address and making it
    primary. Driven over HTTP, it cannot."""

    def setUp(self):
        cache.clear()

    def test_verified_account_cannot_move_its_email(self):
        user = User.objects.create_user("owner", "owner@example.com", PASSWORD)
        mark_email_verified(user)
        client = Client()
        client.post("/accounts/login/", {"login": "owner", "password": PASSWORD})
        mail.outbox.clear()

        client.post(
            "/accounts/email/", {"email": "other@example.com", "action_add": ""}
        )
        client.post(
            "/accounts/email/", {"email": "other@example.com", "action_primary": ""}
        )

        user.refresh_from_db()
        self.assertEqual(user.email, "owner@example.com")
        # allauth refuses a primary move onto an unverified address, and nothing
        # can verify a secondary one: our mail only confirms the CURRENT email
        # (finding 14). That is what keeps this closed.
        self.assertFalse(
            EmailAddress.objects.get(user=user, email="other@example.com").verified
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(is_email_verified(user))

    def test_unverified_account_gets_no_session_to_manage_email(self):
        _register(self, Client(), "fresh", "fresh@example.com")
        client = Client()

        client.post("/accounts/login/", {"login": "fresh", "password": PASSWORD})
        response = client.get("/accounts/email/")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))
