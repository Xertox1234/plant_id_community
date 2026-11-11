"""An account that has not accepted the current policy version is asked again.

Every path that issues tokens refuses with 428 ``policy_update_required`` until the
request carries ``accepted_terms: true``, which stamps the current version
(todo 701). An account on the current version is never asked.
"""

import time
from unittest.mock import patch

from apps.users import oauth_views
from apps.users.consent import needs_policy_acceptance, record_policy_acceptance
from apps.users.constants import (
    CONSENT_REQUIRED_CODE,
    LEGAL_POLICY_VERSION,
    POLICY_UPDATE_REQUIRED_CODE,
)
from apps.users.email_verification import mark_email_verified
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

PASSWORD = "TestPassword123!"  # pragma: allowlist secret
OLD_VERSION = "2026-11-06"


def _user(username="member", version=OLD_VERSION, **extra):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        **extra,
    )
    if version is not None:
        User.objects.filter(pk=user.pk).update(policy_version_accepted=version)
        user.refresh_from_db()
    return user


class NeedsPolicyAcceptanceTests(TestCase):
    def test_older_version_and_no_version_need_it(self):
        self.assertTrue(needs_policy_acceptance(_user("old")))
        self.assertTrue(needs_policy_acceptance(_user("never", version=None)))

    def test_current_version_does_not(self):
        self.assertFalse(needs_policy_acceptance(_user(version=LEGAL_POLICY_VERSION)))


class LoginReconsentTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:users:login")

    def _login(self, **extra):
        return self.client.post(
            self.url,
            {"username": "member", "password": PASSWORD, **extra},
            format="json",
        )

    def test_outdated_account_is_refused_and_gets_no_cookies(self):
        user = _user()

        response = self._login()

        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.data["code"], POLICY_UPDATE_REQUIRED_CODE)
        self.assertEqual(response.data["policy_version"], LEGAL_POLICY_VERSION)
        self.assertNotIn("access_token", response.cookies)
        self.assertNotIn("refresh_token", response.cookies)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, OLD_VERSION)

    def test_never_accepted_account_is_refused(self):
        _user(version=None)

        self.assertEqual(self._login().status_code, 428)

    def test_accepting_stamps_the_version_and_signs_in(self):
        user = _user()

        response = self._login(accepted_terms=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)
        self.assertIsNotNone(user.policy_accepted_at)

    def test_only_json_true_is_acceptance(self):
        _user()

        for value in ("true", 1, False):
            self.assertEqual(self._login(accepted_terms=value).status_code, 428)

    def test_current_account_signs_in_and_is_not_restamped(self):
        user = _user(version=LEGAL_POLICY_VERSION)

        response = self._login()

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertIsNone(user.policy_accepted_at)

    def test_wrong_password_never_reaches_the_consent_answer(self):
        _user()

        response = self.client.post(
            self.url,
            {
                "username": "member",
                "password": "wrong",  # pragma: allowlist secret
                "accepted_terms": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_disabled_account_is_told_disabled_not_asked(self):
        _user(is_active=False)

        self.assertEqual(self._login().status_code, 403)


class RefreshReconsentTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:users:token_refresh")

    def test_outdated_account_is_refused_and_its_token_survives(self):
        user = _user()
        token = str(RefreshToken.for_user(user))

        response = self.client.post(self.url, {"refresh": token}, format="json")

        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.data["code"], POLICY_UPDATE_REQUIRED_CODE)
        self.assertNotIn("access_token", response.cookies)
        # Not blacklisted: the same token works once the user accepts.
        accepted = self.client.post(
            self.url, {"refresh": token, "accepted_terms": True}, format="json"
        )
        self.assertEqual(accepted.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)

    def test_current_account_refreshes(self):
        user = _user(version=LEGAL_POLICY_VERSION)
        token = str(RefreshToken.for_user(user))

        response = self.client.post(self.url, {"refresh": token}, format="json")

        self.assertEqual(response.status_code, 200)


class FirebaseExchangeReconsentTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:users:firebase_token_exchange")
        self.decoded = {
            "uid": "uid-reconsent",
            "email": "member@example.com",
            "email_verified": True,
        }

    def _exchange(self, **extra):
        with patch(
            "apps.users.firebase_auth_views.firebase_auth.verify_id_token",
            return_value=self.decoded,
        ):
            return self.client.post(
                self.url, {"firebase_token": "t", **extra}, format="json"
            )

    def test_outdated_account_is_refused_with_no_tokens(self):
        user = _user(firebase_uid="uid-reconsent")

        response = self._exchange()

        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.data["code"], POLICY_UPDATE_REQUIRED_CODE)
        self.assertNotIn("access_token", response.data)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, OLD_VERSION)

    def test_accepting_stamps_the_version_and_issues_tokens(self):
        user = _user(firebase_uid="uid-reconsent")

        response = self._exchange(accepted_terms=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.data)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)

    def test_current_account_is_not_asked(self):
        _user(firebase_uid="uid-reconsent", version=LEGAL_POLICY_VERSION)

        self.assertEqual(self._exchange().status_code, 200)


