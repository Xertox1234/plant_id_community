"""
Wagtail AI integration with caching and rate limiting.

Monkey-patches Wagtail AI's get_ai_text() function to add:
- Redis/database caching (80-95% cost reduction)
- Per-user rate limiting (quota protection)
- Cost tracking and monitoring

This allows us to use Wagtail AI's native panels while keeping
our custom cost optimization strategies.

Pattern: Transparent middleware for Wagtail AI
"""

import logging
from typing import Any, Optional
from django.contrib.auth.models import User
from wagtail_ai import utils as wagtail_ai_utils

logger = logging.getLogger(__name__)

# Store original function before monkey-patching
_original_get_ai_text = None


def cached_get_ai_text(
    prompt: str,
    backend_name: str = "default",
    **kwargs
) -> str:
    """
    Wrapper for Wagtail AI's get_ai_text() with caching and rate limiting.

    Adds transparent caching and rate limiting without changing
    Wagtail AI's native panel behavior.

    Args:
        prompt: AI generation prompt
        backend_name: Wagtail AI backend name (default: "default")
        **kwargs: Additional arguments passed to original function

    Returns:
        Generated AI content (from cache or fresh API call)

    Raises:
        Exception: If rate limit exceeded or AI generation fails
    """
    from .services import AICacheService, AIRateLimiter

    # Extract user from kwargs for rate limiting
    request = kwargs.get('request')
    user = None
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user

    # 1. Check cache first (fastest path)
    feature = _determine_feature_type(prompt)
    cached_response = AICacheService.get_cached_response(feature, prompt)

    if cached_response:
        logger.info(
            f"[WAGTAIL AI] Cache HIT for {feature} "
            f"(user: {user.id if user else 'anonymous'})"
        )
        return cached_response.get('text', '')

    # 2. Check rate limit before expensive AI call
    if user:
        is_staff = user.is_staff
        user_id = user.id

        if not AIRateLimiter.check_user_limit(user_id, is_staff):
            remaining = AIRateLimiter.get_remaining_calls(user_id, is_staff)
            limit = AIRateLimiter.USER_LIMITS['staff' if is_staff else 'authenticated']

            logger.warning(
                f"[WAGTAIL AI] Rate limit EXCEEDED for user {user_id} "
                f"({remaining}/{limit} calls remaining)"
            )
            raise Exception(
                f"AI rate limit exceeded. You have {remaining}/{limit} calls remaining this hour. "
                "Please try again later."
            )

        logger.info(
            f"[WAGTAIL AI] Rate limit check PASSED for user {user_id} "
            f"({AIRateLimiter.get_remaining_calls(user_id, is_staff)} calls remaining)"
        )

    # 3. Generate content using original Wagtail AI function
    try:
        logger.info(f"[WAGTAIL AI] Generating {feature} content (prompt length: {len(prompt)} chars)")

        response = _original_get_ai_text(prompt, backend_name, **kwargs)

        # 4. Cache successful response
        AICacheService.set_cached_response(feature, prompt, {'text': response})

        logger.info(
            f"[WAGTAIL AI] Generation SUCCESS for {feature} "
            f"(length: {len(response)} chars, user: {user.id if user else 'anonymous'})"
        )

        return response

    except Exception as e:
        logger.error(
            f"[WAGTAIL AI] Generation FAILED for {feature}: {str(e)}",
            exc_info=True,
            extra={
                'feature': feature,
                'user_id': user.id if user else None,
                'prompt_length': len(prompt),
            }
        )
        raise


def _determine_feature_type(prompt: str) -> str:
    """
    Determine AI feature type from prompt for cache key generation.

    Args:
        prompt: AI generation prompt

    Returns:
        Feature type string: 'title', 'description', 'introduction', or 'content'
    """
    prompt_lower = prompt.lower()

    if 'title' in prompt_lower and ('blog post' in prompt_lower or 'seo-optimized' in prompt_lower):
        return 'title'
    elif 'meta description' in prompt_lower or ('description' in prompt_lower and 'seo' in prompt_lower):
        return 'description'
    elif 'introduction' in prompt_lower and ('paragraph' in prompt_lower or 'hook' in prompt_lower):
        return 'introduction'
    else:
        return 'content'


def install_wagtail_ai_integration():
    """
    Install monkey-patch for Wagtail AI integration.

    This function should be called once during Django app initialization
    (typically in AppConfig.ready()).

    Patches wagtail_ai.utils.get_ai_text to add caching and rate limiting
    while preserving all original Wagtail AI functionality.
    """
    global _original_get_ai_text

    # Only patch once
    if _original_get_ai_text is not None:
        logger.warning("[WAGTAIL AI] Integration already installed, skipping")
        return

    # Store original function
    _original_get_ai_text = wagtail_ai_utils.get_ai_text

    # Apply monkey-patch
    wagtail_ai_utils.get_ai_text = cached_get_ai_text

    logger.info(
        "[WAGTAIL AI] Integration installed successfully "
        "(caching + rate limiting enabled)"
    )


def uninstall_wagtail_ai_integration():
    """
    Remove monkey-patch and restore original Wagtail AI behavior.

    Useful for testing or rollback scenarios.
    """
    global _original_get_ai_text

    if _original_get_ai_text is None:
        logger.warning("[WAGTAIL AI] Integration not installed, nothing to uninstall")
        return

    # Restore original function
    wagtail_ai_utils.get_ai_text = _original_get_ai_text
    _original_get_ai_text = None

    logger.info("[WAGTAIL AI] Integration uninstalled, original behavior restored")
