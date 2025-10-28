"""
Tests for PII-Safe Logging Utilities

Tests GDPR compliance and proper pseudonymization of PII data.
"""

from django.test import TestCase
from apps.core.utils.pii_safe_logging import (
    log_safe_username,
    log_safe_email,
    log_safe_ip,
    log_safe_user_context,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class LogSafeUsernameTests(TestCase):
    """Test username pseudonymization"""

    def test_normal_username(self):
        """Test pseudonymization of normal username"""
        result = log_safe_username("johndoe123")
        self.assertTrue(result.startswith("joh***"))
        self.assertEqual(len(result), 14)  # "joh***" + 8 char hash

    def test_short_username(self):
        """Test pseudonymization of short username (< 3 chars)"""
        result = log_safe_username("ab")
        self.assertTrue(result.startswith("ab***"))

    def test_empty_username(self):
        """Test pseudonymization of empty username"""
        result = log_safe_username("")
        self.assertEqual(result, "unknown***00000000")

    def test_none_username(self):
        """Test pseudonymization of None username"""
        result = log_safe_username(None)
        self.assertEqual(result, "unknown***00000000")

    def test_consistent_hashing(self):
        """Test that same username produces same hash"""
        result1 = log_safe_username("testuser")
        result2 = log_safe_username("testuser")
        self.assertEqual(result1, result2)

    def test_different_hashing(self):
        """Test that different usernames produce different hashes"""
        result1 = log_safe_username("user1")
        result2 = log_safe_username("user2")
        self.assertNotEqual(result1, result2)

    def test_unicode_username(self):
        """Test pseudonymization of unicode username"""
        result = log_safe_username("用户名123")
        self.assertTrue(result.startswith("用户名***"))
        self.assertEqual(len(result), 14)  # 3 chars + "***" + 8 char hash


class LogSafeEmailTests(TestCase):
    """Test email pseudonymization"""

    def test_normal_email(self):
        """Test pseudonymization of normal email"""
        result = log_safe_email("user@example.com")
        self.assertTrue(result.startswith("email:"))
        self.assertEqual(len(result), 14)  # "email:" + 8 char hash
        # Should NOT contain the actual email
        self.assertNotIn("user@example.com", result)
        self.assertNotIn("example.com", result)

    def test_empty_email(self):
        """Test pseudonymization of empty email"""
        result = log_safe_email("")
        self.assertEqual(result, "email:00000000")

    def test_none_email(self):
        """Test pseudonymization of None email"""
        result = log_safe_email(None)
        self.assertEqual(result, "email:00000000")

    def test_consistent_hashing(self):
        """Test that same email produces same hash"""
        result1 = log_safe_email("test@example.com")
        result2 = log_safe_email("test@example.com")
        self.assertEqual(result1, result2)

    def test_different_hashing(self):
        """Test that different emails produce different hashes"""
        result1 = log_safe_email("user1@example.com")
        result2 = log_safe_email("user2@example.com")
        self.assertNotEqual(result1, result2)


class LogSafeIPTests(TestCase):
    """Test IP address pseudonymization"""

    def test_ipv4_address(self):
        """Test pseudonymization of IPv4 address"""
        result = log_safe_ip("192.168.1.100")
        self.assertTrue(result.startswith("192.168.***:"))
        # Should NOT contain the full IP
        self.assertNotIn("192.168.1.100", result)

    def test_ipv6_address(self):
        """Test pseudonymization of IPv6 address"""
        result = log_safe_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        self.assertTrue(result.startswith("2001:0db8:85a3:"))
        self.assertIn("***:", result)
        # Should NOT contain the full IP
        self.assertNotIn("2001:0db8:85a3:0000:0000:8a2e:0370:7334", result)

    def test_localhost_ipv4(self):
        """Test pseudonymization of localhost IPv4"""
        result = log_safe_ip("127.0.0.1")
        self.assertTrue(result.startswith("127.0.***:"))

    def test_localhost_ipv6(self):
        """Test pseudonymization of localhost IPv6"""
        result = log_safe_ip("::1")
        self.assertTrue(result.startswith("::1***:"))

    def test_empty_ip(self):
        """Test pseudonymization of empty IP"""
        result = log_safe_ip("")
        self.assertEqual(result, "ip:unknown***00000000")

    def test_none_ip(self):
        """Test pseudonymization of None IP"""
        result = log_safe_ip(None)
        self.assertEqual(result, "ip:unknown***00000000")

    def test_consistent_hashing(self):
        """Test that same IP produces same hash"""
        result1 = log_safe_ip("10.0.0.1")
        result2 = log_safe_ip("10.0.0.1")
        self.assertEqual(result1, result2)

    def test_different_hashing(self):
        """Test that different IPs produce different hashes"""
        result1 = log_safe_ip("10.0.0.1")
        result2 = log_safe_ip("10.0.0.2")
        self.assertNotEqual(result1, result2)


class LogSafeUserContextTests(TestCase):
    """Test user context pseudonymization"""

    def setUp(self):
        """Create test user"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_user_context_without_email(self):
        """Test user context without email"""
        result = log_safe_user_context(self.user, include_email=False)
        self.assertTrue(result.startswith("user:tes***"))
        # Should NOT contain email
        self.assertNotIn("email:", result)
        self.assertNotIn("test@example.com", result)

    def test_user_context_with_email(self):
        """Test user context with email"""
        result = log_safe_user_context(self.user, include_email=True)
        self.assertTrue(result.startswith("user:tes***"))
        self.assertIn("email:", result)
        # Should NOT contain actual email
        self.assertNotIn("test@example.com", result)

    def test_none_user(self):
        """Test None user context"""
        result = log_safe_user_context(None)
        self.assertEqual(result, "user:anonymous")

    def test_user_without_username(self):
        """Test user object without username attribute"""
        class FakeUser:
            pass

        fake_user = FakeUser()
        result = log_safe_user_context(fake_user)
        self.assertTrue(result.startswith("user:unknown***"))


class GDPRComplianceTests(TestCase):
    """Test GDPR compliance of logging utilities"""

    def test_no_raw_username_in_logs(self):
        """Ensure raw username never appears in logs"""
        username = "johndoe123"
        result = log_safe_username(username)
        # Should NOT contain full username
        self.assertNotIn(username, result)
        # Should contain prefix and hash
        self.assertIn("joh***", result)

    def test_no_raw_email_in_logs(self):
        """Ensure raw email never appears in logs"""
        email = "sensitive@private.com"
        result = log_safe_email(email)
        # Should NOT contain any part of the email
        self.assertNotIn(email, result)
        self.assertNotIn("sensitive", result)
        self.assertNotIn("private.com", result)

    def test_no_full_ip_in_logs(self):
        """Ensure full IP address never appears in logs"""
        ip = "203.0.113.195"
        result = log_safe_ip(ip)
        # Should NOT contain full IP
        self.assertNotIn(ip, result)
        # Should contain partial IP and hash
        self.assertIn("203.0.***:", result)

    def test_hash_correlation_possible(self):
        """Ensure same PII produces same hash for correlation"""
        # Same username should produce same hash across calls
        username = "correlationtest"
        result1 = log_safe_username(username)
        result2 = log_safe_username(username)
        self.assertEqual(result1, result2)

        # Same email should produce same hash
        email = "correlation@test.com"
        result3 = log_safe_email(email)
        result4 = log_safe_email(email)
        self.assertEqual(result3, result4)

        # Same IP should produce same hash
        ip = "192.168.1.1"
        result5 = log_safe_ip(ip)
        result6 = log_safe_ip(ip)
        self.assertEqual(result5, result6)

    def test_different_pii_produces_different_hashes(self):
        """Ensure different PII values produce different hashes"""
        # Different usernames
        self.assertNotEqual(
            log_safe_username("user1"),
            log_safe_username("user2")
        )

        # Different emails
        self.assertNotEqual(
            log_safe_email("user1@test.com"),
            log_safe_email("user2@test.com")
        )

        # Different IPs
        self.assertNotEqual(
            log_safe_ip("192.168.1.1"),
            log_safe_ip("192.168.1.2")
        )
