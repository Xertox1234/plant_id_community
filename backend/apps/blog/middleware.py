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

from django.core.cache import cache
from django.db import models, transaction

from .constants import (
    VIEW_DEDUPLICATION_TIMEOUT,
    VIEW_TRACKING_BOT_KEYWORDS,
    VIEW_TRACKING_CACHE_PREFIX,
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
        from .models import BlogPostPage

        # Only track GET requests
        if request.method != "GET":
            return

        # Check if this is a blog post detail view
        # We need to check the resolved view or URL pattern
        resolved_match = request.resolver_match
        if not resolved_match:
            return

        # Check if viewing a Wagtail page (BlogPostPage)
        page = getattr(request, "_wagtail_page", None)
        if not page or not isinstance(page, BlogPostPage):
            return

        record_blog_view(page, user=request.user, request=request)

    def _is_bot(self, user_agent):
        """
        Bot detection based on user agent (uses the constants above).

        Returns True if user agent looks like a bot/crawler.
        Uses comprehensive keyword list from constants.py.
        """
        user_agent_lower = user_agent.lower()
        return any(
            keyword in user_agent_lower for keyword in VIEW_TRACKING_BOT_KEYWORDS
        )


def record_blog_view(page, *, user, request):
    """
    Record one view of ``page`` (a live ``BlogPostPage``).

    Called by the blog API's detail route, which is how the website and the
    app read a post (todo 701: the middleware path below never fired, because
    nothing sets ``request._wagtail_page``). ``user`` is the API's
    authenticated user (a JWT sign-in), not ``request.user`` on the plain
    Django request, which only knows a session. ``request`` is the plain
    ``HttpRequest`` and is read for the IP, browser and referrer only.
    """
    from apps.core.security import SecurityMonitor

    from .models import BlogPostPage, BlogPostView

    # Get tracking data with secure IP extraction
    user = user if user is not None and user.is_authenticated else None
    ip_address = SecurityMonitor._get_client_ip(request)  # ✅ Uses secure method
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
    referrer = request.META.get("HTTP_REFERER", "")

    # Bot detection (simple check)
    if _is_bot(user_agent):
        logger.debug("[ANALYTICS] Skipping bot view tracking")
        return

    # Deduplication: Check if same user/IP viewed this post recently
    cache_key = (
        f"{VIEW_TRACKING_CACHE_PREFIX}:{page.id}:{user.id if user else ip_address}"
    )
    if cache.get(cache_key):
        # Never the key: it holds the reader's IP address.
        logger.debug(f"[ANALYTICS] Duplicate view prevented: post {page.id}")
        return

    # Track the view
    try:
        # Use transaction.on_commit to track after response sent
        def track():
            # An account that switched usage records off (todo 701) gets
            # no row: no user, IP, browser or referrer is kept. The
            # post's own counter below names nobody and still counts.
            if user is None or user.usage_records:
                BlogPostView.objects.create(
                    post=page,
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    referrer=referrer,
                )

            # Increment post view_count (atomic)
            BlogPostPage.objects.filter(id=page.id).update(
                view_count=models.F("view_count") + 1
            )

            logger.info(
                f"[ANALYTICS] View tracked: {page.title} "
                f"(signed_in={user is not None}, "
                f"total_views={page.view_count + 1})"
            )

        transaction.on_commit(track)

        # Set deduplication cache (uses the constant above)
        cache.set(cache_key, True, timeout=VIEW_DEDUPLICATION_TIMEOUT)

    except Exception as e:
        # Don't let tracking errors break the page
        logger.error(f"[ANALYTICS] Error tracking view: {e}")


def _is_bot(user_agent):
    """True if the user agent looks like a bot or crawler."""
    user_agent_lower = user_agent.lower()
    return any(keyword in user_agent_lower for keyword in VIEW_TRACKING_BOT_KEYWORDS)
