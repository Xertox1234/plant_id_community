"""
AI Rate Limiter for Wagtail AI API calls.

Implements Pattern 4 from WAGTAIL_AI_PATTERNS_CODIFIED.md
Prevents cost overruns through per-user and global rate limiting.
"""

from django.core.cache import cache
from django.http import HttpResponse
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class AIRateLimiter:
    """
    Rate limiting for AI API calls to prevent cost overruns.

    Limits:
    - Per-user: 10 AI calls per hour
    - Global: 100 AI calls per hour

    Usage:
        # Check rate limits before API call
        if not AIRateLimiter.check_user_limit(user.id):
            return HttpResponse("Rate limit exceeded", status=429)

        # Make AI API call
        response = generate_ai_content(...)

    Or use decorator:
        @ai_rate_limit
        def generate_title_view(request):
            ...
    """

    # Rate limit thresholds
    USER_LIMIT = 10  # calls per hour
    GLOBAL_LIMIT = 100  # calls per hour
    STAFF_LIMIT = 50  # calls per hour (elevated for staff)
    TTL = 3600  # 1 hour in seconds

    @classmethod
    def check_user_limit(cls, user_id: int, is_staff: bool = False) -> bool:
        """
        Check if user has exceeded their AI quota.

        Args:
            user_id: User ID to check
            is_staff: Whether user is staff (gets elevated limit)

        Returns:
            True if within limit, False if rate limit exceeded

        Example:
            if not AIRateLimiter.check_user_limit(request.user.id, request.user.is_staff):
                return HttpResponse("Rate limit exceeded", status=429)
        """
        cache_key = f"ai_rate_limit:user:{user_id}"
        calls = cache.get(cache_key, 0)

        limit = cls.STAFF_LIMIT if is_staff else cls.USER_LIMIT

        if calls >= limit:
            logger.warning(
                f"[RATE_LIMIT] User {user_id} exceeded limit "
                f"({calls}/{limit} calls/hour)"
            )
            return False  # Rate limit exceeded

        # Increment counter
        cache.set(cache_key, calls + 1, cls.TTL)

        logger.debug(
            f"[RATE_LIMIT] User {user_id}: {calls + 1}/{limit} calls/hour"
        )

        return True

    @classmethod
    def check_global_limit(cls) -> bool:
        """
        Check if global AI quota has been exceeded.

        Returns:
            True if within limit, False if rate limit exceeded

        Example:
            if not AIRateLimiter.check_global_limit():
                return HttpResponse("Server busy, try again later", status=429)
        """
        cache_key = "ai_rate_limit:global"
        calls = cache.get(cache_key, 0)

        if calls >= cls.GLOBAL_LIMIT:
            logger.error(
                f"[RATE_LIMIT] Global limit exceeded "
                f"({calls}/{cls.GLOBAL_LIMIT} calls/hour)"
            )
            return False  # Rate limit exceeded

        # Increment counter
        cache.set(cache_key, calls + 1, cls.TTL)

        logger.debug(
            f"[RATE_LIMIT] Global: {calls + 1}/{cls.GLOBAL_LIMIT} calls/hour"
        )

        return True

    @classmethod
    def get_remaining_calls(cls, user_id: int, is_staff: bool = False) -> int:
        """
        Get remaining AI calls for user.

        Args:
            user_id: User ID to check
            is_staff: Whether user is staff

        Returns:
            Number of remaining calls in current hour

        Example:
            remaining = AIRateLimiter.get_remaining_calls(user.id, user.is_staff)
            print(f"You have {remaining} AI calls remaining this hour")
        """
        cache_key = f"ai_rate_limit:user:{user_id}"
        calls = cache.get(cache_key, 0)

        limit = cls.STAFF_LIMIT if is_staff else cls.USER_LIMIT

        return max(0, limit - calls)

    @classmethod
    def reset_user_limit(cls, user_id: int) -> None:
        """
        Reset rate limit for specific user (admin function).

        Args:
            user_id: User ID to reset

        Example:
            # Admin resets user's rate limit
            AIRateLimiter.reset_user_limit(user.id)
        """
        cache_key = f"ai_rate_limit:user:{user_id}"
        cache.delete(cache_key)

        logger.info(f"[RATE_LIMIT] Reset limit for user {user_id}")

    @classmethod
    def reset_global_limit(cls) -> None:
        """
        Reset global rate limit (admin function).

        Example:
            # Emergency reset of global limit
            AIRateLimiter.reset_global_limit()
        """
        cache_key = "ai_rate_limit:global"
        cache.delete(cache_key)

        logger.info("[RATE_LIMIT] Reset global limit")


def ai_rate_limit(func):
    """
    Decorator to enforce AI rate limiting on views/viewsets.

    Usage:
        @ai_rate_limit
        def generate_title_view(request):
            # AI generation logic here
            pass

    Returns:
        HTTP 429 (Too Many Requests) if rate limit exceeded
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        user_id = request.user.id if request.user.is_authenticated else 0
        is_staff = request.user.is_staff if request.user.is_authenticated else False

        # Check user-specific limit
        if not AIRateLimiter.check_user_limit(user_id, is_staff):
            limit = AIRateLimiter.STAFF_LIMIT if is_staff else AIRateLimiter.USER_LIMIT
            return HttpResponse(
                f"AI rate limit exceeded. You can make {limit} requests per hour. "
                f"Please try again later.",
                status=429,
                headers={'Retry-After': '3600'}  # 1 hour
            )

        # Check global limit
        if not AIRateLimiter.check_global_limit():
            return HttpResponse(
                "Server is experiencing high AI usage. Please try again in a few minutes.",
                status=429,
                headers={'Retry-After': '300'}  # 5 minutes
            )

        return func(request, *args, **kwargs)

    return wrapper


# Async version for Django 5.2+ async views
def ai_rate_limit_async(func):
    """
    Async decorator to enforce AI rate limiting on async views.

    Usage:
        @ai_rate_limit_async
        async def generate_title_view(request):
            # Async AI generation logic here
            pass
    """
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        user_id = request.user.id if request.user.is_authenticated else 0
        is_staff = request.user.is_staff if request.user.is_authenticated else False

        # Check user-specific limit
        if not AIRateLimiter.check_user_limit(user_id, is_staff):
            limit = AIRateLimiter.STAFF_LIMIT if is_staff else AIRateLimiter.USER_LIMIT
            return HttpResponse(
                f"AI rate limit exceeded. You can make {limit} requests per hour. "
                f"Please try again later.",
                status=429,
                headers={'Retry-After': '3600'}
            )

        # Check global limit
        if not AIRateLimiter.check_global_limit():
            return HttpResponse(
                "Server is experiencing high AI usage. Please try again in a few minutes.",
                status=429,
                headers={'Retry-After': '300'}
            )

        return await func(request, *args, **kwargs)

    return wrapper
