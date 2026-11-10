"""Login answers malformed input with a 4xx, never a 500 (audit 2026-11-10, L2).

A 500 is noise in the error tracker, and for an email held by two legacy
accounts it was also an oracle: that address answered differently from every
other one.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()

LOGIN_URL = "/api/v1/auth/login/"
PASSWORD = "CorrectHorseBattery1!"  # pragma: allowlist secret


class LoginMalformedInputTests(TestCase):
    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.addCleanup(cache.clear)

    def post(self, body):
        return self.client.post(LOGIN_URL, body, format="json")

    def test_a_list_body_is_a_400(self):
        response = self.post(["username", "password"])
        self.assertEqual(response.status_code, 400)

    def test_a_non_string_username_is_a_400(self):
        for username in ({"$ne": ""}, ["a"], 7):
            with self.subTest(username=username):
                response = self.post({"username": username, "password": PASSWORD})
                self.assertEqual(response.status_code, 400)

    def test_a_non_string_password_is_a_400(self):
        User.objects.create_user("owner", "owner@example.com", PASSWORD)
        for password in ({"a": 1}, ["a"], 7):
            with self.subTest(password=password):
                response = self.post({"username": "owner", "password": password})
                self.assertEqual(response.status_code, 400)

    def test_an_email_on_two_accounts_is_an_ordinary_refusal(self):
        # Email is not unique in the database; legacy rows can share one.
        User.objects.create_user("first", "shared@example.com", PASSWORD)
        User.objects.create_user("second", "shared@example.com", PASSWORD)
        shared = self.post({"email": "shared@example.com", "password": PASSWORD})
        unknown = self.post({"email": "nobody@example.com", "password": PASSWORD})
        self.assertEqual(shared.status_code, 401)
        self.assertEqual(shared.json(), unknown.json())
