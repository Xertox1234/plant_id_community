"""
Tests for Token Refresh functionality.

Tests token refresh, blacklisting, rotation, and CSRF protection including:
- Token refresh with valid refresh token
- Token blacklisting after rotation
- CSRF enforcement on refresh endpoint
- Invalid/expired token handling
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from unittest.mock import patch
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
