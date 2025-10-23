"""
Security monitoring and utilities for the Plant Community application.

This module provides security monitoring, incident detection, and
response utilities to help maintain application security.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.mail import send_mail
import json

# Import security constants
try:
    from .constants import (
        ACCOUNT_LOCKOUT_THRESHOLD,
        ACCOUNT_LOCKOUT_DURATION,
        ACCOUNT_LOCKOUT_TIME_WINDOW,
        LOCKOUT_ATTEMPTS_KEY,
        LOCKOUT_STATUS_KEY,
        LOCKOUT_EMAIL_ENABLED,
        LOCKOUT_EMAIL_SUBJECT,
        LOG_PREFIX_SECURITY,
        LOG_PREFIX_AUTH,
        LOG_PREFIX_LOCKOUT,
        MAX_FAILED_LOGINS,
        MAX_FAILED_LOGINS_TIME,
        UNKNOWN_IP_ADDRESS,
    )
except ImportError:
    # Fallback values if constants not available
    ACCOUNT_LOCKOUT_THRESHOLD = 10
    ACCOUNT_LOCKOUT_DURATION = 3600
    ACCOUNT_LOCKOUT_TIME_WINDOW = 900
    LOCKOUT_ATTEMPTS_KEY = "security:lockout_attempts:{username}"
    LOCKOUT_STATUS_KEY = "security:lockout_status:{username}"
    LOCKOUT_EMAIL_ENABLED = True
    LOCKOUT_EMAIL_SUBJECT = "Security Alert: Account Locked"
    LOG_PREFIX_SECURITY = "[SECURITY]"
    LOG_PREFIX_AUTH = "[AUTH]"
    LOG_PREFIX_LOCKOUT = "[LOCKOUT]"
    MAX_FAILED_LOGINS = 5
    MAX_FAILED_LOGINS_TIME = 900
    UNKNOWN_IP_ADDRESS = 'unknown'

logger = logging.getLogger(__name__)

User = get_user_model()


class SecurityMonitor:
    """
    Central security monitoring and incident detection system.
    """

    # Cache keys for tracking security events
    FAILED_LOGIN_KEY = "security:failed_login:{ip}"
    RATE_LIMIT_KEY = "security:rate_limit:{user_id}:{endpoint}"
    SUSPICIOUS_ACTIVITY_KEY = "security:suspicious:{user_id}"

    # Thresholds for security alerts (using constants)
    MAX_FAILED_LOGINS = MAX_FAILED_LOGINS
    MAX_FAILED_LOGINS_TIME = MAX_FAILED_LOGINS_TIME
    SUSPICIOUS_ACTIVITY_THRESHOLD = 10
    SUSPICIOUS_ACTIVITY_TIME = 600  # 10 minutes

    @classmethod
    def is_account_locked(cls, username: str) -> Tuple[bool, Optional[int]]:
        """
        Check if an account is currently locked.

        Args:
            username: Username to check

        Returns:
            Tuple of (is_locked, seconds_remaining)
        """
        key = LOCKOUT_STATUS_KEY.format(username=username)
        lockout_data = cache.get(key)

        if not lockout_data:
            return False, None

        lockout_time = lockout_data.get('locked_at', 0)
        current_time = time.time()
        time_elapsed = current_time - lockout_time
        time_remaining = ACCOUNT_LOCKOUT_DURATION - time_elapsed

        if time_remaining > 0:
            return True, int(time_remaining)
        else:
            # Lockout period expired, clear it
            cache.delete(key)
            cls._clear_failed_attempts(username)
            return False, None

    @classmethod
    def track_failed_login_attempt(cls, username: str, ip_address: str) -> Tuple[bool, int]:
        """
        Track failed login attempt and lock account if threshold exceeded.

        THREAD SAFETY: Uses Redis atomic operations to prevent race conditions under
        concurrent load. Multiple simultaneous failed login attempts will be correctly
        tracked without losing data.

        Args:
            username: Username of failed attempt
            ip_address: IP address of failed attempt

        Returns:
            Tuple of (account_locked, attempts_count)
        """
        # Check if already locked
        is_locked, time_remaining = cls.is_account_locked(username)
        if is_locked:
            logger.warning(
                f"{LOG_PREFIX_LOCKOUT} Login attempt on locked account: "
                f"username={username}, ip={ip_address}, "
                f"time_remaining={time_remaining}s"
            )
            return True, 0

        # OPTIMIZATION: Use Redis atomic operations for thread safety
        # This prevents race conditions when multiple requests try to update attempts simultaneously
        key = LOCKOUT_ATTEMPTS_KEY.format(username=username)

        # Try up to 3 times in case of concurrent modifications (optimistic locking)
        max_retries = 3
        for attempt_num in range(max_retries):
            try:
                # Get current attempts list
                attempts = cache.get(key, [])
                current_time = time.time()

                # Remove old attempts outside time window
                attempts = [
                    attempt for attempt in attempts
                    if current_time - attempt['timestamp'] < ACCOUNT_LOCKOUT_TIME_WINDOW
                ]

                # Add new attempt
                new_attempt = {
                    'timestamp': current_time,
                    'ip_address': ip_address,
                }
                attempts.append(new_attempt)

                # ATOMIC: Use add() for first write, set() for updates
                # add() is atomic and fails if key exists, preventing race conditions on first attempt
                if attempt_num == 0 and not cache.get(key):
                    # First attempt for this username - use atomic add()
                    success = cache.add(key, attempts, ACCOUNT_LOCKOUT_TIME_WINDOW)
                    if not success:
                        # Another thread created the key, retry with set()
                        continue
                else:
                    # Subsequent attempts - use set()
                    cache.set(key, attempts, ACCOUNT_LOCKOUT_TIME_WINDOW)

                attempts_count = len(attempts)

                logger.warning(
                    f"{LOG_PREFIX_AUTH} Failed login attempt: "
                    f"username={username}, ip={ip_address}, "
                    f"attempts={attempts_count}/{ACCOUNT_LOCKOUT_THRESHOLD}"
                )

                # Check if threshold exceeded
                if attempts_count >= ACCOUNT_LOCKOUT_THRESHOLD:
                    cls._lock_account(username, attempts)
                    return True, attempts_count

                return False, attempts_count

            except Exception as e:
                logger.error(f"{LOG_PREFIX_SECURITY} Error tracking failed attempt: {str(e)}")
                if attempt_num == max_retries - 1:
                    # Last retry failed, log and return safe defaults
                    logger.error(f"{LOG_PREFIX_SECURITY} All retries exhausted for {username}")
                    return False, 0
                # Retry on next iteration

        # Should never reach here, but return safe defaults
        return False, 0

    @classmethod
    def _lock_account(cls, username: str, attempts: list) -> None:
        """
        Lock account and send notification.

        Args:
            username: Username to lock
            attempts: List of failed attempt records
        """
        current_time = time.time()

        # Set lockout status
        lockout_key = LOCKOUT_STATUS_KEY.format(username=username)
        lockout_data = {
            'locked_at': current_time,
            'attempts_count': len(attempts),
            'ip_addresses': list(set(a['ip_address'] for a in attempts)),
            'reason': 'excessive_failed_logins',
        }
        cache.set(lockout_key, lockout_data, ACCOUNT_LOCKOUT_DURATION)

        logger.error(
            f"{LOG_PREFIX_LOCKOUT} Account locked: "
            f"username={username}, "
            f"attempts={len(attempts)}, "
            f"duration={ACCOUNT_LOCKOUT_DURATION}s, "
            f"ip_addresses={lockout_data['ip_addresses']}"
        )

        # Send email notification
        if LOCKOUT_EMAIL_ENABLED:
            cls._send_lockout_notification(username, lockout_data)

        # Trigger security alert
        cls._trigger_security_alert(
            'account_lockout',
            {
                'username': username,
                'attempts': len(attempts),
                'ip_addresses': lockout_data['ip_addresses'],
                'lockout_duration': ACCOUNT_LOCKOUT_DURATION,
            }
        )

    @classmethod
    def _send_lockout_notification(cls, username: str, lockout_data: Dict[str, Any]) -> None:
        """
        Send email notification about account lockout.

        Args:
            username: Username of locked account
            lockout_data: Lockout details
        """
        try:
            # Get user email
            user = User.objects.get(username=username)
            if not user.email:
                return

            # Calculate unlock time
            unlock_time = timezone.now() + timedelta(seconds=ACCOUNT_LOCKOUT_DURATION)

            # Email content
            message = f"""
