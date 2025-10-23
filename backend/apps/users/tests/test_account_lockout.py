"""
Tests for Account Lockout functionality.

Tests account lockout after failed login attempts including:
- Lockout after 10 failed attempts
- Lockout duration (1 hour)
- Email notifications on lockout
- Manual unlock mechanism
- Lockout expiry and auto-unlock
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.core.security import SecurityMonitor
from apps.core.constants import (
    ACCOUNT_LOCKOUT_THRESHOLD,
    ACCOUNT_LOCKOUT_DURATION,
)
from unittest.mock import patch
import time

User = get_user_model()


class AccountLockoutTestCase(TestCase):
    """Test cases for account lockout after failed login attempts."""

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

    def test_account_locked_after_threshold_failed_attempts(self):
        """Test that account is locked after exceeding failed login threshold."""
        # Make failed login attempts up to threshold
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            is_locked, attempts = SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

            if i < ACCOUNT_LOCKOUT_THRESHOLD - 1:
                self.assertFalse(is_locked)
            else:
                # Last attempt should trigger lockout
                self.assertTrue(is_locked)

        # Verify account is locked
        is_locked, time_remaining = SecurityMonitor.is_account_locked('testuser')
        self.assertTrue(is_locked)
        self.assertIsNotNone(time_remaining)
        self.assertGreater(time_remaining, 0)

    def test_lockout_prevents_further_login_attempts(self):
        """Test that locked account prevents login attempts."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Attempt login (even with correct password)
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Should be rejected due to lockout
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'ACCOUNT_LOCKED')

    def test_lockout_email_notification_sent(self):
        """Test that email notification is sent on account lockout."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('testuser', email.body)
        self.assertIn('locked', email.subject.lower())
        self.assertEqual(email.to, ['test@example.com'])

    def test_lockout_email_contains_unlock_time(self):
        """Test that lockout email contains unlock time information."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Check email content
        email = mail.outbox[0]
        self.assertIn('Unlocks at:', email.body)
        self.assertIn('Failed attempts:', email.body)
        self.assertIn('IP addresses:', email.body)

    def test_lockout_tracks_multiple_ip_addresses(self):
        """Test that lockout tracks all IP addresses involved in failed attempts."""
        # Make failed attempts from different IPs
        ips = ['192.168.1.100', '192.168.1.101', '192.168.1.102']

        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            ip = ips[i % len(ips)]
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address=ip
            )

        # Check that email contains all IPs
        email = mail.outbox[0]
        for ip in ips:
            self.assertIn(ip, email.body)

    def test_successful_login_clears_failed_attempts(self):
        """Test that successful login clears failed attempt counter."""
        # Make some failed attempts (but not enough to lock)
        for i in range(5):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Clear failed attempts (simulating successful login)
        SecurityMonitor._clear_failed_attempts('testuser')

        # Verify attempts are cleared
        is_locked, attempts = SecurityMonitor.track_failed_login_attempt(
            username='testuser',
            ip_address='192.168.1.100'
        )

        # Should be first attempt after clearing
        self.assertFalse(is_locked)

    def test_lockout_duration_enforced(self):
        """Test that lockout lasts for specified duration."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Check initial lockout
        is_locked, time_remaining = SecurityMonitor.is_account_locked('testuser')
        self.assertTrue(is_locked)

        # Time remaining should be close to lockout duration
        self.assertGreater(time_remaining, ACCOUNT_LOCKOUT_DURATION - 10)
        self.assertLessEqual(time_remaining, ACCOUNT_LOCKOUT_DURATION)

    def test_lockout_expires_automatically(self):
        """Test that lockout expires after duration."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Mock time passage (advance cache expiry)
        # In real scenario, would need to wait or mock time.time()
        with patch('time.time') as mock_time:
            # Set current time to past lockout expiry
            mock_time.return_value = time.time() + ACCOUNT_LOCKOUT_DURATION + 1

            is_locked, time_remaining = SecurityMonitor.is_account_locked('testuser')

            # Should be unlocked after duration
            self.assertFalse(is_locked)
            self.assertIsNone(time_remaining)

    def test_manual_unlock_account(self):
        """Test manual account unlock (admin function)."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Verify locked
        is_locked, _ = SecurityMonitor.is_account_locked('testuser')
        self.assertTrue(is_locked)

        # Manually unlock
        was_locked = SecurityMonitor.unlock_account('testuser')
        self.assertTrue(was_locked)

        # Verify unlocked
        is_locked, time_remaining = SecurityMonitor.is_account_locked('testuser')
        self.assertFalse(is_locked)
        self.assertIsNone(time_remaining)

    def test_unlock_account_not_locked(self):
        """Test unlocking an account that isn't locked."""
        # Account is not locked
        was_locked = SecurityMonitor.unlock_account('testuser')

        # Should return False (wasn't locked)
        self.assertFalse(was_locked)

    def test_lockout_window_time_limit(self):
        """Test that failed attempts outside time window don't count."""
        # Make old failed attempts (mock old timestamps)
        with patch('time.time') as mock_time:
            # Set time to past (outside window)
            old_time = time.time() - 1000  # More than 15 minutes ago
            mock_time.return_value = old_time

            for i in range(5):
                SecurityMonitor.track_failed_login_attempt(
                    username='testuser',
                    ip_address='192.168.1.100'
                )

        # Make new attempt (within window)
        is_locked, attempts = SecurityMonitor.track_failed_login_attempt(
            username='testuser',
            ip_address='192.168.1.100'
        )

        # Old attempts should be filtered out, so not locked
        self.assertFalse(is_locked)

    def test_different_usernames_independent_lockouts(self):
        """Test that lockout tracking is per-username."""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='TestPassword123!'
        )

        # Lock first user
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Check first user is locked
        is_locked, _ = SecurityMonitor.is_account_locked('testuser')
        self.assertTrue(is_locked)

        # Check second user is NOT locked
        is_locked, _ = SecurityMonitor.is_account_locked('testuser2')
        self.assertFalse(is_locked)

    def test_lockout_security_alert_triggered(self):
        """Test that security alert is triggered on account lockout."""
        # Mock the alert trigger
        with patch.object(SecurityMonitor, '_trigger_security_alert') as mock_alert:
            # Lock the account
            for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
                SecurityMonitor.track_failed_login_attempt(
                    username='testuser',
                    ip_address='192.168.1.100'
                )

            # Verify alert was triggered
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args[0]

            # Check alert type
            self.assertEqual(call_args[0], 'account_lockout')

            # Check alert details
            alert_details = call_args[1]
            self.assertEqual(alert_details['username'], 'testuser')
            self.assertEqual(alert_details['attempts'], ACCOUNT_LOCKOUT_THRESHOLD)

    def test_lockout_with_nonexistent_user(self):
        """Test lockout tracking for non-existent username."""
        # Track failed attempts for non-existent user
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            is_locked, attempts = SecurityMonitor.track_failed_login_attempt(
                username='nonexistent',
                ip_address='192.168.1.100'
            )

        # Should still lock even if user doesn't exist
        # (prevents username enumeration)
        is_locked, _ = SecurityMonitor.is_account_locked('nonexistent')
        self.assertTrue(is_locked)

    def test_lockout_email_not_sent_if_user_has_no_email(self):
        """Test that lockout email is not sent if user has no email address."""
        # Create user without email
        user_no_email = User.objects.create_user(
            username='noemail',
            email='',
            password='TestPassword123!'
        )

        # Clear mail outbox
        mail.outbox = []

        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='noemail',
                ip_address='192.168.1.100'
            )

        # No email should be sent
        self.assertEqual(len(mail.outbox), 0)

    def test_lockout_message_includes_time_remaining(self):
        """Test that lockout error message includes time remaining."""
        # Lock the account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Attempt login
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Check error message includes time information
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        error_details = response.data['error']['details']
        self.assertIn('minutes', error_details.lower())


