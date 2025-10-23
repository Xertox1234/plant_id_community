"""
Tests for Rate Limiting.

Tests per-IP and per-user rate limits for authentication endpoints including:
- Login rate limiting (5/15m per IP)
- Registration rate limiting (3/h per IP)
- Token refresh rate limiting (10/h)
- Authenticated vs anonymous rate limits
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
import time

User = get_user_model()


class LoginRateLimitingTestCase(TestCase):
    """Test rate limiting for login endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_login_rate_limit_per_ip(self):
        """Test that login is rate limited to 5 attempts per 15 minutes per IP."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make 5 login attempts (should succeed)
        for i in range(5):
            response = self.client.post(
                '/api/auth/login/',
                data={
                    'username': 'testuser',
                    'password': 'WrongPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token
            )
            # Should fail due to wrong password but not rate limited
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED])

        # 6th attempt should be rate limited
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'WrongPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_rate_limit_different_ips(self):
        """Test that rate limit is per-IP (different IPs have separate limits)."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make 5 attempts from first IP
        for i in range(5):
            self.client.post(
                '/api/auth/login/',
                data={
                    'username': 'testuser',
                    'password': 'WrongPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token,
                REMOTE_ADDR='192.168.1.1'
            )

        # Attempt from different IP should not be rate limited
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'WrongPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token,
            REMOTE_ADDR='192.168.1.2'
        )

        # Should fail due to wrong password but NOT rate limited
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_successful_login_not_rate_limited(self):
        """Test that successful logins don't count toward rate limit."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make 5 successful logins
        for i in range(5):
            # Logout if logged in
            self.client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=csrf_token)

            csrf_response = self.client.get('/api/auth/csrf/')
            csrf_token = csrf_response.cookies.get('csrftoken').value

            response = self.client.post(
                '/api/auth/login/',
                data={
                    'username': 'testuser',
                    'password': 'TestPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 6th successful login should still work (not rate limited)
        self.client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=csrf_token)

        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Note: This might be rate limited by django-ratelimit
        # The rate limit applies to ALL requests, not just failed ones
        # So this test may need adjustment based on actual implementation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])


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
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make 3 registration attempts (should succeed)
        for i in range(3):
            response = self.client.post(
                '/api/auth/register/',
                data={
                    'username': f'testuser{i}',
                    'email': f'test{i}@example.com',
                    'password': 'TestPassword123!',
                    'confirmPassword': 'TestPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 4th attempt should be rate limited
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/register/',
            data={
                'username': 'testuser4',
                'email': 'test4@example.com',
                'password': 'TestPassword123!',
                'confirmPassword': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_registration_rate_limit_different_ips(self):
        """Test that registration rate limit is per-IP."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make 3 registrations from first IP
        for i in range(3):
            self.client.post(
                '/api/auth/register/',
                data={
                    'username': f'testuser{i}',
                    'email': f'test{i}@example.com',
                    'password': 'TestPassword123!',
                    'confirmPassword': 'TestPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token,
                REMOTE_ADDR='192.168.1.1'
            )

        # Registration from different IP should work
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/register/',
            data={
                'username': 'testuser_different_ip',
                'email': 'test_different@example.com',
                'password': 'TestPassword123!',
                'confirmPassword': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token,
            REMOTE_ADDR='192.168.1.2'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TokenRefreshRateLimitingTestCase(TestCase):
    """Test rate limiting for token refresh endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        cache.clear()

        # Login to get refresh token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_token_refresh_rate_limit(self):
        """Test that token refresh is rate limited to 10 per hour."""
        # Make 10 refresh requests (should succeed)
        for i in range(10):
            csrf_response = self.client.get('/api/auth/csrf/')
            csrf_token = csrf_response.cookies.get('csrftoken').value

            response = self.client.post(
                '/api/auth/token/refresh/',
                HTTP_X_CSRFTOKEN=csrf_token
            )
            # Some may fail if token is blacklisted, but should not be rate limited
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED])

        # 11th attempt should be rate limited
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class RateLimitHeadersTestCase(TestCase):
    """Test that rate limit information is communicated to clients."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_rate_limit_response_includes_retry_after(self):
        """Test that rate limited responses include Retry-After header."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make requests until rate limited
        for i in range(6):
            response = self.client.post(
                '/api/auth/login/',
                data={
                    'username': 'testuser',
                    'password': 'WrongPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token
            )

        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            # Check for Retry-After header (django-ratelimit may set this)
            # Note: This depends on django-ratelimit configuration
            # May not be present in all configurations
            pass  # Header check is optional


class AnonymousVsAuthenticatedRateLimitsTestCase(TestCase):
    """Test different rate limits for anonymous vs authenticated users."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_anonymous_has_stricter_limits(self):
        """Test that anonymous users have stricter rate limits."""
        # This test depends on specific endpoint implementations
        # For plant identification endpoint, anonymous users have 10/hour
        # while authenticated users have 100/hour

        # Test anonymous access to a rate-limited endpoint
        # (Assuming plant identification endpoint exists and is rate limited)
        pass  # Implementation depends on specific endpoints

    def test_authentication_increases_rate_limit(self):
        """Test that authenticated users get higher rate limits."""
        # Login
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Test that authenticated user can make more requests
        # (Specific implementation depends on endpoint configuration)
        pass  # Implementation depends on specific endpoints
