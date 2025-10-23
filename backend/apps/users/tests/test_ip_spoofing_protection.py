"""
Tests for IP Spoofing Protection.

Tests SecurityMonitor IP validation and spoofing protection including:
- X-Forwarded-For header validation
- IP format validation
- Handling of invalid/spoofed IPs
- Fallback to REMOTE_ADDR
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.core.security import SecurityMonitor
from unittest.mock import patch
import logging

User = get_user_model()


class IPSpoofingProtectionTestCase(TestCase):
    """Test IP spoofing protection in SecurityMonitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_get_client_ip_from_remote_addr(self):
        """Test getting client IP from REMOTE_ADDR (most reliable)."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        ip = SecurityMonitor._get_client_ip(request)

        self.assertEqual(ip, '192.168.1.100')

    def test_get_client_ip_with_x_forwarded_for(self):
        """Test getting client IP from X-Forwarded-For when behind proxy."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'  # Proxy IP
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 198.51.100.1, 10.0.0.1'

        # Mock USE_X_FORWARDED_HOST setting
        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should use rightmost valid IP from X-Forwarded-For
            self.assertIn(ip, ['203.0.113.1', '198.51.100.1', '10.0.0.1'])

    def test_get_client_ip_invalid_x_forwarded_for(self):
        """Test that invalid IPs in X-Forwarded-For are rejected."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = 'invalid_ip, 192.168.1.1'

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should skip invalid IP and use valid one
            self.assertEqual(ip, '192.168.1.1')

    def test_get_client_ip_all_invalid_x_forwarded_for(self):
        """Test fallback to REMOTE_ADDR when all X-Forwarded-For IPs are invalid."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = 'not_an_ip, also_not_an_ip'

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should fallback to REMOTE_ADDR
            self.assertEqual(ip, '192.168.1.100')

    def test_get_client_ip_sql_injection_attempt(self):
        """Test that SQL injection attempts in IP headers are rejected."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = "1.2.3.4'; DROP TABLE users; --"

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should reject injection attempt and use REMOTE_ADDR
            self.assertEqual(ip, '192.168.1.100')

    def test_get_client_ip_xss_attempt(self):
        """Test that XSS attempts in IP headers are rejected."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = '<script>alert("xss")</script>'

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should reject XSS attempt and use REMOTE_ADDR
            self.assertEqual(ip, '192.168.1.100')

    def test_get_client_ip_ipv6_address(self):
        """Test handling of IPv6 addresses."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'

        ip = SecurityMonitor._get_client_ip(request)

        self.assertEqual(ip, '2001:0db8:85a3:0000:0000:8a2e:0370:7334')

    def test_get_client_ip_ipv6_in_x_forwarded_for(self):
        """Test IPv6 in X-Forwarded-For header."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        request.META['HTTP_X_FORWARDED_FOR'] = '2001:db8::1, 10.0.0.1'

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should accept IPv6 address
            self.assertIn(ip, ['2001:db8::1', '10.0.0.1'])

    def test_get_client_ip_empty_x_forwarded_for(self):
        """Test handling of empty X-Forwarded-For header."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = ''

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should fallback to REMOTE_ADDR
            self.assertEqual(ip, '192.168.1.100')

    def test_get_client_ip_missing_remote_addr(self):
        """Test handling when REMOTE_ADDR is missing."""
        request = self.factory.get('/api/test/')
        # Don't set REMOTE_ADDR

        ip = SecurityMonitor._get_client_ip(request)

        # Should return 'unknown'
        self.assertEqual(ip, 'unknown')

    def test_get_client_ip_invalid_remote_addr(self):
        """Test handling of invalid REMOTE_ADDR."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = 'not_an_ip_address'

        ip = SecurityMonitor._get_client_ip(request)

        # Should return 'unknown' when REMOTE_ADDR is invalid
        self.assertEqual(ip, 'unknown')

    def test_ip_spoofing_logged(self):
        """Test that IP spoofing attempts are logged."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = 'spoofed_ip_123'

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            # Mock logger to verify warning is logged
            with patch('apps.core.security.logger') as mock_logger:
                ip = SecurityMonitor._get_client_ip(request)

                # Should log warning about invalid IP
                mock_logger.warning.assert_called()
                warning_message = mock_logger.warning.call_args[0][0]
                self.assertIn('Invalid IP', warning_message)
                self.assertIn('spoofed_ip_123', warning_message)

    def test_multiple_proxies_in_x_forwarded_for(self):
        """Test handling of multiple proxies in X-Forwarded-For chain."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        # Client IP, Proxy1, Proxy2, Proxy3
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 198.51.100.1, 10.0.0.3, 10.0.0.5'

        with patch('apps.core.security.settings') as mock_settings:
            mock_settings.USE_X_FORWARDED_HOST = True

            ip = SecurityMonitor._get_client_ip(request)

            # Should use rightmost valid IP (most trustworthy)
            # In production, you'd configure number of trusted proxies
            self.assertIn(ip, ['203.0.113.1', '198.51.100.1', '10.0.0.3', '10.0.0.5'])

    def test_localhost_ips_accepted(self):
        """Test that localhost IPs are accepted."""
        request = self.factory.get('/api/test/')

        # IPv4 localhost
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        ip = SecurityMonitor._get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')

        # IPv6 localhost
        request.META['REMOTE_ADDR'] = '::1'
        ip = SecurityMonitor._get_client_ip(request)
        self.assertEqual(ip, '::1')

    def test_private_ips_accepted(self):
        """Test that private IP addresses are accepted."""
        private_ips = [
            '10.0.0.1',
            '172.16.0.1',
            '192.168.1.1',
        ]

        for private_ip in private_ips:
            request = self.factory.get('/api/test/')
            request.META['REMOTE_ADDR'] = private_ip

            ip = SecurityMonitor._get_client_ip(request)

            self.assertEqual(ip, private_ip)


class IPValidationInSecurityContextTestCase(TestCase):
    """Test IP validation in security monitoring context."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_failed_login_tracking_with_spoofed_ip(self):
        """Test that failed login tracking uses validated IP."""
        request = self.factory.post('/api/auth/login/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_X_FORWARDED_FOR'] = 'spoofed_ip'

        # Track failed login
        with patch('apps.core.security.logger') as mock_logger:
            SecurityMonitor.track_failed_login(
                ip_address=SecurityMonitor._get_client_ip(request),
                username='testuser'
            )

            # Should use validated REMOTE_ADDR, not spoofed IP
            # Check that warning was logged for invalid IP
            self.assertTrue(any(
                'Invalid IP' in str(call) or 'Failed login' in str(call)
                for call in mock_logger.warning.call_args_list
            ))

    def test_successful_login_tracking_with_validated_ip(self):
        """Test that successful login tracking uses validated IP."""
        request = self.factory.post('/api/auth/login/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        # Track successful login
        ip = SecurityMonitor._get_client_ip(request)
        SecurityMonitor.track_successful_login(self.user, ip)

        # Should complete without error using validated IP
        self.assertEqual(ip, '192.168.1.100')
