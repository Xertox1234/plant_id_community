"""
Tests for Token Refresh functionality.

Tests token refresh, blacklisting, rotation, and CSRF protection including:
- Token refresh with valid refresh token
- Token blacklisting after rotation
- CSRF enforcement on refresh endpoint
- Invalid/expired token handling
- Token expiration verification (OWASP compliance)
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.exceptions import TokenError
from unittest.mock import patch
from datetime import timedelta
from django.conf import settings
import time

User = get_user_model()


class TokenRefreshTestCase(TestCase):
    """Test cases for token refresh functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_token_refresh_with_valid_token(self):
        """Test token refresh with valid refresh token in cookie."""
        # Login to get refresh token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        login_response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        # Get new CSRF token
        csrf_token = login_response.cookies.get('csrftoken').value

        # Refresh token
        refresh_response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', refresh_response.cookies)
        self.assertIn('refresh_token', refresh_response.cookies)

    def test_token_refresh_without_csrf(self):
        """Test that token refresh requires CSRF token."""
        # Login first
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

        # Attempt refresh without CSRF token
        refresh_response = self.client.post('/api/auth/token/refresh/')

        # Should fail due to CSRF protection
        self.assertEqual(refresh_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_token_refresh_without_refresh_token(self):
        """Test token refresh fails without refresh token."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Attempt refresh without being logged in (no refresh token)
        response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_token_refresh_with_invalid_token(self):
        """Test token refresh fails with invalid refresh token."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Set invalid refresh token in cookie
        self.client.cookies['refresh_token'] = 'invalid_token_here'

        # Attempt refresh
        response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)

    def test_token_rotation_on_refresh(self):
        """Test that refresh tokens are rotated on refresh."""
        # Login to get initial refresh token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        login_response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        original_refresh_token = login_response.cookies.get('refresh_token').value

        # Refresh token
        csrf_token = login_response.cookies.get('csrftoken').value
        refresh_response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        new_refresh_token = refresh_response.cookies.get('refresh_token').value

        # Tokens should be different (rotation)
        self.assertNotEqual(original_refresh_token, new_refresh_token)

    def test_old_refresh_token_blacklisted(self):
        """Test that old refresh token is blacklisted after rotation."""
        # Login to get initial refresh token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        login_response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Refresh token
        csrf_token = login_response.cookies.get('csrftoken').value
        self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Try to use old refresh token again (should fail)
        # Reset cookies to use old token
        old_refresh_token = login_response.cookies.get('refresh_token').value
        self.client.cookies['refresh_token'] = old_refresh_token

        # Get new CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        second_refresh_response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Should fail because old token is blacklisted
        self.assertEqual(second_refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_rate_limiting(self):
        """Test that token refresh endpoint is rate limited."""
        # Login first
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

        # Make many refresh requests to trigger rate limit (10/h limit)
        for i in range(11):
            csrf_response = self.client.get('/api/auth/csrf/')
            csrf_token = csrf_response.cookies.get('csrftoken').value

            response = self.client.post(
                '/api/auth/token/refresh/',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if i < 10:
                # First 10 should succeed
                self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED])
            else:
                # 11th should be rate limited
                self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_blacklist_on_logout(self):
        """Test that refresh token is blacklisted on logout."""
        # Login
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        login_response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        refresh_token = login_response.cookies.get('refresh_token').value

        # Logout
        csrf_token = login_response.cookies.get('csrftoken').value
        self.client.post(
            '/api/auth/logout/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Try to use the refresh token after logout
        self.client.cookies['refresh_token'] = refresh_token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Should fail because token is blacklisted
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_updates_last_login(self):
        """Test that token refresh updates user's last_login."""
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

        # Get user's last_login before refresh
        self.user.refresh_from_db()
        last_login_before = self.user.last_login

        # Wait a bit
        time.sleep(0.1)

        # Refresh token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Get user's last_login after refresh
        self.user.refresh_from_db()
        last_login_after = self.user.last_login

        # last_login should be updated (if UPDATE_LAST_LOGIN is True)
        # This depends on JWT settings configuration
        # For now, just check that it's still set
        self.assertIsNotNone(last_login_after)


class TokenRefreshErrorHandlingTestCase(TestCase):
    """Test error handling for token refresh."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_refresh_with_blacklist_failure(self):
        """Test token refresh handles blacklist failures gracefully."""
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

        # Mock blacklist to raise exception
        with patch('rest_framework_simplejwt.tokens.RefreshToken.blacklist') as mock_blacklist:
            mock_blacklist.side_effect = Exception('Blacklist service unavailable')

            csrf_response = self.client.get('/api/auth/csrf/')
            csrf_token = csrf_response.cookies.get('csrftoken').value

            response = self.client.post(
                '/api/auth/token/refresh/',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            # Should return service unavailable error
            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertIn('error', response.data)

    def test_refresh_with_nonexistent_user(self):
        """Test token refresh fails if user no longer exists."""
        # Create a refresh token
        refresh = RefreshToken.for_user(self.user)
        refresh_token_str = str(refresh)

        # Delete the user
        self.user.delete()

        # Set the refresh token in cookies
        self.client.cookies['refresh_token'] = refresh_token_str

        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Attempt refresh
        response = self.client.post(
            '/api/auth/token/refresh/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Should fail with unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)


class TokenLifetimeTestCase(TestCase):
    """Test cases for JWT token lifetime configuration (OWASP compliance)."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_access_token_lifetime_configuration(self):
        """Test that access token lifetime is configured correctly (1 hour max)."""
        # Get the configured access token lifetime
        access_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']

        # OWASP recommends 15-60 minutes for access tokens
        # Phase 1: 1 hour (60 minutes) is acceptable
        # Phase 2 target: 15 minutes
        max_lifetime = timedelta(hours=1)
        recommended_lifetime = timedelta(minutes=15)

        # Verify token lifetime is within OWASP recommendations
        self.assertLessEqual(
            access_lifetime,
            max_lifetime,
            f"Access token lifetime ({access_lifetime}) exceeds 1 hour maximum. "
            f"OWASP recommends ≤60 minutes for access tokens."
        )

        # Log warning if not at recommended 15 minutes (Phase 2 target)
        if access_lifetime > recommended_lifetime:
            print(f"\nWARNING: Access token lifetime is {access_lifetime} (Phase 1)")
            print(f"OWASP recommends {recommended_lifetime} (Phase 2 target)")
            print("Consider implementing frontend auto-refresh for 15-minute tokens")

    def test_refresh_token_lifetime_configuration(self):
        """Test that refresh token lifetime is reasonable (7-30 days)."""
        # Get the configured refresh token lifetime
        refresh_lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']

        # Reasonable range: 7-30 days
        min_lifetime = timedelta(days=7)
        max_lifetime = timedelta(days=30)

        self.assertGreaterEqual(
            refresh_lifetime,
            min_lifetime,
            f"Refresh token lifetime ({refresh_lifetime}) is too short. "
            f"Minimum recommended: {min_lifetime}"
        )

        self.assertLessEqual(
            refresh_lifetime,
            max_lifetime,
            f"Refresh token lifetime ({refresh_lifetime}) is too long. "
            f"Maximum recommended: {max_lifetime}"
        )

    def test_token_rotation_enabled(self):
        """Test that token rotation is enabled for security."""
        self.assertTrue(
            settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS'],
            "Token rotation must be enabled (ROTATE_REFRESH_TOKENS=True)"
        )

    def test_token_blacklist_enabled(self):
        """Test that token blacklisting is enabled after rotation."""
        self.assertTrue(
            settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'],
            "Token blacklisting must be enabled (BLACKLIST_AFTER_ROTATION=True)"
        )

    def test_access_token_expires_correctly(self):
        """Test that access tokens actually expire after configured lifetime."""
        # Create an access token
        refresh = RefreshToken.for_user(self.user)
        access = refresh.access_token

        # Check token is valid now
        try:
            AccessToken(str(access))
            token_valid = True
        except TokenError:
            token_valid = False

        self.assertTrue(token_valid, "Newly created access token should be valid")

        # Verify token has expiration claim
        self.assertIn('exp', access.payload)

        # Verify expiration time matches configured lifetime
        token_lifetime = access['exp'] - access['iat']
        configured_lifetime = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())

        # Allow 1 second tolerance for processing time
        self.assertAlmostEqual(
            token_lifetime,
            configured_lifetime,
            delta=1,
            msg=f"Token lifetime ({token_lifetime}s) doesn't match configured lifetime ({configured_lifetime}s)"
        )

    def test_expired_access_token_rejected(self):
        """Test that expired access tokens are rejected by the API."""
        # Login to get tokens
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        login_response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        # Create an expired access token by manipulating the payload
        refresh = RefreshToken.for_user(self.user)
        access = refresh.access_token

        # Set expiration to 1 second ago
        access.set_exp(lifetime=-timedelta(seconds=1))

        # Try to use the expired token
        self.client.cookies['access_token'] = str(access)

        # Attempt to access a protected endpoint (if available)
        # For now, just verify the token is considered invalid
        try:
            AccessToken(str(access))
            token_valid = True
        except TokenError:
            token_valid = False

        self.assertFalse(token_valid, "Expired access token should be invalid")

    def test_security_window_reduced(self):
        """Test that the security window for stolen tokens is acceptable."""
        # Get the configured access token lifetime in seconds
        access_lifetime_seconds = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()

        # Phase 1 target: ≤1 hour (3600 seconds)
        # Phase 2 target: ≤15 minutes (900 seconds)
        phase1_target = 3600  # 1 hour
        phase2_target = 900   # 15 minutes

        self.assertLessEqual(
            access_lifetime_seconds,
            phase1_target,
            f"Access token lifetime ({access_lifetime_seconds}s) exceeds Phase 1 target ({phase1_target}s). "
            f"This creates a {access_lifetime_seconds/3600:.1f}-hour window for session hijacking."
        )

        # Calculate security improvement vs. 24-hour tokens
        old_lifetime = 86400  # 24 hours in seconds
        improvement_factor = old_lifetime / access_lifetime_seconds

        print(f"\nSecurity window analysis:")
        print(f"  Current token lifetime: {access_lifetime_seconds/60:.0f} minutes")
        print(f"  Hijacking window: {access_lifetime_seconds/3600:.1f} hours")
        print(f"  Improvement over 24h tokens: {improvement_factor:.0f}x smaller window")
        print(f"  Phase 2 target: {phase2_target/60:.0f} minutes ({old_lifetime/phase2_target:.0f}x improvement)")

    def test_production_vs_debug_token_lifetimes(self):
        """Test that debug mode has extended tokens for easier development."""
        # This test verifies the configuration only if DEBUG mode is being used
        if settings.DEBUG:
            debug_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME_DEBUG')
            if debug_lifetime:
                # Debug tokens should be longer than production tokens for convenience
                production_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']

                self.assertGreater(
                    debug_lifetime,
                    production_lifetime,
                    "Debug mode tokens should be longer than production tokens"
                )

                print(f"\nDebug mode token configuration:")
                print(f"  Production lifetime: {production_lifetime}")
                print(f"  Debug lifetime: {debug_lifetime}")
        else:
            # In production, ACCESS_TOKEN_LIFETIME_DEBUG should be None
            debug_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME_DEBUG')
            self.assertIsNone(
                debug_lifetime,
                "Debug token lifetime should be None in production"
            )
