"""The two-tab refresh race (todo 706, audit 2026-11-10 M18), against the real view.

Every tab of the web app shares one cookie jar and runs its own 10-minute
refresh timer. The refresh endpoint rotates the refresh token and blacklists
the one it was given (ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION). So
when two tabs' refreshes overlap, both requests carry the same refresh cookie:
the first rotates it, the second presents a blacklisted token and gets 401, and
the web client logged that tab out of a session that was still good.

The interleave is forced here: tab B's request is sent with the cookie the jar
held BEFORE tab A's response landed. The web fix (one refresh at a time across
tabs, `refreshSession()` in web/src/services/authService.ts) makes B wait for
A's response, so B sends the rotated cookie, which the last test shows works.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD = "TestPassword123!"  # pragma: allowlist secret - test fixture

REFRESH_URL = "/api/v1/auth/token/refresh/"


class RefreshRotationRaceTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        User.objects.create_user(
            username="racer", email="racer@example.com", password=PASSWORD
        )
        csrf = self.client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        login = self.client.post(
            "/api/v1/auth/login/",
            data={"username": "racer", "password": PASSWORD},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.csrf = self.client.cookies["csrftoken"].value

    def _refresh(self):
        return self.client.post(REFRESH_URL, HTTP_X_CSRFTOKEN=self.csrf)

    def test_overlapping_refresh_with_the_same_cookie_is_refused(self):
        sent_by_both_tabs = self.client.cookies["refresh_token"].value

        tab_a = self._refresh()
        self.assertEqual(tab_a.status_code, status.HTTP_200_OK)
        rotated = self.client.cookies["refresh_token"].value
        self.assertNotEqual(rotated, sent_by_both_tabs)

        # Tab B's request left before tab A's response landed: old cookie.
        self.client.cookies["refresh_token"] = sent_by_both_tabs
        tab_b = self._refresh()

        # The race is real: a still-valid session is refused, and the web
        # client logged out on any non-2xx refresh.
        self.assertEqual(tab_b.status_code, status.HTTP_401_UNAUTHORIZED)
        # The refusal does not clear the cookies tab A was just given, so the
        # session itself survives; only the losing tab's state was wrong.
        self.assertNotIn("refresh_token", tab_b.cookies)

        self.client.cookies["refresh_token"] = rotated
        self.assertEqual(self._refresh().status_code, status.HTTP_200_OK)

    def test_serialized_refreshes_both_succeed(self):
        # With the web lock, tab B sends only after tab A's response set the
        # rotated cookie in the shared jar.
        self.assertEqual(self._refresh().status_code, status.HTTP_200_OK)
        self.assertEqual(self._refresh().status_code, status.HTTP_200_OK)
