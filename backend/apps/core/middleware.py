"""
Custom middleware for the Plant Community application.

This module provides middleware for rate limit monitoring, security tracking,
and other cross-cutting concerns.
"""

import logging
import time
from typing import Optional
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.contrib.auth import get_user_model

# Import constants
try:
    from .constants import (
        RATE_LIMIT_VIOLATION_THRESHOLD,
        RATE_LIMIT_VIOLATION_WINDOW,
        LOG_PREFIX_RATELIMIT,
        LOG_PREFIX_SECURITY,
    )
except ImportError:
    # Fallback values
    RATE_LIMIT_VIOLATION_THRESHOLD = 5
    RATE_LIMIT_VIOLATION_WINDOW = 3600
    LOG_PREFIX_RATELIMIT = "[RATELIMIT]"
    LOG_PREFIX_SECURITY = "[SECURITY]"

logger = logging.getLogger(__name__)

User = get_user_model()


class RateLimitMonitoringMiddleware:
    """
    Middleware to monitor rate limit violations and track suspicious patterns.

    This middleware integrates with django-ratelimit to track when users
    hit rate limits and identify potentially malicious behavior.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and monitor for rate limit violations."""

        # Pre-request processing
        user_id = self._get_user_id(request)
        ip_address = self._get_client_ip(request)
        endpoint = request.path

        # Process the request
        response = self.get_response(request)

        # Post-request processing - check for rate limit violations
        if response.status_code == 429:  # Too Many Requests
            self._track_rate_limit_violation(
                user_id=user_id,
                ip_address=ip_address,
                endpoint=endpoint,
                request=request
            )

        return response

    def _get_user_id(self, request: HttpRequest) -> str:
        """
        Get user ID from request.

        Args:
            request: Django request object

        Returns:
            User ID or 'anonymous'
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            return str(request.user.id)
        return 'anonymous'

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address from request.

        Args:
            request: Django request object

        Returns:
            Client IP address
        """
        # Import SecurityMonitor to use its IP extraction logic
        from .security import SecurityMonitor
        return SecurityMonitor._get_client_ip(request)

    def _track_rate_limit_violation(
        self,
        user_id: str,
        ip_address: str,
        endpoint: str,
        request: HttpRequest
    ) -> None:
        """
        Track rate limit violation and alert on suspicious patterns.

        Args:
            user_id: User ID or 'anonymous'
            ip_address: Client IP address
            endpoint: API endpoint that was rate limited
            request: Django request object
        """
        # Log the violation
        logger.warning(
            f"{LOG_PREFIX_RATELIMIT} Rate limit violation: "
            f"user_id={user_id}, ip={ip_address}, endpoint={endpoint}"
        )

        # Track violations for this user/IP combination
        violation_key = f"rate_limit_violations:{user_id}:{ip_address}"
        violations = cache.get(violation_key, [])
        current_time = time.time()

        # Remove old violations outside the time window
        violations = [
            v for v in violations
            if current_time - v['timestamp'] < RATE_LIMIT_VIOLATION_WINDOW
        ]

        # Add new violation
        violations.append({
            'timestamp': current_time,
            'endpoint': endpoint,
            'method': request.method,
        })

        # Store updated violations
        cache.set(violation_key, violations, RATE_LIMIT_VIOLATION_WINDOW)

        # Check if threshold exceeded
        if len(violations) >= RATE_LIMIT_VIOLATION_THRESHOLD:
            self._trigger_rate_limit_alert(
                user_id=user_id,
                ip_address=ip_address,
                violations=violations
            )

    def _trigger_rate_limit_alert(
        self,
        user_id: str,
        ip_address: str,
        violations: list
    ) -> None:
        """
        Trigger security alert for excessive rate limit violations.

        Args:
            user_id: User ID or 'anonymous'
            ip_address: Client IP address
            violations: List of violation records
        """
        # Get unique endpoints hit
        endpoints = list(set(v['endpoint'] for v in violations))

        logger.error(
            f"{LOG_PREFIX_SECURITY} ALERT: Excessive rate limit violations: "
            f"user_id={user_id}, ip={ip_address}, "
            f"violation_count={len(violations)}, "
            f"endpoints={endpoints}"
        )

        # Integrate with SecurityMonitor for centralized alerting
        from .security import SecurityMonitor
        SecurityMonitor._trigger_security_alert(
            'excessive_rate_limit_violations',
            {
                'user_id': user_id,
                'ip_address': ip_address,
                'violation_count': len(violations),
                'endpoints': endpoints,
                'time_window': f'{RATE_LIMIT_VIOLATION_WINDOW}s',
            }
        )

        # In production, you might want to:
        # - Temporarily block the IP address
        # - Disable the user account
        # - Send notification to security team
        # - Create incident ticket


