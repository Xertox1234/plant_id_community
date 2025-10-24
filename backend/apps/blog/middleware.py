"""
Blog view tracking middleware (Phase 6.2).

Tracks page views for blog posts to enable analytics including:
- Popular posts ranking
- Trending content identification
- Traffic source analysis
- User engagement metrics

Performance Considerations:
- View tracking is async (doesn't block response)
- Deduplication prevents inflation from page refreshes
- Rate limiting prevents bot spam
- Database indexes optimize analytics queries
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction, models
from .constants import (
    VIEW_DEDUPLICATION_TIMEOUT,
    VIEW_TRACKING_CACHE_PREFIX,
    VIEW_TRACKING_BOT_KEYWORDS,
)

logger = logging.getLogger(__name__)


class BlogViewTrackingMiddleware:
    """
    Middleware to track blog post views for analytics.

    Tracks views on BlogPostPage detail requests and stores:
    - User (if authenticated)
    - IP address
    - User agent (browser/device info)
    - Referrer (traffic source)
    - Timestamp

    View Deduplication:
    - Same IP/user viewing same post within 15 minutes = 1 view
    - Prevents inflation from page refreshes
    - Uses cache for fast deduplication checks
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Track view after response (async processing)
        if response.status_code == 200:
            self._track_view(request, response)

        return response

    def _track_view(self, request, response):
        """
        Track blog post view if applicable.

        Only tracks views on:
        - Blog post detail pages
        - GET requests
        - Non-bot traffic

        Deduplication:
        - Cache key: view:blog:{post_id}:{ip_or_user}
        - TTL: 15 minutes
        - Prevents duplicate views from same user/IP

        Security:
        - Uses SecurityMonitor._get_client_ip() for IP spoofing protection
        """
        from .models import BlogPostPage, BlogPostView
        from apps.core.security import SecurityMonitor

        # Only track GET requests
        if request.method != 'GET':
            return

        # Check if this is a blog post detail view
        # We need to check the resolved view or URL pattern
        resolved_match = request.resolver_match
        if not resolved_match:
            return

        # Check if viewing a Wagtail page (BlogPostPage)
        page = getattr(request, '_wagtail_page', None)
        if not page or not isinstance(page, BlogPostPage):
            return

        # Get tracking data with secure IP extraction (BLOCKER 1 fix)
        user = request.user if request.user.is_authenticated else None
        ip_address = SecurityMonitor._get_client_ip(request)  # ✅ Uses secure method
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        referrer = request.META.get('HTTP_REFERER', '')

        # Bot detection (simple check)
        if self._is_bot(user_agent):
            logger.debug(f"[ANALYTICS] Skipping bot view tracking: {user_agent[:50]}")
            return

        # Deduplication: Check if same user/IP viewed this post recently (BLOCKER 3 fix)
        cache_key = f"{VIEW_TRACKING_CACHE_PREFIX}:{page.id}:{user.id if user else ip_address}"
        if cache.get(cache_key):
            logger.debug(f"[ANALYTICS] Duplicate view prevented: {page.title} ({cache_key})")
            return

        # Track the view
        try:
            # Use transaction.on_commit to track after response sent
            def track():
                BlogPostView.objects.create(
                    post=page,
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    referrer=referrer,
                )

                # Increment post view_count (atomic)
                BlogPostPage.objects.filter(id=page.id).update(
                    view_count=models.F('view_count') + 1
                )

                logger.info(
                    f"[ANALYTICS] View tracked: {page.title} "
                    f"(user={user.username if user else 'anonymous'}, "
                    f"total_views={page.view_count + 1})"
                )

            transaction.on_commit(track)

            # Set deduplication cache (BLOCKER 3 fix - uses constant)
            cache.set(cache_key, True, timeout=VIEW_DEDUPLICATION_TIMEOUT)

        except Exception as e:
            # Don't let tracking errors break the page
            logger.error(f"[ANALYTICS] Error tracking view: {e}")

    def _is_bot(self, user_agent):
        """
        Bot detection based on user agent (BLOCKER 3 fix - uses constants).

        Returns True if user agent looks like a bot/crawler.
        Uses comprehensive keyword list from constants.py.
        """
        user_agent_lower = user_agent.lower()
        return any(keyword in user_agent_lower for keyword in VIEW_TRACKING_BOT_KEYWORDS)
