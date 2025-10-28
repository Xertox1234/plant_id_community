#!/usr/bin/env python
"""
Simple test script to verify PII-safe logging utilities work correctly.
This bypasses Django's test framework configuration issues.
"""

import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the PII-safe logging utilities directly
from apps.core.utils.pii_safe_logging import (
    log_safe_username,
    log_safe_email,
    log_safe_ip,
    log_safe_user_context,
)


def test_username_logging():
    """Test username pseudonymization"""
    print("Testing username logging...")

    # Test normal username
    result = log_safe_username("johndoe123")
    assert result.startswith("joh***"), f"Expected prefix 'joh***', got: {result}"
    assert "johndoe123" not in result, "Raw username should not appear in result"
    print(f"  ✓ Normal username: {result}")

    # Test empty username
    result = log_safe_username("")
    assert result == "unknown***00000000", f"Expected 'unknown***00000000', got: {result}"
    print(f"  ✓ Empty username: {result}")

    # Test None username
    result = log_safe_username(None)
    assert result == "unknown***00000000", f"Expected 'unknown***00000000', got: {result}"
    print(f"  ✓ None username: {result}")

    # Test consistency
    result1 = log_safe_username("testuser")
    result2 = log_safe_username("testuser")
    assert result1 == result2, "Same username should produce same hash"
    print(f"  ✓ Consistent hashing: {result1}")

    print("  All username tests passed! ✅\n")


def test_email_logging():
    """Test email pseudonymization"""
    print("Testing email logging...")

    # Test normal email
    result = log_safe_email("user@example.com")
    assert result.startswith("email:"), f"Expected prefix 'email:', got: {result}"
    assert "user@example.com" not in result, "Raw email should not appear in result"
    assert "example.com" not in result, "Domain should not appear in result"
    print(f"  ✓ Normal email: {result}")

    # Test empty email
    result = log_safe_email("")
    assert result == "email:00000000", f"Expected 'email:00000000', got: {result}"
    print(f"  ✓ Empty email: {result}")

    # Test None email
    result = log_safe_email(None)
    assert result == "email:00000000", f"Expected 'email:00000000', got: {result}"
    print(f"  ✓ None email: {result}")

    print("  All email tests passed! ✅\n")


def test_ip_logging():
    """Test IP address pseudonymization"""
    print("Testing IP address logging...")

    # Test IPv4
    result = log_safe_ip("192.168.1.100")
    assert result.startswith("192.168.***:"), f"Expected prefix '192.168.***:', got: {result}"
    assert "192.168.1.100" not in result, "Full IP should not appear in result"
    print(f"  ✓ IPv4 address: {result}")

    # Test IPv6
    result = log_safe_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert "2001:0db8:85a3:" in result, f"Expected IPv6 prefix, got: {result}"
    assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" not in result, "Full IP should not appear"
    print(f"  ✓ IPv6 address: {result}")

    # Test localhost
    result = log_safe_ip("127.0.0.1")
    assert result.startswith("127.0.***:"), f"Expected prefix '127.0.***:', got: {result}"
    print(f"  ✓ Localhost IPv4: {result}")

    # Test empty IP
    result = log_safe_ip("")
    assert result == "ip:unknown***00000000", f"Expected 'ip:unknown***00000000', got: {result}"
    print(f"  ✓ Empty IP: {result}")

    print("  All IP tests passed! ✅\n")


def test_gdpr_compliance():
    """Test GDPR compliance"""
    print("Testing GDPR compliance...")

    # Test that no raw PII appears in logs
    username = "sensitive_user_123"
    email = "sensitive@private.com"
    ip = "203.0.113.195"

    username_result = log_safe_username(username)
    email_result = log_safe_email(email)
    ip_result = log_safe_ip(ip)

    assert username not in username_result, "Raw username must not appear"
    assert email not in email_result, "Raw email must not appear"
    assert "sensitive" not in email_result, "Email local part must not appear"
    assert "private.com" not in email_result, "Email domain must not appear"
    assert ip not in ip_result, "Full IP must not appear"

    print(f"  ✓ No raw username: {username_result}")
    print(f"  ✓ No raw email: {email_result}")
    print(f"  ✓ No full IP: {ip_result}")
    print("  All GDPR compliance tests passed! ✅\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("PII-Safe Logging Utility Tests")
    print("=" * 60)
    print()

    try:
        test_username_logging()
        test_email_logging()
        test_ip_logging()
        test_gdpr_compliance()

        print("=" * 60)
        print("All tests passed! ✅")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