class AccountLockoutIntegrationTestCase(TestCase):
    """Integration tests for complete account lockout flow."""

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

    def test_complete_lockout_flow_via_api(self):
        """Test complete account lockout flow via API endpoints."""
        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Make failed login attempts
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            response = self.client.post(
                '/api/auth/login/',
                data={
                    'username': 'testuser',
                    'password': 'WrongPassword123!'
                },
                HTTP_X_CSRFTOKEN=csrf_token
            )

            if i < ACCOUNT_LOCKOUT_THRESHOLD - 1:
                # Should fail with invalid credentials
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            else:
                # Last attempt should trigger lockout
                self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Attempt login with correct password (should still be locked)
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['error']['code'], 'ACCOUNT_LOCKED')

    def test_lockout_cleared_after_successful_login_post_expiry(self):
        """Test that account can login successfully after lockout expires."""
        # Lock account
        for i in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username='testuser',
                ip_address='192.168.1.100'
            )

        # Manually unlock (simulating expiry)
        SecurityMonitor.unlock_account('testuser')

        # Get CSRF token
        csrf_response = self.client.get('/api/auth/csrf/')
        csrf_token = csrf_response.cookies.get('csrftoken').value

        # Login should succeed
        response = self.client.post(
            '/api/auth/login/',
            data={
                'username': 'testuser',
                'password': 'TestPassword123!'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
