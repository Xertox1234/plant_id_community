"""Firebase exchange hardening (todo 705 M6, audit 2026-11-10).

The exchange refuses a token whose sign-in provider the apps do not offer, and
a disabled (banned) account, with 401: the app reads 401 as signed out.
"""

from unittest.mock import patch

from apps.users.constants import (
    ACCOUNT_DISABLED_CODE,
    FIREBASE_ALLOWED_SIGN_IN_PROVIDERS,
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

User = get_user_model()

VERIFY = "apps.users.firebase_auth_views.firebase_auth.verify_id_token"


def _decoded(provider, uid="uid-m6", email="m6@example.com"):
    token = {"uid": uid, "email": email, "email_verified": True}
    if provider is not None:
        token["firebase"] = {"sign_in_provider": provider}
    return token


class SignInProviderAllowlistTest(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:users:firebase_token_exchange")

    def _exchange(self):
        return self.client.post(
            self.url,
            {"firebase_token": "fake-token", "accepted_terms": True},
            format="json",
        )

    def test_the_allowlist_is_the_providers_the_apps_offer(self):
        self.assertEqual(
            FIREBASE_ALLOWED_SIGN_IN_PROVIDERS,
            frozenset({"password", "google.com", "apple.com"}),
        )

    def test_a_provider_outside_the_allowlist_gets_401_and_no_account(self):
        for provider in ("anonymous", "phone", "custom", "github.com", "", None):
            with self.subTest(provider=provider):
                cache.clear()
                with patch(VERIFY, return_value=_decoded(provider)):
                    response = self._exchange()
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertNotIn("access_token", response.data)
                self.assertFalse(User.objects.filter(firebase_uid="uid-m6").exists())

    def test_a_non_object_firebase_claim_gets_401(self):
        decoded = _decoded("password")
        decoded["firebase"] = "password"
        with patch(VERIFY, return_value=decoded):
            response = self._exchange()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_each_allowed_provider_signs_in(self):
        for i, provider in enumerate(sorted(FIREBASE_ALLOWED_SIGN_IN_PROVIDERS)):
            with self.subTest(provider=provider):
                cache.clear()
                decoded = _decoded(
                    provider, uid=f"uid-ok-{i}", email=f"ok{i}@example.com"
                )
                with patch(VERIFY, return_value=decoded):
                    response = self._exchange()
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("refresh_token", response.data)


class InactiveUserExchangeTest(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:users:firebase_token_exchange")
        self.user = User.objects.create_user(
            username="banned",
            email="banned@example.com",
            password="unused-Pa55word!",  # pragma: allowlist secret
            firebase_uid="uid-banned",
            is_active=False,
        )

    def test_an_inactive_user_gets_401_and_no_tokens(self):
        decoded = _decoded("password", uid="uid-banned", email="banned@example.com")
        with patch(VERIFY, return_value=decoded):
            response = self.client.post(
                self.url, {"firebase_token": "fake-token"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], ACCOUNT_DISABLED_CODE)
        self.assertNotIn("access_token", response.data)
        self.assertNotIn("refresh_token", response.data)
        self.assertFalse(OutstandingToken.objects.filter(user=self.user).exists())

    def test_the_same_user_active_signs_in(self):
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        decoded = _decoded("password", uid="uid-banned", email="banned@example.com")
        with patch(VERIFY, return_value=decoded):
            response = self.client.post(
                self.url, {"firebase_token": "fake-token"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
