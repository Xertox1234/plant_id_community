"""
PII-Safe Logging Utilities

GDPR-compliant logging helpers that hash/pseudonymize personally identifiable information (PII).
This module ensures logs do not contain raw usernames, emails, or IP addresses.

Usage:
    from apps.core.utils.pii_safe_logging import log_safe_username, log_safe_email, log_safe_ip

    logger.info(f"User logged in: {log_safe_username(user.username)}")
    logger.info(f"Email sent to: {log_safe_email(user.email)}")
    logger.info(f"Request from: {log_safe_ip(request.META.get('REMOTE_ADDR'))}")
"""

import hashlib
from typing import Optional


def log_safe_username(username: Optional[str]) -> str:
    """
    Create a GDPR-compliant pseudonymized username for logging.

    Shows first 3 characters + hash suffix for debugging while protecting PII.

    Args:
        username: The username to pseudonymize

    Returns:
        Pseudonymized username (e.g., "joh***a1b2c3d4")

    Example:
        >>> log_safe_username("johndoe123")
        "joh***a1b2c3d4"
    """
    if not username:
        return "unknown***00000000"

    try:
        hash_suffix = hashlib.sha256(username.encode()).hexdigest()[:8]
        prefix = username[:3] if len(username) >= 3 else username
        return f"{prefix}***{hash_suffix}"
    except Exception:
        return "error***00000000"


def log_safe_email(email: Optional[str]) -> str:
    """
    Create a GDPR-compliant pseudonymized email for logging.

    NEVER logs the actual email address. Shows only a hash for correlation.

    Args:
        email: The email address to pseudonymize

    Returns:
        Hash-only representation (e.g., "email:a1b2c3d4")

    Example:
        >>> log_safe_email("user@example.com")
        "email:a1b2c3d4"
    """
    if not email:
        return "email:00000000"

    try:
        hash_value = hashlib.sha256(email.encode()).hexdigest()[:8]
        return f"email:{hash_value}"
    except Exception:
        return "email:00000000"


def log_safe_ip(ip_address: Optional[str]) -> str:
    """
    Create a GDPR-compliant pseudonymized IP address for logging.

    IPv4: Shows first 2 octets + hash (e.g., "192.168.***:a1b2c3d4")
    IPv6: Shows first 16 chars + hash (e.g., "2001:0db8:85a3:***:a1b2c3d4")

    Args:
        ip_address: The IP address to pseudonymize

    Returns:
        Pseudonymized IP address

    Example:
        >>> log_safe_ip("192.168.1.100")
        "192.168.***:a1b2c3d4"
        >>> log_safe_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        "2001:0db8:85a3:***:a1b2c3d4"
    """
    if not ip_address:
        return "ip:unknown***00000000"

    try:
        hash_suffix = hashlib.sha256(ip_address.encode()).hexdigest()[:8]

        # IPv4: Show first 2 octets
        if '.' in ip_address and ':' not in ip_address:
            parts = ip_address.split('.')
            if len(parts) >= 2:
                prefix = f"{parts[0]}.{parts[1]}"
                return f"{prefix}.***:{hash_suffix}"

        # IPv6: Show first 16 characters
        elif ':' in ip_address:
            prefix = ip_address[:16] if len(ip_address) >= 16 else ip_address
            return f"{prefix}***:{hash_suffix}"

        # Fallback: just hash
        return f"ip:{hash_suffix}"
    except Exception:
        return "ip:error***00000000"


def log_safe_user_context(user, include_email: bool = False) -> str:
    """
    Create a GDPR-compliant user context string for logging.

    Args:
        user: Django User object
        include_email: Whether to include pseudonymized email (default: False)

    Returns:
        Safe user context string

    Example:
        >>> log_safe_user_context(user)
        "user:joh***a1b2c3d4"
        >>> log_safe_user_context(user, include_email=True)
        "user:joh***a1b2c3d4 (email:b2c3d4e5)"
    """
    if not user:
        return "user:anonymous"

    safe_username = log_safe_username(getattr(user, 'username', None))

    if include_email and hasattr(user, 'email'):
        safe_email = log_safe_email(user.email)
        return f"user:{safe_username} ({safe_email})"

    return f"user:{safe_username}"
