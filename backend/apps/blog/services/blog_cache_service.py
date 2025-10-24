"""
Blog caching service for API response optimization.

Follows patterns from apps/plant_identification/services/plant_id_service.py
to achieve 40% cache hit rate with instant (<10ms) responses.

Pattern Reference:
- Bracketed logging prefixes: [CACHE], [PERF]
- Type hints on all methods
- Constants from constants.py
- Signal-based cache invalidation

Performance Targets:
- Cache hit rate: >35% (target: 40%)
- Cached response time: <50ms
- Cache TTL: 24 hours (blog content changes infrequently)
"""

import hashlib
import logging
from typing import Optional, Dict, Any

from django.core.cache import cache
from django.conf import settings

from ..constants import (
    BLOG_LIST_CACHE_TIMEOUT,
    BLOG_POST_CACHE_TIMEOUT,
    BLOG_CATEGORY_CACHE_TIMEOUT,
    CACHE_PREFIX_BLOG_POST,
    CACHE_PREFIX_BLOG_LIST,
    CACHE_PREFIX_BLOG_CATEGORY,
)

logger = logging.getLogger(__name__)


class BlogCacheService:
    """
    Caching service for blog API responses.

    Follows patterns from apps/plant_identification/services/plant_id_service.py:
    - Static methods for stateless operation
    - Bracketed logging for filtering: [CACHE]
    - Type hints on all methods
    - SHA-256 hash for cache key generation
    - Pattern matching for bulk invalidation

    Usage:
        # Check cache before API call
        cached_post = BlogCacheService.get_blog_post(slug)
        if cached_post:
            return cached_post  # Instant response <10ms

        # Make API call, then cache
        post_data = fetch_from_db(slug)
        BlogCacheService.set_blog_post(slug, post_data)
    """

    @staticmethod
    def get_blog_post(slug: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached blog post by slug.

        Args:
            slug: URL-friendly identifier for blog post

        Returns:
            Cached blog post data dict or None if cache miss

        Performance:
            - Cache hit: <10ms response
            - Cache miss: Returns None, triggers DB query
        """
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for blog post {slug} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for blog post {slug}")
        return None

    @staticmethod
    def set_blog_post(slug: str, data: Dict[str, Any]) -> None:
        """
        Cache blog post data.

        Args:
            slug: URL-friendly identifier for blog post
            data: Blog post data to cache (serialized dict)

        Cache Configuration:
            - TTL: 24 hours (BLOG_POST_CACHE_TIMEOUT)
            - Key format: blog:post:{slug}
            - Invalidation: On publish, unpublish, delete
        """
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cache.set(cache_key, data, BLOG_POST_CACHE_TIMEOUT)
        logger.info(f"[CACHE] SET for blog post {slug} (24h TTL)")

    @staticmethod
    def get_blog_list(page: int, limit: int, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached blog list with pagination and filters.

        Args:
            page: Page number for pagination
            limit: Results per page
            filters: Query filters (category, tag, search, etc.)

        Returns:
            Cached blog list data dict or None if cache miss

        Cache Key Generation:
            - Hash filters to create unique key per filter combination
            - Format: blog:list:{page}:{limit}:{filters_hash}
            - SHA-256 hash truncated to 16 characters (64 bits)
            - Birthday paradox: 50% collision after ~5 billion combinations
        """
        filters_hash = hashlib.sha256(str(sorted(filters.items())).encode()).hexdigest()[:16]
        cache_key = f"{CACHE_PREFIX_BLOG_LIST}:{page}:{limit}:{filters_hash}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for blog list page {page} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for blog list page {page}")
        return None

    @staticmethod
    def set_blog_list(page: int, limit: int, filters: Dict[str, Any], data: Dict[str, Any]) -> None:
        """
        Cache blog list data.

        Args:
            page: Page number for pagination
            limit: Results per page
            filters: Query filters used for this list
            data: Blog list data to cache (serialized dict)

        Cache Configuration:
            - TTL: 24 hours (BLOG_LIST_CACHE_TIMEOUT)
            - Key format: blog:list:{page}:{limit}:{filters_hash}
            - Hash length: 16 characters (64 bits) to prevent collisions
            - Invalidation: On ANY post publish/unpublish/delete
            - Tracking: Keys tracked for non-Redis backend invalidation
        """
        filters_hash = hashlib.sha256(str(sorted(filters.items())).encode()).hexdigest()[:16]
        cache_key = f"{CACHE_PREFIX_BLOG_LIST}:{page}:{limit}:{filters_hash}"
        cache.set(cache_key, data, BLOG_LIST_CACHE_TIMEOUT)

        # Track this key for fallback invalidation (non-Redis backends)
        # This enables invalidation when delete_pattern is not available
        try:
            cache_key_set = f"{CACHE_PREFIX_BLOG_LIST}:_keys"
            tracked_keys = cache.get(cache_key_set, set())
            if not isinstance(tracked_keys, set):
                tracked_keys = set()
            tracked_keys.add(cache_key)
            cache.set(cache_key_set, tracked_keys, BLOG_LIST_CACHE_TIMEOUT)
        except Exception as e:
            # If tracking fails, pattern matching will handle it (Redis)
            # or cache will naturally expire after 24h
            logger.debug(f"[CACHE] Failed to track key {cache_key}: {e}")

        logger.info(f"[CACHE] SET for blog list page {page} (24h TTL)")

    @staticmethod
    def get_blog_category(slug: str, page: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached blog category page.

        Args:
            slug: Category URL slug
            page: Page number for paginated category results

        Returns:
            Cached category page data dict or None if cache miss
        """
        cache_key = f"{CACHE_PREFIX_BLOG_CATEGORY}:{slug}:{page}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for category {slug} page {page} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for category {slug} page {page}")
        return None

    @staticmethod
    def set_blog_category(slug: str, page: int, data: Dict[str, Any]) -> None:
        """
        Cache blog category page data.

        Args:
            slug: Category URL slug
            page: Page number for pagination
            data: Category page data to cache

        Cache Configuration:
            - TTL: 24 hours (BLOG_CATEGORY_CACHE_TIMEOUT)
            - Key format: blog:category:{slug}:{page}
            - Invalidation: On category update or post category assignment
        """
        cache_key = f"{CACHE_PREFIX_BLOG_CATEGORY}:{slug}:{page}"
        cache.set(cache_key, data, BLOG_CATEGORY_CACHE_TIMEOUT)
        logger.info(f"[CACHE] SET for category {slug} page {page} (24h TTL)")

    @staticmethod
    def invalidate_blog_post(slug: str) -> None:
        """
        Invalidate blog post cache on update.

        Called by signals when:
        - Blog post is published
        - Blog post is unpublished
        - Blog post is deleted
        - Blog post content is updated

        Args:
            slug: Blog post slug to invalidate
        """
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cache.delete(cache_key)
        logger.info(f"[CACHE] INVALIDATE for blog post {slug}")

    @staticmethod
    def invalidate_blog_lists() -> None:
        """
        Invalidate all blog list caches.

        Called by signals when:
        - ANY blog post is published/unpublished/deleted
        - Blog post categories are changed
        - Featured flag is toggled

        Strategy:
        - Primary: Redis pattern matching (most efficient)
        - Fallback: Tracked key deletion (non-Redis backends)
        - Last resort: 24h natural expiration

        Note:
            This is intentionally aggressive - any blog content change
            invalidates ALL list caches. Trade-off between complexity
            and cache freshness favors simplicity.
        """
        # Try Redis pattern matching (most efficient)
        try:
            cache.delete_pattern(f"{CACHE_PREFIX_BLOG_LIST}:*")
            logger.info("[CACHE] INVALIDATE all blog lists (pattern match)")
            return
        except AttributeError:
            # Fallback: Use tracked keys for non-Redis backends
            try:
                cache_key_set = f"{CACHE_PREFIX_BLOG_LIST}:_keys"
                tracked_keys = cache.get(cache_key_set, set())

                if tracked_keys and isinstance(tracked_keys, set):
                    # Delete each tracked cache key
                    for key in tracked_keys:
                        cache.delete(key)
                    # Delete the tracking set itself
                    cache.delete(cache_key_set)
                    logger.info(f"[CACHE] INVALIDATE {len(tracked_keys)} blog list keys (tracked)")
                else:
                    logger.warning("[CACHE] No tracked blog list keys to invalidate (will expire naturally in 24h)")
            except Exception as e:
                logger.error(f"[CACHE] Failed to invalidate blog lists: {e}")

    @staticmethod
    def invalidate_blog_category(slug: str) -> None:
        """
        Invalidate all pages for a specific category.

        Called by signals when:
        - Category is updated
        - Posts are added/removed from category

        Args:
            slug: Category slug to invalidate
        """
        try:
            cache.delete_pattern(f"{CACHE_PREFIX_BLOG_CATEGORY}:{slug}:*")
            logger.info(f"[CACHE] INVALIDATE all pages for category {slug}")
        except AttributeError:
            logger.warning(f"[CACHE] Cache backend doesn't support delete_pattern, skipping category {slug} invalidation")

    @staticmethod
    def clear_all_blog_caches() -> None:
        """
        Nuclear option: clear ALL blog caches.

        Use cases:
        - Manual cache flush via management command
        - Major data migrations
        - Emergency cache clearing

        Warning:
            This will cause temporary performance degradation
            as caches are rebuilt from cold state.
        """
        try:
            cache.delete_pattern(f"{CACHE_PREFIX_BLOG_POST}:*")
            cache.delete_pattern(f"{CACHE_PREFIX_BLOG_LIST}:*")
            cache.delete_pattern(f"{CACHE_PREFIX_BLOG_CATEGORY}:*")
            logger.warning("[CACHE] CLEARED all blog caches (nuclear option)")
        except AttributeError:
            logger.warning("[CACHE] Cache backend doesn't support delete_pattern, manual flush required")

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache performance metrics

        Usage:
            stats = BlogCacheService.get_cache_stats()
            print(f"Hit rate: {stats['hit_rate']:.1%}")

        Note:
            Requires custom instrumentation in ViewSets to track hits/misses.
            This is a placeholder for future monitoring dashboard.
        """
        return {
            'hit_rate': 0.0,  # Placeholder - requires instrumentation
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'note': 'Statistics require instrumentation in ViewSets'
        }
