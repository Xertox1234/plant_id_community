"""Session sign-ins also wait for the current policy version (todo 701).

The token paths are covered by ``test_policy_reconsent.py``. These are the
Django-session paths with no consent box: the API's session authentication,
the ``/cms/`` and ``/admin/`` sign-in forms, and allauth's ``/accounts/login/``.
Each refuses an account on an older version and lets a current one through.
"""

from apps.users.constants import (
    LEGAL_POLICY_VERSION,
    POLICY_UPDATED_SIGN_IN_ON_WEBSITE_MESSAGE,
)
from apps.users.email_verification import mark_email_verified
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD = "TestPassword123!"  # pragma: allowlist secret
OLD_VERSION = "2026-11-06"


def _staff(username, version):
    user = User.objects.create_superuser(
        username=username, email=f"{username}@example.com", password=PASSWORD
    )
    User.objects.filter(pk=user.pk).update(policy_version_accepted=version)
    user.refresh_from_db()
    return user


def _signed_in(client):
    return "_auth_user_id" in client.session


class ApiSessionTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:users:current_user")

    def test_a_session_on_an_older_version_is_treated_as_signed_out(self):
        self.client.force_login(_staff("old", OLD_VERSION))

        response = self.client.get(self.url)

        self.assertIn(response.status_code, (401, 403))

    def test_a_session_on_the_current_version_is_honoured(self):
        self.client.force_login(_staff("current", LEGAL_POLICY_VERSION))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_the_login_that_carries_the_acceptance_is_not_refused(self):
        # A stale session must not block the very request that accepts.
        user = _staff("relog", OLD_VERSION)
        self.client.force_login(user)

        response = self.client.post(
            reverse("v1:users:login"),
            {"email": user.email, "password": PASSWORD, "accepted_terms": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.policy_version_accepted, LEGAL_POLICY_VERSION)


class DjangoLoginFormTests(TestCase):
    def setUp(self):
        cache.clear()

    def _post(self, url, username):
        return self.client.post(url, {"username": username, "password": PASSWORD})

    def test_cms_refuses_an_older_version(self):
        _staff("cmsold", OLD_VERSION)

        response = self._post(reverse("wagtailadmin_login"), "cmsold")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in on the website once")
        self.assertFalse(_signed_in(self.client))

    def test_cms_lets_the_current_version_in(self):
        _staff("cmsnew", LEGAL_POLICY_VERSION)

        response = self._post(reverse("wagtailadmin_login"), "cmsnew")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(_signed_in(self.client))

    def test_admin_refuses_an_older_version(self):
        _staff("admold", OLD_VERSION)

        response = self._post(reverse("admin:login"), "admold")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in on the website once")
        self.assertFalse(_signed_in(self.client))

    def test_admin_lets_the_current_version_in(self):
        _staff("admnew", LEGAL_POLICY_VERSION)

        response = self._post(reverse("admin:login"), "admnew")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(_signed_in(self.client))


@override_settings(FRONTEND_BASE_URL="https://web.example")
class AllauthLoginTests(TestCase):
    def setUp(self):
        cache.clear()

    def _post(self, user):
        mark_email_verified(user)
        return self.client.post(
            reverse("account_login"), {"login": user.email, "password": PASSWORD}
        )

    def test_an_older_version_is_sent_to_the_website(self):
        response = self._post(_staff("aaold", OLD_VERSION))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], "https://web.example/login?reason=policy_updated"
        )
        self.assertFalse(_signed_in(self.client))

    def test_the_current_version_signs_in(self):
        self._post(_staff("aanew", LEGAL_POLICY_VERSION))

        self.assertTrue(_signed_in(self.client))


class MessageTests(TestCase):
    def test_the_form_message_names_the_website(self):
        self.assertIn("website", POLICY_UPDATED_SIGN_IN_ON_WEBSITE_MESSAGE)
