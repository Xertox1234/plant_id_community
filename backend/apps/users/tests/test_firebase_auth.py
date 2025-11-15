"""
Tests for Firebase Authentication Integration.

This module tests the Firebase token exchange endpoint that validates Firebase ID tokens
and exchanges them for Django JWT tokens.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class FirebaseTokenExchangeTestCase(TestCase):
    """Test cases for Firebase token exchange endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.url = reverse('users:firebase_token_exchange')

        # Sample Firebase token (fake, for testing only)
        self.firebase_token = 'eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3QifQ.eyJ1aWQiOiJ0ZXN0dWlkMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.test'

        # Sample decoded token data
        self.decoded_token = {
            'uid': 'test-firebase-uid-123',
            'email': 'test@example.com',
            'email_verified': True,
        }

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_successful_token_exchange_new_user(self, mock_verify):
        """Test successful token exchange for a new user."""
        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Make request
        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
            'display_name': 'Test User',
        }, format='json')

        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)

        # Verify user was created
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.first_name, 'Test User')
        self.assertTrue(user.is_active)

        # Verify user data in response
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        self.assertEqual(response.data['user']['display_name'], 'Test User')
        self.assertTrue(response.data['user']['is_active'])

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_successful_token_exchange_existing_user(self, mock_verify):
        """Test successful token exchange for an existing user."""
        # Create existing user
        existing_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Make request
        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
        }, format='json')

        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)

        # Verify no duplicate user was created
        self.assertEqual(User.objects.filter(email='test@example.com').count(), 1)

        # Verify response contains existing user data
        self.assertEqual(response.data['user']['id'], existing_user.id)
        self.assertEqual(response.data['user']['email'], 'test@example.com')

    def test_missing_firebase_token(self):
        """Test error when firebase_token is missing."""
        response = self.client.post(self.url, {
            'email': 'test@example.com',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'firebase_token is required')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_invalid_firebase_token(self, mock_verify):
        """Test error when Firebase token is invalid."""
        # Mock Firebase token verification failure
        from firebase_admin.auth import InvalidIdTokenError
        mock_verify.side_effect = InvalidIdTokenError('Invalid token')

        response = self.client.post(self.url, {
            'firebase_token': 'invalid-token',
            'email': 'test@example.com',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Invalid Firebase token')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_expired_firebase_token(self, mock_verify):
        """Test error when Firebase token is expired."""
        # Mock Firebase token expiration
        from firebase_admin.auth import ExpiredIdTokenError
        mock_verify.side_effect = ExpiredIdTokenError('Token expired')

        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Firebase token has expired')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_firebase_verification_exception(self, mock_verify):
        """Test error when Firebase verification raises an exception."""
        # Mock Firebase verification exception
        mock_verify.side_effect = Exception('Firebase service unavailable')

        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Token verification failed')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_update_display_name_for_existing_user(self, mock_verify):
        """Test that display name is updated for existing user if not set."""
        # Create user without first_name
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name=''
        )

        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Make request with display_name
        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
            'display_name': 'Updated Name',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify display name was updated
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.first_name, 'Updated Name')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_dont_override_existing_display_name(self, mock_verify):
        """Test that existing display name is not overridden."""
        # Create user with first_name already set
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Original Name'
        )

        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Make request with different display_name
        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
            'display_name': 'New Name',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify display name was NOT changed
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.first_name, 'Original Name')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_jwt_tokens_are_valid(self, mock_verify):
        """Test that returned JWT tokens are valid and can be used for authentication."""
        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Make request
        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
            'display_name': 'Test User',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['access_token']

        # Try to access a protected endpoint with the JWT
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # Get current user endpoint (should be accessible with JWT)
        current_user_url = reverse('users:current_user')
        user_response = self.client.get(current_user_url)

        # Verify we can access protected endpoint
        self.assertEqual(user_response.status_code, status.HTTP_200_OK)
        self.assertEqual(user_response.data['email'], 'test@example.com')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_username_generation_from_email(self, mock_verify):
        """Test that username is correctly generated from email prefix."""
        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Make request
        response = self.client.post(self.url, {
            'firebase_token': self.firebase_token,
            'email': 'test@example.com',
            'display_name': 'Test User',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify username was set to email prefix
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.username, 'test')

    @patch('apps.users.firebase_auth_views.firebase_auth.verify_id_token')
    def test_unexpected_error_handling(self, mock_verify):
        """Test handling of unexpected errors during token exchange."""
        # Mock Firebase token verification
        mock_verify.return_value = self.decoded_token

        # Mock User.objects.get_or_create to raise an exception
        with patch('apps.users.firebase_auth_views.User.objects.get_or_create') as mock_get_create:
            mock_get_create.side_effect = Exception('Database error')

            response = self.client.post(self.url, {
                'firebase_token': self.firebase_token,
                'email': 'test@example.com',
            }, format='json')

            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn('error', response.data)
            self.assertEqual(response.data['error'], 'Internal server error')


class GetOrCreateUserFromFirebaseTestCase(TestCase):
    """Test cases for get_or_create_user_from_firebase helper function."""

    def test_create_new_user(self):
        """Test creating a new user from Firebase credentials."""
        from apps.users.firebase_auth_views import get_or_create_user_from_firebase

        user, created = get_or_create_user_from_firebase(
            firebase_uid='firebase-uid-123',
            firebase_email='newuser@example.com',
            display_name='New User'
        )

        self.assertTrue(created)
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'New User')
        self.assertEqual(user.username, 'newuser')
        self.assertTrue(user.is_active)

    def test_get_existing_user(self):
        """Test retrieving an existing user."""
        from apps.users.firebase_auth_views import get_or_create_user_from_firebase

        # Create existing user
        existing_user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='testpass123'
        )

        user, created = get_or_create_user_from_firebase(
            firebase_uid='firebase-uid-456',
            firebase_email='existing@example.com',
            display_name='Should Not Change'
        )

        self.assertFalse(created)
        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(user.email, 'existing@example.com')

    def test_update_display_name_if_empty(self):
        """Test that display name is updated if user has no first_name."""
        from apps.users.firebase_auth_views import get_or_create_user_from_firebase

        # Create user without first_name
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name=''
        )

        user, created = get_or_create_user_from_firebase(
            firebase_uid='firebase-uid-789',
            firebase_email='test@example.com',
            display_name='Updated Name'
        )

        self.assertFalse(created)
        self.assertEqual(user.first_name, 'Updated Name')

    def test_dont_update_existing_display_name(self):
        """Test that existing display name is preserved."""
        from apps.users.firebase_auth_views import get_or_create_user_from_firebase

        # Create user with first_name
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Original Name'
        )

        user, created = get_or_create_user_from_firebase(
            firebase_uid='firebase-uid-789',
            firebase_email='test@example.com',
            display_name='New Name'
        )

        self.assertFalse(created)
        self.assertEqual(user.first_name, 'Original Name')

    def test_create_user_without_display_name(self):
        """Test creating a user without providing a display name."""
        from apps.users.firebase_auth_views import get_or_create_user_from_firebase

        user, created = get_or_create_user_from_firebase(
            firebase_uid='firebase-uid-999',
            firebase_email='nodisplay@example.com',
            display_name=None
        )

        self.assertTrue(created)
        self.assertEqual(user.email, 'nodisplay@example.com')
        self.assertEqual(user.first_name, '')
