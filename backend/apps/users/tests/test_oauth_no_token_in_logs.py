"""The provider's access token and reply bodies stay out of our logs (audit
2026-11-10, L1).

The Google token used to ride in the userinfo URL. ``requests`` puts the URL in
its exception text, and the handler logged that text, so one timeout wrote a
live token to the log.
"""

from unittest.mock import MagicMock, patch

import requests
from apps.users import oauth_views
from django.test import RequestFactory, TestCase

TOKEN = "ya29.secret-access-token"
EMAIL = "victim@example.com"


def _response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


class GoogleCallbackLoggingTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/api/auth/oauth/google/callback/")

    def run_callback(self):
        with self.assertLogs("apps.users.oauth_views", level="ERROR") as logs:
            profile = oauth_views._handle_google_callback(self.request, code="abc")
        return profile, "\n".join(logs.output)

    @patch("requests.get")
    @patch("requests.post")
    def test_token_goes_in_a_header_not_the_url(self, mock_post, mock_get):
        mock_post.return_value = _response(200, {"access_token": TOKEN})
        mock_get.return_value = _response(200, {"email": EMAIL, "verified_email": True})

        oauth_views._handle_google_callback(self.request, code="abc")

        args, kwargs = mock_get.call_args
        self.assertNotIn(TOKEN, args[0])
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {TOKEN}")

    @patch("requests.get")
    @patch("requests.post")
    def test_a_failed_profile_fetch_logs_no_token(self, mock_post, mock_get):
        mock_post.return_value = _response(200, {"access_token": TOKEN})

        def raise_with_the_url(url, **kwargs):
            # What requests does: the message carries the URL it was given.
            raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

        mock_get.side_effect = raise_with_the_url

        profile, logged = self.run_callback()

        self.assertIsNone(profile)
        self.assertNotIn(TOKEN, logged)

    @patch("requests.get")
    @patch("requests.post")
    def test_a_refused_profile_fetch_logs_no_body(self, mock_post, mock_get):
        mock_post.return_value = _response(200, {"access_token": TOKEN})
        mock_get.return_value = _response(403, text=f'{{"email": "{EMAIL}"}}')

        profile, logged = self.run_callback()

        self.assertIsNone(profile)
        self.assertNotIn(EMAIL, logged)
        self.assertIn("403", logged)

    @patch("requests.post")
    def test_a_failed_exchange_logs_only_the_error_code(self, mock_post):
        mock_post.return_value = _response(
            400, {"error": "invalid_grant", "id_token": "eyJ.private.claims"}
        )

        profile, logged = self.run_callback()

        self.assertIsNone(profile)
        self.assertIn("invalid_grant", logged)
        self.assertNotIn("eyJ.private.claims", logged)


class GitHubCallbackLoggingTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/api/auth/oauth/github/callback/")

    @patch("requests.get")
    @patch("requests.post")
    def test_a_refused_profile_fetch_logs_no_body(self, mock_post, mock_get):
        mock_post.return_value = _response(200, {"access_token": TOKEN})
        mock_get.return_value = _response(403, text=f'{{"email": "{EMAIL}"}}')

        with self.assertLogs("apps.users.oauth_views", level="ERROR") as logs:
            profile = oauth_views._handle_github_callback(self.request, code="abc")

        logged = "\n".join(logs.output)
        self.assertIsNone(profile)
        self.assertNotIn(EMAIL, logged)
        self.assertIn("403", logged)