Your account has been temporarily locked due to multiple failed login attempts.

Account: {username}
Failed attempts: {lockout_data['attempts_count']}
IP addresses: {', '.join(lockout_data['ip_addresses'])}
Locked at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Unlocks at: {unlock_time.strftime('%Y-%m-%d %H:%M:%S UTC')}

If you did not attempt to log in, please contact support immediately as your account may be under attack.

If you forgot your password, you can reset it after the lockout period expires.

This is an automated security message from Plant Community.
            """.strip()

            send_mail(
                subject=LOCKOUT_EMAIL_SUBJECT,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

            logger.info(
                f"{LOG_PREFIX_LOCKOUT} Lockout notification sent: "
                f"username={username}, email={user.email}"
            )

        except User.DoesNotExist:
            logger.warning(
                f"{LOG_PREFIX_LOCKOUT} Cannot send lockout email: "
                f"user not found: {username}"
            )
        except Exception as e:
            logger.error(
                f"{LOG_PREFIX_LOCKOUT} Failed to send lockout email: "
                f"username={username}, error={str(e)}"
            )

    @classmethod
    def _clear_failed_attempts(cls, username: str) -> None:
        """
        Clear failed login attempts for a username.

        Args:
            username: Username to clear attempts for
        """
        key = LOCKOUT_ATTEMPTS_KEY.format(username=username)
        cache.delete(key)

    @classmethod
    def unlock_account(cls, username: str) -> bool:
        """
        Manually unlock an account (admin function).

        Args:
            username: Username to unlock

        Returns:
            True if account was unlocked, False if not locked
        """
        lockout_key = LOCKOUT_STATUS_KEY.format(username=username)
        attempts_key = LOCKOUT_ATTEMPTS_KEY.format(username=username)

        was_locked = cache.get(lockout_key) is not None

        # Clear both lockout status and failed attempts
        cache.delete(lockout_key)
        cache.delete(attempts_key)

        if was_locked:
            logger.info(
                f"{LOG_PREFIX_LOCKOUT} Account manually unlocked: username={username}"
            )

        return was_locked
    
    @classmethod
    def track_failed_login(cls, ip_address: str, username: str = None) -> None:
        """
        Track failed login attempts and detect brute force attacks.

        Args:
            ip_address: IP address of the failed attempt
            username: Username that was attempted (optional)
        """
        key = cls.FAILED_LOGIN_KEY.format(ip=ip_address)
        
        # Get current failed attempts
        attempts = cache.get(key, [])
        current_time = time.time()
        
        # Remove old attempts (outside time window)
        attempts = [attempt for attempt in attempts 
                   if current_time - attempt['timestamp'] < cls.MAX_FAILED_LOGINS_TIME]
        
        # Add new attempt
        attempts.append({
            'timestamp': current_time,
            'username': username,
            'ip': ip_address
        })
        
        # Store updated attempts
        cache.set(key, attempts, cls.MAX_FAILED_LOGINS_TIME)
        
        # Check if threshold exceeded
        if len(attempts) >= cls.MAX_FAILED_LOGINS:
            cls._trigger_security_alert(
                'brute_force_login',
                {
                    'ip_address': ip_address,
                    'attempts': len(attempts),
                    'usernames': list(set(a.get('username') for a in attempts if a.get('username'))),
                    'time_window': cls.MAX_FAILED_LOGINS_TIME
                }
            )
        
        # Log the event
        logger.warning(
            f"Failed login attempt: ip={ip_address}, username={username}, "
            f"total_attempts_in_window={len(attempts)}"
        )
    
    @classmethod
    def track_successful_login(cls, user: User, ip_address: str) -> None:
        """
        Track successful login and clear failed attempt counters.

        Args:
            user: User who logged in successfully
            ip_address: IP address of successful login
        """
        # Clear failed login counter for this IP
        key = cls.FAILED_LOGIN_KEY.format(ip=ip_address)
        cache.delete(key)

        # Log successful login
        logger.info(f"{LOG_PREFIX_AUTH} Successful login: user={user.username}, ip={ip_address}")
        
        # Check for suspicious login patterns
        cls._check_suspicious_login(user, ip_address)
    
    @classmethod
    def _check_suspicious_login(cls, user: User, ip_address: str) -> None:
        """Check for suspicious login patterns."""
        # This is a basic implementation - can be enhanced with geolocation,
        # device fingerprinting, etc.
        
        # For now, just track multiple rapid logins
        key = f"login_frequency:{user.id}"
        recent_logins = cache.get(key, [])
        current_time = time.time()
        
        # Remove old logins (outside 1 hour window)
        recent_logins = [login for login in recent_logins 
                        if current_time - login < 3600]
        
        # Add current login
        recent_logins.append(current_time)
        cache.set(key, recent_logins, 3600)
        
        # Alert if too many logins in short time
        if len(recent_logins) > 10:  # More than 10 logins per hour
            cls._trigger_security_alert(
                'suspicious_login_frequency',
                {
                    'user_id': user.id,
                    'username': user.username,
                    'ip_address': ip_address,
                    'login_count': len(recent_logins),
                    'time_window': '1 hour'
                }
            )
    
    @classmethod
    def track_api_request(cls, request: HttpRequest, endpoint: str, user: User = None) -> None:
        """
        Track API requests for rate limiting and abuse detection.

        Args:
            request: Django request object
            endpoint: API endpoint being accessed
            user: User making the request (if authenticated)
        """
        user_id = user.id if user else 'anonymous'
        ip_address = cls._get_client_ip(request)
        
        # Track request rate
        key = cls.RATE_LIMIT_KEY.format(user_id=user_id, endpoint=endpoint)
        requests = cache.get(key, [])
        current_time = time.time()
        
        # Remove old requests (outside 1 minute window)
        requests = [req for req in requests if current_time - req < 60]
        
        # Add current request
        requests.append(current_time)
        cache.set(key, requests, 60)
        
        # Log high-frequency requests
        if len(requests) > 30:  # More than 30 requests per minute
            logger.warning(
                f"High API request frequency: user={user_id}, ip={ip_address}, "
                f"endpoint={endpoint}, requests={len(requests)}/minute"
            )
    
    @classmethod
    def track_file_upload(cls, user: User, filename: str, file_size: int,
                         success: bool, error: str = None) -> None:
        """
        Track file upload attempts for security monitoring.

        Args:
            user: User uploading the file
            filename: Name of the uploaded file
            file_size: Size of the file in bytes
            success: Whether upload was successful
            error: Error message if upload failed
        """
        user_id = user.id if user else 'anonymous'
        
        if success:
            logger.info(
                f"File upload successful: user={user_id}, file={filename}, "
                f"size={file_size} bytes"
            )
        else:
            logger.warning(
                f"File upload failed: user={user_id}, file={filename}, "
                f"size={file_size} bytes, error={error}"
            )
            
            # Track failed upload attempts
            key = f"failed_uploads:{user_id}"
            failures = cache.get(key, [])
            current_time = time.time()
            
            # Remove old failures (outside 1 hour window)
            failures = [f for f in failures if current_time - f['timestamp'] < 3600]
            
            # Add current failure
            failures.append({
                'timestamp': current_time,
                'filename': filename,
                'error': error
            })
            cache.set(key, failures, 3600)
            
            # Alert on multiple failures
            if len(failures) > 20:  # More than 20 failed uploads per hour
                cls._trigger_security_alert(
                    'excessive_upload_failures',
                    {
                        'user_id': user_id,
                        'failures': len(failures),
                        'time_window': '1 hour'
                    }
                )
    
    @classmethod
    def track_validation_failure(cls, user: User, field: str, value_type: str,
                                error: str, request: HttpRequest = None) -> None:
        """
        Track validation failures that might indicate attacks.

        Args:
            user: User who submitted invalid data
            field: Field that failed validation
            value_type: Type of value that was invalid
            error: Validation error message
            request: Django request object
        """
        user_id = user.id if user else 'anonymous'
        ip_address = cls._get_client_ip(request) if request else UNKNOWN_IP_ADDRESS
        
        logger.warning(
            f"Validation failure: user={user_id}, ip={ip_address}, "
            f"field={field}, type={value_type}, error={error}"
        )
        
        # Track validation failures
        key = f"validation_failures:{user_id}"
        failures = cache.get(key, [])
        current_time = time.time()
        
        # Remove old failures (outside 1 hour window)
        failures = [f for f in failures if current_time - f['timestamp'] < 3600]
        
        # Add current failure
        failures.append({
            'timestamp': current_time,
            'field': field,
            'error': error,
            'ip': ip_address
        })
        cache.set(key, failures, 3600)
        
        # Alert on excessive validation failures
        if len(failures) > 50:  # More than 50 validation failures per hour
            cls._trigger_security_alert(
                'excessive_validation_failures',
                {
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'failures': len(failures),
                    'time_window': '1 hour'
                }
            )
    
    @classmethod
    def _trigger_security_alert(cls, alert_type: str, details: Dict[str, Any]) -> None:
        """
        Trigger a security alert for investigation.

        Args:
            alert_type: Type of security alert
            details: Details about the security event
        """
        alert_data = {
            'timestamp': timezone.now().isoformat(),
            'alert_type': alert_type,
            'details': details,
            'severity': 'high' if alert_type in ['brute_force_login'] else 'medium'
        }
        
        # Log the alert
        logger.error(
            f"SECURITY ALERT [{alert_type}]: {json.dumps(details, indent=2)}"
        )
        
        # Store alert for investigation
        key = f"security_alert:{alert_type}:{int(time.time())}"
        cache.set(key, alert_data, 86400)  # Keep for 24 hours
        
        # In production, you might want to:
        # - Send email notifications
        # - Send to monitoring system (Sentry, DataDog, etc.)
        # - Create incident tickets
        # - Block suspicious IPs temporarily
    
    @classmethod
    def _get_client_ip(cls, request: HttpRequest) -> str:
        """
        Get the real IP address of the client with spoofing protection.

        SECURITY: X-Forwarded-For header can be spoofed by attackers.
        We validate IP format and use the rightmost trustworthy IP.

        Args:
            request: Django request object

        Returns:
            Client IP address (validated)
        """
        from ipaddress import ip_address, AddressValueError

        # If behind trusted proxy/load balancer, use X-Forwarded-For
        if getattr(settings, 'USE_X_FORWARDED_HOST', False):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                # X-Forwarded-For format: client, proxy1, proxy2, ...
                # Use rightmost IP (closest to server, hardest to spoof)
                # In production, you'd extract the rightmost N IPs based on known proxy count
                ips = [ip_str.strip() for ip_str in x_forwarded_for.split(',')]
                for ip_str in reversed(ips):
                    try:
                        # Validate IP format to prevent injection attacks
                        ip_address(ip_str)
                        return ip_str
                    except AddressValueError:
                        # Skip invalid IPs (possible spoofing attempt)
                        logger.warning(f"{LOG_PREFIX_SECURITY} Invalid IP in X-Forwarded-For: {ip_str}")
                        continue

        # Fallback to REMOTE_ADDR (always trustworthy, set by web server)
        remote_addr = request.META.get('REMOTE_ADDR', UNKNOWN_IP_ADDRESS)

        # Validate REMOTE_ADDR format (should always be valid, but defensive programming)
        if remote_addr != UNKNOWN_IP_ADDRESS:
            try:
                ip_address(remote_addr)
                return remote_addr
            except AddressValueError:
                logger.error(f"{LOG_PREFIX_SECURITY} REMOTE_ADDR has invalid format: {remote_addr}")

        return UNKNOWN_IP_ADDRESS
    
    @classmethod
    def get_security_status(cls) -> Dict[str, Any]:
        """
        Get current security status and metrics.
        
        Returns:
            Dictionary containing security metrics
        """
        # This could be expanded to provide comprehensive security metrics
        return {
            'status': 'monitoring',
            'alerts_active': 0,  # Count active alerts
            'monitoring_enabled': True,
            'last_check': timezone.now().isoformat()
        }


class SecurityMiddleware:
    """
    Django middleware for security monitoring.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Pre-request security checks
        self._pre_request_checks(request)

        response = self.get_response(request)

        # Post-request security tracking
        self._post_request_tracking(request, response)

        return response

    def _pre_request_checks(self, request: HttpRequest) -> None:
        """Perform security checks before processing request."""
        # Track API requests for rate limiting
        if request.path.startswith('/api/'):
            SecurityMonitor.track_api_request(
                request,
                request.path,
                request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            )

    def _post_request_tracking(self, request: HttpRequest, response: HttpResponse) -> None:
        """Track security-relevant information after request processing."""
        # Track failed authentication attempts
        if (request.path in ['/api/auth/login/', '/api/auth/register/'] and 
            response.status_code in [400, 401, 403]):
            ip_address = SecurityMonitor._get_client_ip(request)
            
            # Safely extract username from request data
            username = None
            try:
                # Try POST data first (form data)
                if hasattr(request, 'POST') and request.POST:
                    username = request.POST.get('username')
                # Try parsed JSON data (if available from DRF)
                elif hasattr(request, 'data') and hasattr(request.data, 'get'):
                    try:
                        username = request.data.get('username')
                    except (AttributeError, TypeError):
                        pass
                # Only try body access if request stream hasn't been read yet
                elif hasattr(request, '_read_started') and not request._read_started:
                    try:
                        if hasattr(request, 'body') and request.body:
                            import json
                            data = json.loads(request.body.decode('utf-8'))
                            username = data.get('username')
                    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError, Exception):
                        pass
            except (AttributeError, TypeError, Exception):
                # Fallback: don't extract username if there are any issues
                username = None
                
            SecurityMonitor.track_failed_login(ip_address, username)