class OAuthReconsentTests(TestCase):
    PROFILE = {
        "id": "g-1",
        "email": "member@example.com",
        "verified_email": True,
        "given_name": "Mem",
        "family_name": "Ber",
    }

    def setUp(self):
        cache.clear()

    def _callback(self, **session_extra):
        session = self.client.session
        session["oauth_state"] = "test-state"
        for key, value in session_extra.items():
            session[key] = value
        session.save()
        with patch.object(
            oauth_views, "_handle_google_callback", return_value=dict(self.PROFILE)
        ):
            return self.client.get(
                reverse("v1:users:oauth_callback", kwargs={"provider": "google"}),
                {"code": "abc", "state": "test-state"},
            )

    def test_outdated_account_is_parked_for_the_finish_step(self):
        user = _user()
        mark_email_verified(user)

        response = self._callback()

        self.assertEqual(response.status_code, 302)
        self.assertIn("/signup/finish", response["Location"])
        self.assertNotIn("access_token", response.cookies)
        self.assertIn("oauth_pending_signup", self.client.session)

    def test_finish_stamps_the_existing_account_and_signs_in(self):
        user = _user()
        mark_email_verified(user)
        session = self.client.session
        session["oauth_pending_signup"] = {
            "provider": "google",
            "user_data": dict(self.PROFILE),
            "created_at": int(time.time()),
        }
        session.save()

        response = self.client.post(
            reverse("v1:users:oauth_finish_signup"),
            {"accepted_terms": True},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)
        self.assertEqual(User.objects.filter(email="member@example.com").count(), 1)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)

    def test_callback_started_from_the_sign_up_page_stamps_and_signs_in(self):
        user = _user()
        mark_email_verified(user)

        response = self._callback(oauth_accepted_terms=True)

        self.assertIn("success=true", response["Location"])
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)

    def test_current_account_signs_in_directly(self):
        user = _user(version=LEGAL_POLICY_VERSION)
        mark_email_verified(user)

        response = self._callback()

        self.assertIn("success=true", response["Location"])
        self.assertIn("access_token", response.cookies)


class RefusalCodeTests(TestCase):
    def test_it_is_never_the_sign_up_code(self):
        # App builds 20 and 21 delete the Firebase login when the person
        # cancels the sheet they show for the sign-up code.
        self.assertNotEqual(POLICY_UPDATE_REQUIRED_CODE, CONSENT_REQUIRED_CODE)
        self.assertEqual(POLICY_UPDATE_REQUIRED_CODE, "policy_update_required")


class RecordAcceptanceTests(TestCase):
    def test_recording_ends_the_need(self):
        user = _user()

        record_policy_acceptance(user)

        self.assertFalse(needs_policy_acceptance(user))
