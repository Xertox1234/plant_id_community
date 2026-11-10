"""A password is stored exactly as typed (audit 2026-11-10, H6).

DRF's CharField trims by default and login reads the body as sent, so a
password with a leading or trailing space was stored trimmed and then refused
at login.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD = "  Correct Horse Battery 1!  "


class PasswordWhitespaceTests(TestCase):
    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.addCleanup(cache.clear)

    def test_a_password_with_outer_spaces_registers_and_logs_in(self):
        registered = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "spacey",
                "email": "spacey@example.com",
                "password": PASSWORD,
                "confirmPassword": PASSWORD,
                "accepted_terms": True,
            },
            format="json",
        )
        self.assertEqual(registered.status_code, 201, registered.content)
        self.assertTrue(User.objects.get(username="spacey").check_password(PASSWORD))

        login = APIClient().post(
            "/api/v1/auth/login/",
            {"email": "spacey@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.content)
