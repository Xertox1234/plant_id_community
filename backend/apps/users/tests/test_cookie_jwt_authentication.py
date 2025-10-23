"""
Tests for Cookie-based JWT Authentication.

Tests the CookieJWTAuthentication class and cookie-based auth flow including:
- CSRF enforcement
- Cookie setting and retrieval
- Token extraction from cookies
- httpOnly and Secure flags
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from apps.users.authentication import (
    CookieJWTAuthentication,
    set_jwt_cookies,
    clear_jwt_cookies,
    RefreshTokenFromCookie
)
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class CookieJWTAuthenticationTestCase(TestCase):
    """Test cases for cookie-based JWT authentication."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_set_jwt_cookies(self):
        """Test that JWT tokens are set as httpOnly cookies."""
        from django.http import HttpResponse

        # Create a response
        response = HttpResponse()

        # Set JWT cookies
        response = set_jwt_cookies(response, self.user)

        # Check that access_token cookie is set
        self.assertIn('access_token', response.cookies)
        access_cookie = response.cookies['access_token']
        self.assertTrue(access_cookie['httponly'])
        self.assertIsNotNone(access_cookie.value)

        # Check that refresh_token cookie is set
        self.assertIn('refresh_token', response.cookies)
        refresh_cookie = response.cookies['refresh_token']
        self.assertTrue(refresh_cookie['httponly'])
        self.assertIsNotNone(refresh_cookie.value)

        # Check Secure flag based on DEBUG setting
        if not settings.DEBUG:
            self.assertTrue(access_cookie['secure'])
            self.assertTrue(refresh_cookie['secure'])

    def test_clear_jwt_cookies(self):
        """Test that JWT cookies are properly cleared."""
        from django.http import HttpResponse

        # Create response and set cookies first
        response = HttpResponse()
        response = set_jwt_cookies(response, self.user)

        # Clear cookies
        response = clear_jwt_cookies(response)

        # Check that cookies are cleared (max_age=0)
        access_cookie = response.cookies.get('access_token')
        refresh_cookie = response.cookies.get('refresh_token')

        # Cookies should be set to expire
        if access_cookie:
            self.assertEqual(access_cookie['max-age'], 0)
        if refresh_cookie:
            self.assertEqual(refresh_cookie['max-age'], 0)

    def test_cookie_jwt_authentication_with_valid_token(self):
        """Test authentication with valid JWT token in cookie."""
        # Create refresh token
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        # Create request with access token cookie
        request = self.factory.get('/api/test/')
        request.COOKIES = {'access_token': access_token}

        # Mock user attribute
        request.user = None

        # Authenticate
        auth = CookieJWTAuthentication()
        result = auth.authenticate(request)

        # Should return (user, token)
        self.assertIsNotNone(result)
        authenticated_user, validated_token = result
        self.assertEqual(authenticated_user.id, self.user.id)

    def test_cookie_jwt_authentication_without_cookie(self):
        """Test authentication fails gracefully without cookie."""
        # Create request without cookies
        request = self.factory.get('/api/test/')
        request.COOKIES = {}

        # Authenticate
        auth = CookieJWTAuthentication()
        result = auth.authenticate(request)

        # Should return None (not raise exception)
        self.assertIsNone(result)

    def test_cookie_jwt_authentication_with_invalid_token(self):
        """Test authentication fails with invalid token."""
        # Create request with invalid token
        request = self.factory.get('/api/test/')
        request.COOKIES = {'access_token': 'invalid_token_here'}
        request.user = None

        # Authenticate - should raise exception
        auth = CookieJWTAuthentication()
        result = auth.authenticate(request)

        # Should return None for invalid token
        self.assertIsNone(result)

    def test_refresh_token_from_cookie(self):
        """Test refresh token extraction from cookie."""
        # Create refresh token
        refresh = RefreshToken.for_user(self.user)
        refresh_token_str = str(refresh)

        # Create request with refresh token cookie
        request = self.factory.post('/api/auth/token/refresh/')
        request.COOKIES = {'refresh_token': refresh_token_str}

        # Extract refresh token
        extracted_token = RefreshTokenFromCookie.get_refresh_token(request)

        self.assertEqual(extracted_token, refresh_token_str)

    def test_refresh_token_from_post_data(self):
        """Test refresh token extraction from POST data."""
        # Create refresh token
        refresh = RefreshToken.for_user(self.user)
        refresh_token_str = str(refresh)

        # Create request with refresh token in POST data
        request = self.factory.post(
            '/api/auth/token/refresh/',
            data={'refresh': refresh_token_str}
        )

        # Mock request.data for DRF
        request.data = {'refresh': refresh_token_str}

        # Extract refresh token
        extracted_token = RefreshTokenFromCookie.get_refresh_token(request)

        self.assertEqual(extracted_token, refresh_token_str)

    def test_cookie_samesite_attribute(self):
        """Test that cookies have appropriate SameSite attribute."""
        from django.http import HttpResponse

        response = HttpResponse()
        response = set_jwt_cookies(response, self.user)

        access_cookie = response.cookies['access_token']

        # SameSite should be set based on DEBUG setting
        if settings.DEBUG:
            self.assertEqual(access_cookie['samesite'], 'Lax')
        else:
            self.assertEqual(access_cookie['samesite'], 'Strict')


class LoginLogoutCookieFlowTestCase(TestCase):
    """Test complete login/logout flow with cookie-based auth."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_login_sets_cookies(self):
        """Test that login endpoint sets JWT cookies."""
        # Get CSRF token first
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Login
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

    def test_logout_clears_cookies(self):
        """Test that logout endpoint clears JWT cookies."""
        # Login first
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

        # Get new CSRF token after login
        csrf_token = login_response.cookies.get('csrftoken').value

        # Logout
        logout_response = self.client.post(
            '/api/auth/logout/',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Cookies should be cleared (max_age=0)
        access_cookie = logout_response.cookies.get('access_token')
        if access_cookie:
            self.assertEqual(access_cookie['max-age'], 0)

    def test_authenticated_request_with_cookie(self):
        """Test making authenticated request with JWT cookie."""
        # Login to get cookies
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

        # Make authenticated request
        response = self.client.get('/api/auth/me/')

        # Should succeed with cookie authentication
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')


class CSRFProtectionTestCase(TestCase):
    """Test CSRF protection for cookie-based auth."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_login_requires_csrf_token(self):
        """Test that login endpoint requires CSRF token."""
        # Attempt login without CSRF token
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            }
        )

        # Should fail due to missing CSRF token
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_succeeds_with_csrf_token(self):
        """Test that login succeeds with valid CSRF token."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Login with CSRF token
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_token_refresh_requires_csrf(self):
        """Test that token refresh endpoint requires CSRF token."""
        # Login first to get refresh token
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

        # Attempt token refresh without CSRF token (should fail)
        response = self.client.post('/api/auth/token/refresh/')

        # Should fail due to CSRF protection
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
