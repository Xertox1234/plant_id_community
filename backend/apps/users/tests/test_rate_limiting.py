"""
Tests for Rate Limiting.

Tests per-IP and per-user rate limits for authentication endpoints including:
- Login rate limiting (5/15m per IP)
- Registration rate limiting (3/h per IP)
- Token refresh rate limiting (10/h)
- Authenticated vs anonymous rate limits

WHY EVERY COUNT-TO-LIMIT TEST HERE FREEZES TIME
-----------------------------------------------
django-ratelimit buckets by a window END computed per key, not by a sliding
count (`django_ratelimit/core.py::_get_window`)::

    ts = int(time.time())
    w  = ts - (ts % period) + (zlib.crc32(value) % period)

That `w` is a fixed wall-clock instant (the crc32 term only jitters WHICH
instant, per key), and `_make_cache_key` folds the window into the cache key.
So when wall-clock crosses `w` the key changes and the counter RESETS to zero.
A test that fires N requests and expects the N+1th to be blocked therefore
fails with the endpoint's normal status (401/201) instead of 429 whenever the
hammer straddles that boundary — rare per run, but this suite runs on every
push, and it took down `main` on 2026-07-30 (backend CI run 30550373085) with
`AssertionError: 401 != 429`.

`freeze_time` pins `time.time()` so every request in one test shares one
window, which is the condition the assertions actually describe.

Use the CONTEXT-MANAGER form, never the bare `@freeze_time()` decorator:
`freeze_time()` resolves "now" when the object is CONSTRUCTED, and a decorator
is constructed at import time — so the whole suite would freeze to whenever
this module was imported, not to when each test runs.

Freezing is safe for these assertions: `Retry-After` is derived from the rate
STRING (`apps/core/exceptions.py::_retry_after_seconds`, e.g. 15m -> 900), not
from time remaining in the window, so it stays positive under a freeze.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class LoginRateLimitingTestCase(TestCase):
    """Test rate limiting for login endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPassword123!"
        )
        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_login_rate_limit_per_ip(self):
        """Test that login is rate limited to 5 attempts per 15 minutes per IP."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            # Get CSRF token
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            # Make 5 login attempts (should succeed)
            for i in range(5):
                response = self.client.post(
                    "/api/v1/auth/login/",
                    data={"username": "testuser", "password": "WrongPassword123!"},
                    HTTP_X_CSRFTOKEN=csrf_token,
                )
                # Should fail due to wrong password but not rate limited
                self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED])

            # 6th attempt should be rate limited
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            response = self.client.post(
                "/api/v1/auth/login/",
                data={"username": "testuser", "password": "WrongPassword123!"},
                HTTP_X_CSRFTOKEN=csrf_token,
            )

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_rate_limit_different_ips(self):
        """Test that rate limit is per-IP (different IPs have separate limits)."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            # Get CSRF token
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            # Make 5 attempts from first IP
            for i in range(5):
                self.client.post(
                    "/api/v1/auth/login/",
                    data={"username": "testuser", "password": "WrongPassword123!"},
                    HTTP_X_CSRFTOKEN=csrf_token,
                    REMOTE_ADDR="192.168.1.1",
                )

            # Attempt from different IP should not be rate limited
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            response = self.client.post(
                "/api/v1/auth/login/",
                data={"username": "testuser", "password": "WrongPassword123!"},
                HTTP_X_CSRFTOKEN=csrf_token,
                REMOTE_ADDR="192.168.1.2",
            )

            # Should fail due to wrong password but NOT rate limited
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_rate_limit_counts_successful_attempts(self):
        """The login rate limit (5/15m) counts every attempt by IP, including
        successful ones — the 6th login in the window is blocked with 429."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            # Get CSRF token
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            # Make 5 successful logins
            for i in range(5):
                # Logout if logged in
                self.client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=csrf_token)

                csrf_response = self.client.get("/api/v1/auth/csrf/")
                csrf_token = csrf_response.cookies.get("csrftoken").value

                response = self.client.post(
                    "/api/v1/auth/login/",
                    data={"username": "testuser", "password": "TestPassword123!"},
                    HTTP_X_CSRFTOKEN=csrf_token,
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

            # 6th successful login should still work (not rate limited)
            self.client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=csrf_token)

            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            response = self.client.post(
                "/api/v1/auth/login/",
                data={"username": "testuser", "password": "TestPassword123!"},
                HTTP_X_CSRFTOKEN=csrf_token,
            )

            # The @ratelimit(5/15m) decorator counts ALL login POSTs by IP, not just
            # failed ones, so the 6th attempt in the window is blocked regardless of
            # whether the credentials are valid.
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class RegistrationRateLimitingTestCase(TestCase):
    """Test rate limiting for registration endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_registration_rate_limit_per_ip(self):
        """Test that registration is rate limited to 3 per hour per IP."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            # Get CSRF token
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            # Make 3 registration attempts (should succeed)
            for i in range(3):
                response = self.client.post(
                    "/api/v1/auth/register/",
                    data={
                        "username": f"testuser{i}",
                        "email": f"test{i}@example.com",
                        "password": "TestPassword123!",
                        "confirmPassword": "TestPassword123!",
                    },
                    HTTP_X_CSRFTOKEN=csrf_token,
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # 4th attempt should be rate limited
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            response = self.client.post(
                "/api/v1/auth/register/",
                data={
                    "username": "testuser4",
                    "email": "test4@example.com",
                    "password": "TestPassword123!",
                    "confirmPassword": "TestPassword123!",
                },
                HTTP_X_CSRFTOKEN=csrf_token,
            )

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_registration_rate_limit_different_ips(self):
        """Test that registration rate limit is per-IP."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            # Get CSRF token
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            # Make 3 registrations from first IP
            for i in range(3):
                self.client.post(
                    "/api/v1/auth/register/",
                    data={
                        "username": f"testuser{i}",
                        "email": f"test{i}@example.com",
                        "password": "TestPassword123!",
                        "confirmPassword": "TestPassword123!",
                    },
                    HTTP_X_CSRFTOKEN=csrf_token,
                    REMOTE_ADDR="192.168.1.1",
                )

            # Registration from different IP should work
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            response = self.client.post(
                "/api/v1/auth/register/",
                data={
                    "username": "testuser_different_ip",
                    "email": "test_different@example.com",
                    "password": "TestPassword123!",
                    "confirmPassword": "TestPassword123!",
                },
                HTTP_X_CSRFTOKEN=csrf_token,
                REMOTE_ADDR="192.168.1.2",
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TokenRefreshRateLimitingTestCase(TestCase):
    """Test rate limiting for token refresh endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPassword123!"
        )
        cache.clear()

        # Login to get refresh token
        csrf_response = self.client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.cookies.get("csrftoken").value

        self.client.post(
            "/api/v1/auth/login/",
            data={"username": "testuser", "password": "TestPassword123!"},
            HTTP_X_CSRFTOKEN=csrf_token,
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_token_refresh_rate_limit(self):
        """Test that token refresh is rate limited to 10 per hour."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            # Make 10 refresh requests (should succeed)
            for i in range(10):
                csrf_response = self.client.get("/api/v1/auth/csrf/")
                csrf_token = csrf_response.cookies.get("csrftoken").value

                response = self.client.post(
                    "/api/v1/auth/token/refresh/", HTTP_X_CSRFTOKEN=csrf_token
                )
                # Some may fail if token is blacklisted, but should not be rate limited
                self.assertIn(
                    response.status_code,
                    [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED],
                )

            # 11th attempt should be rate limited
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            response = self.client.post(
                "/api/v1/auth/token/refresh/", HTTP_X_CSRFTOKEN=csrf_token
            )

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class RateLimitHeadersTestCase(TestCase):
    """Test that rate limit information is communicated to clients."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestPassword123!"
        )
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_rate_limit_response_includes_retry_after(self):
        """A rate-limited (429) login response must carry a Retry-After header
        with a positive integer seconds value (RFC 6585 / CLAUDE.md gotcha #4)."""
        # freeze_time so all N requests share ONE rate-limit window (see
        # module docstring). Context-manager form, NOT @freeze_time() —
        # the decorator captures "now" at import time, not call time.
        with freeze_time():
            csrf_response = self.client.get("/api/v1/auth/csrf/")
            csrf_token = csrf_response.cookies.get("csrftoken").value

            # 5 attempts stay within the 5/15m per-IP login limit.
            for _ in range(5):
                self.client.post(
                    "/api/v1/auth/login/",
                    data={"username": "testuser", "password": "WrongPassword123!"},
                    HTTP_X_CSRFTOKEN=csrf_token,
                )

            # The 6th attempt in the window is rate limited.
            response = self.client.post(
                "/api/v1/auth/login/",
                data={"username": "testuser", "password": "WrongPassword123!"},
                HTTP_X_CSRFTOKEN=csrf_token,
            )

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertTrue(
                response.has_header("Retry-After"),
                "429 response must include a Retry-After header",
            )
            self.assertGreater(int(response["Retry-After"]), 0)