class SecurityMetricsMiddleware:
    """
    Middleware to collect security metrics for monitoring and analysis.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Collect security metrics for the request."""

        # Track request timing
        start_time = time.time()

        # Process request
        response = self.get_response(request)

        # Calculate request duration
        duration = time.time() - start_time

        # Track metrics for security-sensitive endpoints
        if self._is_security_sensitive_endpoint(request.path):
            self._track_security_metric(
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                duration=duration,
                user_id=self._get_user_id(request),
                ip_address=self._get_client_ip(request)
            )

        return response

    def _is_security_sensitive_endpoint(self, path: str) -> bool:
        """
        Check if endpoint is security-sensitive and should be tracked.

        Args:
            path: Request path

        Returns:
            True if security-sensitive, False otherwise
        """
        sensitive_paths = [
            '/api/auth/login/',
            '/api/auth/register/',
            '/api/auth/logout/',
            '/api/auth/token/refresh/',
            '/api/auth/password/reset/',
            '/api/auth/password/change/',
        ]

        return any(path.startswith(p) for p in sensitive_paths)

    def _get_user_id(self, request: HttpRequest) -> str:
        """Get user ID from request."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return str(request.user.id)
        return 'anonymous'

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP from request."""
        from .security import SecurityMonitor
        return SecurityMonitor._get_client_ip(request)

    def _track_security_metric(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
        user_id: str,
        ip_address: str
    ) -> None:
        """
        Track security metric for analysis.

        Args:
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            duration: Request duration in seconds
            user_id: User ID or 'anonymous'
            ip_address: Client IP address
        """
        # Store aggregated metrics in cache for monitoring dashboard
        metrics_key = f"security_metrics:{endpoint}:{method}"
        metrics = cache.get(metrics_key, {
            'total_requests': 0,
            'failed_requests': 0,
            'avg_duration': 0,
            'unique_ips': set(),
        })

        metrics['total_requests'] += 1
        if status_code >= 400:
            metrics['failed_requests'] += 1

        # Update rolling average duration
        metrics['avg_duration'] = (
            (metrics['avg_duration'] * (metrics['total_requests'] - 1) + duration)
            / metrics['total_requests']
        )

        # Track unique IPs (convert to list for cache storage)
        if isinstance(metrics['unique_ips'], set):
            metrics['unique_ips'].add(ip_address)
        else:
            metrics['unique_ips'] = set(metrics['unique_ips'])
            metrics['unique_ips'].add(ip_address)

        # Convert set to list for cache storage
        metrics_to_store = metrics.copy()
        metrics_to_store['unique_ips'] = list(metrics['unique_ips'])

        # Store for 24 hours
        cache.set(metrics_key, metrics_to_store, 86400)

        # Log high-duration requests
        if duration > 5.0:  # More than 5 seconds
            logger.warning(
                f"{LOG_PREFIX_SECURITY} Slow security endpoint: "
                f"endpoint={endpoint}, duration={duration:.2f}s, "
                f"user_id={user_id}, status={status_code}"
            )


def get_security_metrics() -> dict:
    """
    Get security metrics for monitoring dashboard.

    Returns:
        Dictionary of security metrics
    """
    # This could be expanded to aggregate metrics from cache
    # and provide comprehensive security dashboard data
    return {
        'status': 'active',
        'monitoring_enabled': True,
    }