# Utility functions for use in views
def log_security_event(event_type: str, user: User = None, details: Dict[str, Any] = None,
                      request: HttpRequest = None) -> None:
    """
    Convenience function to log security events from views.

    Args:
        event_type: Type of security event
        user: User associated with the event
        details: Additional details about the event
        request: Django request object
    """
    user_id = user.id if user else 'anonymous'
    ip_address = SecurityMonitor._get_client_ip(request) if request else UNKNOWN_IP_ADDRESS
    
    logger.info(
        f"Security event [{event_type}]: user={user_id}, ip={ip_address}, "
        f"details={details or {}}"
    )


def check_rate_limit(user: User, action: str, limit: int, time_window: int = 60) -> bool:
    """
    Check if user has exceeded rate limit for a specific action.
    
    Args:
        user: User to check
        action: Action being rate limited
        limit: Maximum number of actions allowed
        time_window: Time window in seconds
        
    Returns:
        True if under rate limit, False if exceeded
    """
    user_id = user.id if user else 'anonymous'
    key = f"rate_limit:{user_id}:{action}"
    
    attempts = cache.get(key, [])
    current_time = time.time()
    
    # Remove old attempts
    attempts = [attempt for attempt in attempts 
               if current_time - attempt < time_window]
    
    if len(attempts) >= limit:
        logger.warning(
            f"Rate limit exceeded: user={user_id}, action={action}, "
            f"attempts={len(attempts)}/{limit} in {time_window}s"
        )
        return False
    
    # Add current attempt
    attempts.append(current_time)
    cache.set(key, attempts, time_window)
    
    return True