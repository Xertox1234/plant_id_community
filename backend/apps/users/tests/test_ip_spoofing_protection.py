"""
Tests for IP Spoofing Protection.

Tests SecurityMonitor IP validation and spoofing protection including:
- X-Forwarded-For read only through the trusted-proxy resolver the login rate
  limit uses (``RATELIMIT_TRUSTED_PROXY_COUNT``, todo 553 finding 2)
- IP format validation
- Handling of invalid/spoofed IPs
- Fallback to REMOTE_ADDR
"""

from apps.core.security import SecurityMonitor
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

User = get_user_model()


class IPSpoofingProtectionTestCase(TestCase):
    """Test IP spoofing protection in SecurityMonitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPassword123!"
        )

    def test_get_client_ip_from_remote_addr(self):
        """Test getting client IP from REMOTE_ADDR (most reliable)."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        ip = SecurityMonitor._get_client_ip(request)

        self.assertEqual(ip, "192.168.1.100")

    def test_x_forwarded_for_is_ignored_without_a_trusted_proxy_count(self):
        """Default settings (no proxy configured): REMOTE_ADDR is the client,
        and a header any client can send is never read."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1"

        self.assertEqual(SecurityMonitor._get_client_ip(request), "192.168.1.100")

    @override_settings(USE_X_FORWARDED_HOST=True)
    def test_use_x_forwarded_host_no_longer_selects_the_header(self):
        """Todo 553 finding 2: the old resolver read XFF only under this
        setting, which nothing set, and then trusted the rightmost entry."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 10.0.0.1"

        self.assertEqual(SecurityMonitor._get_client_ip(request), "10.0.0.1")

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_the_client_behind_two_trusted_proxies_is_resolved(self):
        """The shape the login rate limit is configured for in production:
        ``client, proxy1`` appended by two trusted hops, REMOTE_ADDR the
        last proxy."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "10.0.0.2"
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.7, 10.0.0.1"

        self.assertEqual(SecurityMonitor._get_client_ip(request), "203.0.113.7")

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_a_left_prepended_spoofed_entry_does_not_move_the_result(self):
        """A client may pre-set X-Forwarded-For. Counting hops from the right
        means whatever it prepends cannot become the resolved address."""
        for xff in (
            "198.51.100.66, 203.0.113.7, 10.0.0.1",
            "1.2.3.4, 198.51.100.66, 203.0.113.7, 10.0.0.1",
        ):
            with self.subTest(xff=xff):
                request = self.factory.get("/api/test/")
                request.META["REMOTE_ADDR"] = "10.0.0.2"
                request.META["HTTP_X_FORWARDED_FOR"] = xff

                self.assertEqual(SecurityMonitor._get_client_ip(request), "203.0.113.7")

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_two_clients_behind_the_proxy_get_separate_addresses(self):
        """The production symptom: every client shared the proxy's address,
        so one per-IP failed-login bucket for everybody."""
        ips = set()
        for client in ("203.0.113.7", "203.0.113.8"):
            request = self.factory.get("/api/test/")
            request.META["REMOTE_ADDR"] = "10.0.0.2"
            request.META["HTTP_X_FORWARDED_FOR"] = f"{client}, 10.0.0.1"
            ips.add(SecurityMonitor._get_client_ip(request))

        self.assertEqual(ips, {"203.0.113.7", "203.0.113.8"})

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_a_non_ip_in_the_trusted_position_falls_back_to_remote_addr(self):
        for xff in (
            "invalid_ip, 10.0.0.1",
            "1.2.3.4'; DROP TABLE users; --, 10.0.0.1",
            '<script>alert("xss")</script>, 10.0.0.1',
        ):
            with self.subTest(xff=xff):
                request = self.factory.get("/api/test/")
                request.META["REMOTE_ADDR"] = "192.168.1.100"
                request.META["HTTP_X_FORWARDED_FOR"] = xff

                self.assertEqual(
                    SecurityMonitor._get_client_ip(request), "192.168.1.100"
                )

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_too_few_entries_fall_back_to_remote_addr(self):
        """Fewer entries than trusted hops means an expected hop is missing:
        the header is not trusted at all."""
        for xff in ("", "203.0.113.7"):
            with self.subTest(xff=xff):
                request = self.factory.get("/api/test/")
                request.META["REMOTE_ADDR"] = "192.168.1.100"
                request.META["HTTP_X_FORWARDED_FOR"] = xff

                self.assertEqual(
                    SecurityMonitor._get_client_ip(request), "192.168.1.100"
                )

    def test_get_client_ip_ipv6_address(self):
        """Test handling of IPv6 addresses."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        ip = SecurityMonitor._get_client_ip(request)

        self.assertEqual(ip, "2001:0db8:85a3:0000:0000:8a2e:0370:7334")

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_get_client_ip_ipv6_in_x_forwarded_for(self):
        """Test IPv6 in X-Forwarded-For header."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "10.0.0.2"
        request.META["HTTP_X_FORWARDED_FOR"] = "2001:db8::1, 10.0.0.1"

        self.assertEqual(SecurityMonitor._get_client_ip(request), "2001:db8::1")

    def test_get_client_ip_missing_remote_addr(self):
        """Test handling when REMOTE_ADDR is missing."""
        request = self.factory.get("/api/test/")
        # RequestFactory sets REMOTE_ADDR='127.0.0.1' by default; explicitly remove it
        del request.META["REMOTE_ADDR"]

        ip = SecurityMonitor._get_client_ip(request)

        # Should return 'unknown'
        self.assertEqual(ip, "unknown")

    def test_get_client_ip_invalid_remote_addr(self):
        """Test handling of invalid REMOTE_ADDR."""
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "not_an_ip_address"

        ip = SecurityMonitor._get_client_ip(request)

        # Should return 'unknown' when REMOTE_ADDR is invalid
        self.assertEqual(ip, "unknown")

    def test_an_invalid_remote_addr_is_logged_without_the_raw_value(self):
        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "spoofed_ip_123"

        with self.assertLogs("apps.core.security", level="ERROR") as logs:
            ip = SecurityMonitor._get_client_ip(request)

        self.assertEqual(ip, "unknown")
        self.assertIn("invalid format", logs.output[0])
        self.assertNotIn("spoofed_ip_123", logs.output[0])

    def test_localhost_ips_accepted(self):
        """Test that localhost IPs are accepted."""
        request = self.factory.get("/api/test/")

        # IPv4 localhost
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        ip = SecurityMonitor._get_client_ip(request)
        self.assertEqual(ip, "127.0.0.1")

        # IPv6 localhost
        request.META["REMOTE_ADDR"] = "::1"
        ip = SecurityMonitor._get_client_ip(request)
        self.assertEqual(ip, "::1")

    def test_private_ips_accepted(self):
        """Test that private IP addresses are accepted."""
        private_ips = [
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
        ]

        for private_ip in private_ips:
            request = self.factory.get("/api/test/")
            request.META["REMOTE_ADDR"] = private_ip

            ip = SecurityMonitor._get_client_ip(request)

            self.assertEqual(ip, private_ip)


class IPValidationInSecurityContextTestCase(TestCase):
    """Test IP validation in security monitoring context."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPassword123!"
        )

    @override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
    def test_failed_login_tracking_with_spoofed_ip(self):
        """Failed-login tracking must use the validated REMOTE_ADDR, not a spoofed
        X-Forwarded-For value."""
        request = self.factory.post("/api/v1/auth/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_X_FORWARDED_FOR"] = "spoofed_ip, 10.0.0.1"

        validated_ip = SecurityMonitor._get_client_ip(request)

        # The garbage X-Forwarded-For value is rejected; the real REMOTE_ADDR wins.
        self.assertEqual(validated_ip, "192.168.1.100")

        # Tracking the validated IP must not raise.
        SecurityMonitor.track_failed_login(ip_address=validated_ip, username="testuser")

    def test_successful_login_tracking_with_validated_ip(self):
        """Test that successful login tracking uses validated IP."""
        request = self.factory.post("/api/v1/auth/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        # Track successful login
        ip = SecurityMonitor._get_client_ip(request)
        SecurityMonitor.track_successful_login(self.user, ip)

        # Should complete without error using validated IP
        self.assertEqual(ip, "192.168.1.100")
