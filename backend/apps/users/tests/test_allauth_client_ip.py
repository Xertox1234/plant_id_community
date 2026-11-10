"""allauth's own rate limits count the real client (audit 2026-11-10, M3).

``/accounts/login/`` is a password login outside ``views.login``. allauth
throttled it per ``REMOTE_ADDR``, which behind the proxy is a different
internal address on every request, so its per-IP limits never added up.
"""

from allauth.account.adapter import get_adapter
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings

User = get_user_model()

CLIENT_IP = "203.0.113.7"


@override_settings(RATELIMIT_CLIENT_IP_META_KEY="HTTP_X_REAL_IP")
class AllauthClientIpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_adapter_resolves_the_client_like_our_rate_limiter(self):
        request = RequestFactory().post(
            "/accounts/login/", REMOTE_ADDR="100.64.0.9", HTTP_X_REAL_IP=CLIENT_IP
        )
        self.assertEqual(get_adapter().get_client_ip(request), CLIENT_IP)

    def test_failed_logins_from_one_client_are_throttled_across_proxies(self):
        # allauth's default is 10 failed logins a minute per IP. Every request
        # arrives from a new proxy address and tries a new username, so only
        # the real client address ties them together.
        client = Client()

        def error_codes(n):
            response = client.post(
                "/accounts/login/",
                {
                    "login": f"nobody{n}",
                    "password": "wrong-password-1",  # pragma: allowlist secret
                },
                REMOTE_ADDR=f"100.64.0.{n + 1}",
                HTTP_X_REAL_IP=CLIENT_IP,
            )
            errors = response.context["form"].errors.as_data()
            return {error.code for found in errors.values() for error in found}

        codes = [error_codes(n) for n in range(12)]
        self.assertNotIn("too_many_login_attempts", codes[0])
        self.assertIn("too_many_login_attempts", codes[-1])


class AllauthClientIpFallbackTests(TestCase):
    def test_without_a_trusted_header_it_is_the_socket_address(self):
        request = RequestFactory().post("/accounts/login/", REMOTE_ADDR="198.51.100.4")
        self.assertEqual(get_adapter().get_client_ip(request), "198.51.100.4")
