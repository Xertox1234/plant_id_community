"""Web OAuth: PKCE and a fixed redirect_uri (todo 705 L6, audit 2026-11-10).

* The authorisation URL carries an S256 code challenge; the code exchange
  sends the verifier kept in the session.
* redirect_uri comes from OAUTH_CALLBACK_ORIGIN (API_PUBLIC_URL), never from
  the request's Host header; with none configured OAuth refuses to start.
"""

import base64
import hashlib
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from apps.users import oauth_views
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

_PROVIDER_SETTINGS = {
    "APP": {
        "client_id": "client-id",
        "secret": "client-secret",  # pragma: allowlist secret
    },
    "SCOPE": ["email", "profile"],
}
ORIGIN = "https://api.example.test"


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


@override_settings(DEBUG=False, OAUTH_CALLBACK_ORIGIN=ORIGIN, ALLOWED_HOSTS=["*"])
class OAuthLoginPkceTest(TestCase):
    def setUp(self):
        cache.clear()

    def _login(self, provider, **extra):
        with patch.object(
            oauth_views, "_provider_settings", return_value=_PROVIDER_SETTINGS
        ):
            return self.client.get(
                reverse("v1:users:oauth_login", kwargs={"provider": provider}), **extra
            )

    def test_the_authorisation_url_carries_an_s256_challenge(self):
        for provider in sorted(oauth_views.SUPPORTED_PROVIDERS):
            with self.subTest(provider=provider):
                cache.clear()
                response = self._login(provider)
                self.assertEqual(response.status_code, 200)
                query = _query(response.json()["oauth_url"])
                verifier = self.client.session[oauth_views.OAUTH_PKCE_VERIFIER_KEY]
                self.assertGreaterEqual(len(verifier), 43)
                expected = (
                    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                    .rstrip(b"=")
                    .decode()
                )
                self.assertEqual(query["code_challenge"], expected)
                self.assertEqual(query["code_challenge_method"], "S256")

    def test_redirect_uri_ignores_the_host_header(self):
        response = self._login("google", HTTP_HOST="attacker.example")
        query = _query(response.json()["oauth_url"])
        self.assertEqual(
            query["redirect_uri"], f"{ORIGIN}/api/auth/oauth/google/callback/"
        )

    @override_settings(OAUTH_CALLBACK_ORIGIN="")
    def test_no_configured_origin_refuses_to_start(self):
        response = self._login("google")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(oauth_views.OAUTH_PKCE_VERIFIER_KEY, self.client.session)


@override_settings(DEBUG=False, OAUTH_CALLBACK_ORIGIN=ORIGIN)
class OAuthCodeExchangePkceTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get(
            "/api/auth/oauth/google/callback/", HTTP_HOST="attacker.example"
        )

    def _token_reply(self):
        reply = MagicMock()
        reply.json.return_value = {"error": "stop-here"}
        return reply

    def test_google_exchange_sends_the_verifier_and_the_fixed_uri(self):
        with patch.object(
            oauth_views, "_provider_settings", return_value=_PROVIDER_SETTINGS
        ), patch("requests.post", return_value=self._token_reply()) as post:
            oauth_views._handle_google_callback(self.request, "code", "the-verifier")
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["code_verifier"], "the-verifier")
        self.assertEqual(
            sent["redirect_uri"], f"{ORIGIN}/api/auth/oauth/google/callback/"
        )

    def test_github_exchange_sends_the_verifier_and_the_fixed_uri(self):
        with patch.object(
            oauth_views, "_provider_settings", return_value=_PROVIDER_SETTINGS
        ), patch("requests.post", return_value=self._token_reply()) as post:
            oauth_views._handle_github_callback(self.request, "code", "the-verifier")
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["code_verifier"], "the-verifier")
        self.assertEqual(
            sent["redirect_uri"], f"{ORIGIN}/api/auth/oauth/github/callback/"
        )


class OAuthCallbackPassesTheVerifierTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_callback_hands_the_session_verifier_to_the_exchange_once(self):
        session = self.client.session
        session["oauth_state"] = "test-state"
        session[oauth_views.OAUTH_PKCE_VERIFIER_KEY] = "kept-verifier"
        session.save()
        with patch.object(
            oauth_views, "_handle_google_callback", return_value=None
        ) as handler:
            self.client.get(
                reverse("v1:users:oauth_callback", kwargs={"provider": "google"}),
                {"code": "abc", "state": "test-state"},
            )
        self.assertEqual(handler.call_args.args[2], "kept-verifier")
        self.assertNotIn(oauth_views.OAUTH_PKCE_VERIFIER_KEY, self.client.session)
