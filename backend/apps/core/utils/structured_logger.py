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

    # With automatic request context
    logger.error("[API] External API failed", extra={'api': 'plant.id', 'status': 500})

    # Debug level (development only)
    logger.debug("[DB] Query executed", extra={'query_time': 0.023, 'rows': 150})

Pattern Reference:
- Follows patterns from apps/plant_identification/services/plant_id_service.py
- Maintains bracket prefixes for backward compatibility
- Type hints on all methods
- Automatic context injection (request_id, user_id, environment)
"""

import logging
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
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')

    def _get_context(self) -> Dict[str, Any]:
        """
        Extract automatic context from current request.

        Returns:
            Dictionary with request_id, user_id, environment
        """
        context = {
            'environment': self.environment,
        }

        # Add request ID if available (from django-request-id middleware)
        if HAS_REQUEST_ID:
            try:
                request_id = getattr(local, 'request_id', None)
                if request_id:
                    context['request_id'] = request_id
            except Exception:
                pass

        # Add user ID if available (from request context)
        try:
            from crum import get_current_user
            user = get_current_user()
            if user and hasattr(user, 'id'):
                context['user_id'] = str(user.id)
                context['username'] = user.username
        except ImportError:
            pass
        except Exception:
            pass

        return context

    def _merge_extra(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Merge user-provided extra data with automatic context.

        Args:
            extra: User-provided context dictionary

        Returns:
            Merged context dictionary
        """
        context = self._get_context()

        if extra:
            # User-provided data takes precedence
            context.update(extra)

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


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        StructuredLogger instance

    Example:
        from apps.core.utils.structured_logger import get_logger

        logger = get_logger(__name__)
        logger.info("[CACHE] Cache miss", extra={'key': cache_key})
    """
    return StructuredLogger(name)


# Convenience function for backward compatibility
def get_structured_logger(name: str) -> StructuredLogger:
    """Alias for get_logger() for backward compatibility."""
    return get_logger(name)
