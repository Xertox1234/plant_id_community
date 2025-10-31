"""
Enterprise-grade structured logging wrapper for Django.

This module provides a production-ready logging interface with:
- Automatic request ID extraction
- User ID context injection
- Structured JSON logging (when pythonjsonlogger is installed)
- Bracket prefix support for log filtering ([CACHE], [PERF], etc.)
- Sentry integration for error tracking

Usage:
    from apps.core.utils.structured_logger import get_logger

    logger = get_logger(__name__)

    # Basic logging with bracket prefix
    logger.info("[CACHE] Cache hit", extra={'key': cache_key, 'hit_rate': 0.42})

    # With automatic request context (request_id, user_id auto-injected)
    logger.error("[API] External API failed", extra={'api': 'plant.id', 'status': 500})

    # Debug level (development only)
    logger.debug("[DB] Query executed", extra={'query_time': 0.023, 'rows': 150})

Pattern Reference:
- Follows patterns from apps/plant_identification/services/plant_id_service.py
- Maintains bracket prefixes for backward compatibility
- Type hints on all methods
- Automatic context injection (request_id, user_id, environment)
- PII-safe logging (no usernames or emails in structured logs)
"""

import json
import logging
import threading
from typing import Any, Dict, Optional
from django.conf import settings

# Try to import request_id for automatic context injection
try:
    from request_id.middleware import local
    HAS_REQUEST_ID = True
except ImportError:
    HAS_REQUEST_ID = False


class StructuredLogger:
    """
    Wrapper around Python's standard logging that adds structured context.

    This class automatically injects:
    - request_id: From django-request-id middleware
    - user_id: From request.user if available
    - environment: From Django settings
    - timestamp: Automatic from logging framework

    The logger maintains bracket prefixes ([CACHE], [PERF]) for backward
    compatibility with existing log filtering patterns.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger for a module.

        Args:
            name: Module name (typically __name__)
        """
        self.logger = logging.getLogger(name)

    def _get_context(self) -> Dict[str, Any]:
        """
        Extract automatic context from current request.

        Returns:
            Dictionary with request_id, user_id, environment

        Note:
            Usernames and emails are NOT logged to prevent PII leakage.
            Use user_id for correlation instead.
        """
        context = {
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
        }

        # Add request ID if available (from django-request-id middleware)
        if HAS_REQUEST_ID:
            try:
                request_id = getattr(local, 'request_id', None)
                if request_id:
                    context['request_id'] = request_id
            except (AttributeError, RuntimeError):
                # AttributeError: local doesn't exist
                # RuntimeError: called outside request context
                pass

        # Add user ID if available (from request context)
        # NOTE: Username is PII and NOT logged for GDPR/CCPA compliance
        try:
            from crum import get_current_user
            user = get_current_user()
            if user and hasattr(user, 'id'):
                context['user_id'] = str(user.id)
                # Do NOT log username - it's PII
        except (ImportError, AttributeError, RuntimeError):
            # ImportError: crum not installed
            # AttributeError: user has no 'id' attribute
            # RuntimeError: called outside request context
            pass

        return context

    def _merge_extra(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Merge user-provided extra data with automatic context.

        Args:
            extra: User-provided context dictionary

        Returns:
            Merged context dictionary

        Note:
            Non-dict `extra` values are handled gracefully.
            Non-JSON-serializable values are converted to strings.
        """
        context = self._get_context()

        if extra:
            # Validate input type
            if not isinstance(extra, dict):
                # Log warning but don't crash
                self.logger.warning(
                    f"[LOGGER] Invalid extra type: {type(extra).__name__}. Expected dict."
                )
                return context

            # Sanitize values for JSON serialization
            for key, value in extra.items():
                try:
                    # Test JSON serializability
                    json.dumps(value)
                    context[key] = value
                except (TypeError, ValueError):
                    # Convert non-serializable objects to string
                    context[key] = str(value)

        return context

    def debug(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """
        Log debug-level message (development only).

        Args:
            message: Log message with optional bracket prefix
            extra: Additional structured context
            exc_info: Include exception traceback

        Example:
            logger.debug("[DB] Query executed", extra={'rows': 150, 'time': 0.023})
        """
        self.logger.debug(message, extra=self._merge_extra(extra), exc_info=exc_info)

    def info(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """
        Log info-level message (general operations).

        Args:
            message: Log message with optional bracket prefix
            extra: Additional structured context
            exc_info: Include exception traceback

        Example:
            logger.info("[CACHE] Hit", extra={'key': 'blog:post:123', 'hit_rate': 0.42})
        """
        self.logger.info(message, extra=self._merge_extra(extra), exc_info=exc_info)

    def warning(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """
        Log warning-level message (unexpected but recoverable).

        Args:
            message: Log message with optional bracket prefix
            extra: Additional structured context
            exc_info: Include exception traceback

        Example:
            logger.warning("[CIRCUIT] Circuit breaker opened", extra={'api': 'plant.id'})
        """
        self.logger.warning(message, extra=self._merge_extra(extra), exc_info=exc_info)

    def error(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ) -> None:
        """
        Log error-level message (serious problems).

        Args:
            message: Log message with optional bracket prefix
            extra: Additional structured context
            exc_info: Include exception traceback (default: True)

        Example:
            logger.error("[API] Plant.id API failed", extra={'status': 500, 'retry': 3})
        """
        self.logger.error(message, extra=self._merge_extra(extra), exc_info=exc_info)

    def critical(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ) -> None:
        """
        Log critical-level message (system failure).

        Args:
            message: Log message with optional bracket prefix
            extra: Additional structured context
            exc_info: Include exception traceback (default: True)

        Example:
            logger.critical("[DB] Database connection lost", extra={'retry_count': 5})
        """
        self.logger.critical(message, extra=self._merge_extra(extra), exc_info=exc_info)

    def exception(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log exception with full traceback (convenience method).

        Args:
            message: Log message with optional bracket prefix
            extra: Additional structured context

        Example:
            try:
                risky_operation()
            except Exception as e:
                logger.exception("[ERROR] Operation failed", extra={'operation': 'identify'})
        """
        self.logger.exception(message, extra=self._merge_extra(extra))


# Module-level logger cache for performance
_logger_cache: Dict[str, StructuredLogger] = {}
_logger_lock: threading.Lock = threading.Lock()


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance for a module.

    Logger instances are cached per module name for performance.
    This avoids creating new wrapper objects on every call.

    Args:
        name: Module name (typically __name__)

    Returns:
        Cached StructuredLogger instance

    Example:
        from apps.core.utils.structured_logger import get_logger

        logger = get_logger(__name__)
        logger.info("[CACHE] Cache miss", extra={'key': cache_key})

    Thread Safety:
        Uses double-checked locking for thread-safe cache access.
    """
    # Fast path: check cache without lock
    if name in _logger_cache:
        return _logger_cache[name]

    # Slow path: create logger with lock
    with _logger_lock:
        # Double-checked locking pattern
        if name not in _logger_cache:
            _logger_cache[name] = StructuredLogger(name)

    return _logger_cache[name]


# Convenience function for backward compatibility
def get_structured_logger(name: str) -> StructuredLogger:
    """Alias for get_logger() for backward compatibility."""
    return get_logger(name)
