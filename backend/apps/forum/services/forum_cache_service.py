"""
Forum caching service for API response optimization.

Follows patterns from apps/blog/services/blog_cache_service.py
to achieve 30% cache hit rate with instant (<50ms) responses.

Pattern Reference:
- Bracketed logging prefixes: [CACHE], [PERF]
- Type hints on all methods
- Constants from constants.py
- Signal-based cache invalidation
- Dual-strategy invalidation (Redis pattern + tracked keys)

Performance Targets:
- Cache hit rate: >30% (lower than blog due to higher update frequency)
- Cached response time: <50ms
- Thread details TTL: 1 hour (frequent updates)
- Thread lists TTL: 6 hours
- Categories TTL: 24 hours (rarely change)
"""

import hashlib
import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.conf import settings

from ..constants import (
    CACHE_TIMEOUT_1_HOUR,
    CACHE_TIMEOUT_6_HOURS,
    CACHE_TIMEOUT_24_HOURS,
    CACHE_PREFIX_FORUM_THREAD,
    CACHE_PREFIX_FORUM_LIST,
    CACHE_PREFIX_FORUM_CATEGORY,
    CACHE_PREFIX_FORUM_POST,
)

logger = logging.getLogger(__name__)


class ForumCacheService:
    """
    Caching service for forum API responses.

    Follows patterns from apps/blog/services/blog_cache_service.py:
    - Static methods for stateless operation
    - Bracketed logging for filtering: [CACHE]
    - Type hints on all methods
    - SHA-256 hash for cache key generation
    - Pattern matching for bulk invalidation

    Usage:
        # Check cache before API call
        cached_thread = ForumCacheService.get_thread(slug)
        if cached_thread:
            return cached_thread  # Instant response <50ms

        # Make DB query, then cache
        thread_data = fetch_from_db(slug)
        ForumCacheService.set_thread(slug, thread_data)
    """

    @staticmethod
    def get_thread(slug: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached thread by slug.

        Args:
            slug: URL-friendly identifier for thread

        Returns:
            Cached thread data dict or None if cache miss

        Performance:
            - Cache hit: <10ms response
            - Cache miss: Returns None, triggers DB query
        """
        cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for thread {slug} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for thread {slug}")
        return None

    @staticmethod
    def set_thread(slug: str, data: Dict[str, Any]) -> None:
        """
        Cache thread data.

        Args:
            slug: URL-friendly identifier for thread
            data: Thread data to cache (serialized dict)

        Cache Configuration:
            - TTL: 1 hour (CACHE_TIMEOUT_1_HOUR)
            - Key format: forum:thread:{slug}
            - Invalidation: On post create/delete, thread update
        """
        cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
        cache.set(cache_key, data, CACHE_TIMEOUT_1_HOUR)
        logger.info(f"[CACHE] SET for thread {slug} (1h TTL)")

    @staticmethod
    def get_thread_list(page: int, limit: int, category_id: Optional[str], filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached thread list with pagination and filters.

        Args:
            page: Page number for pagination
            limit: Results per page
            category_id: Optional category UUID filter
            filters: Query filters (search, is_pinned, author, etc.)

        Returns:
            Cached thread list data dict or None if cache miss

        Cache Key Generation:
            - Hash filters to create unique key per filter combination
            - Format: forum:list:{category_id}:{page}:{limit}:{filters_hash}
            - Full SHA-256 hash (64 characters, 256 bits)
        """
        category_part = category_id or "all"
        filters_hash = hashlib.sha256(str(sorted(filters.items())).encode()).hexdigest()
        cache_key = f"{CACHE_PREFIX_FORUM_LIST}:{category_part}:{page}:{limit}:{filters_hash}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for thread list page {page} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for thread list page {page}")
        return None

    @staticmethod
    def set_thread_list(page: int, limit: int, category_id: Optional[str], filters: Dict[str, Any], data: Dict[str, Any]) -> None:
        """
        Cache thread list data.

        Args:
            page: Page number for pagination
            limit: Results per page
            category_id: Optional category UUID filter
            filters: Query filters used for this list
            data: Thread list data to cache (serialized dict)

        Cache Configuration:
            - TTL: 6 hours (CACHE_TIMEOUT_6_HOURS)
            - Key format: forum:list:{category_id}:{page}:{limit}:{filters_hash}
            - Invalidation: On ANY thread create/delete/update
            - Tracking: Keys tracked for non-Redis backend invalidation
        """
        category_part = category_id or "all"
        filters_hash = hashlib.sha256(str(sorted(filters.items())).encode()).hexdigest()
        cache_key = f"{CACHE_PREFIX_FORUM_LIST}:{category_part}:{page}:{limit}:{filters_hash}"
        cache.set(cache_key, data, CACHE_TIMEOUT_6_HOURS)

        # Track this key for fallback invalidation (non-Redis backends)
        try:
            cache_key_set = f"{CACHE_PREFIX_FORUM_LIST}:_keys"
            tracked_keys = cache.get(cache_key_set, set())
            if not isinstance(tracked_keys, set):
                tracked_keys = set()
            tracked_keys.add(cache_key)
            cache.set(cache_key_set, tracked_keys, CACHE_TIMEOUT_6_HOURS)
        except Exception as e:
            logger.debug(f"[CACHE] Failed to track key {cache_key}: {e}")

        logger.info(f"[CACHE] SET for thread list page {page} (6h TTL)")

    @staticmethod
    def get_category(slug: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached category by slug.

        Args:
            slug: URL-friendly identifier for category

        Returns:
            Cached category data dict or None if cache miss
        """
        cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for category {slug} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for category {slug}")
        return None

    @staticmethod
    def set_category(slug: str, data: Dict[str, Any]) -> None:
        """
        Cache category data.

        Args:
            slug: URL-friendly identifier for category
            data: Category data to cache (serialized dict)

        Cache Configuration:
            - TTL: 24 hours (CACHE_TIMEOUT_24_HOURS)
            - Key format: forum:category:{slug}
            - Invalidation: On category update, thread count change
        """
        cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
        cache.set(cache_key, data, CACHE_TIMEOUT_24_HOURS)
        logger.info(f"[CACHE] SET for category {slug} (24h TTL)")

    @staticmethod
    def get_post_list(thread_id: str, page: int, limit: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached post list for a thread.

        Args:
            thread_id: Thread UUID
            page: Page number for pagination
            limit: Results per page

        Returns:
            Cached post list data dict or None if cache miss
        """
        cache_key = f"{CACHE_PREFIX_FORUM_POST}:list:{thread_id}:{page}:{limit}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for post list thread {thread_id} page {page} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for post list thread {thread_id} page {page}")
        return None

    @staticmethod
    def set_post_list(thread_id: str, page: int, limit: int, data: Dict[str, Any]) -> None:
        """
        Cache post list data for a thread.

        Args:
            thread_id: Thread UUID
            page: Page number for pagination
            limit: Results per page
            data: Post list data to cache (serialized dict)

        Cache Configuration:
            - TTL: 1 hour (CACHE_TIMEOUT_1_HOUR)
            - Key format: forum:post:list:{thread_id}:{page}:{limit}
            - Invalidation: On post create/delete/edit in thread
        """
        cache_key = f"{CACHE_PREFIX_FORUM_POST}:list:{thread_id}:{page}:{limit}"
        cache.set(cache_key, data, CACHE_TIMEOUT_1_HOUR)
        logger.info(f"[CACHE] SET for post list thread {thread_id} page {page} (1h TTL)")

    @staticmethod
    def invalidate_thread(slug: str) -> None:
        """
        Invalidate thread cache on update.

        Called by signals when:
        - Thread is updated (title, content, pinned, locked)
        - Post count changes
        - View count increments

        Args:
            slug: Thread slug to invalidate
        """
        cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
        cache.delete(cache_key)
        logger.info(f"[CACHE] INVALIDATE for thread {slug}")

    @staticmethod
    def invalidate_thread_lists() -> None:
        """
        Invalidate all thread list caches.

        Called by signals when:
        - ANY thread is created/deleted/updated
        - Thread categories are changed
        - Pinned status is toggled

        Strategy:
        - Primary: Redis pattern matching (most efficient)
        - Fallback: Tracked key deletion (non-Redis backends)
        - Last resort: 6h natural expiration

        Note:
            This is intentionally aggressive - any thread content change
            invalidates ALL list caches. Trade-off between complexity
            and cache freshness favors simplicity.
        """
        # Try Redis pattern matching (most efficient)
        try:
            cache.delete_pattern(f"{CACHE_PREFIX_FORUM_LIST}:*")
            logger.info("[CACHE] INVALIDATE all thread lists (pattern match)")
            return
        except AttributeError:
            # Fallback: Use tracked keys for non-Redis backends
            try:
                cache_key_set = f"{CACHE_PREFIX_FORUM_LIST}:_keys"
                tracked_keys = cache.get(cache_key_set, set())

                if tracked_keys and isinstance(tracked_keys, set):
                    for key in tracked_keys:
                        cache.delete(key)
                    cache.delete(cache_key_set)
                    logger.info(f"[CACHE] INVALIDATE {len(tracked_keys)} thread list keys (tracked)")
                else:
                    logger.warning("[CACHE] No tracked thread list keys to invalidate (will expire naturally in 6h)")
            except Exception as e:
                logger.error(f"[CACHE] Failed to invalidate thread lists: {e}")

    @staticmethod
    def invalidate_category(slug: str) -> None:
        """
        Invalidate category cache on update.

        Called by signals when:
        - Category is updated
        - Thread count in category changes

        Args:
            slug: Category slug to invalidate
        """
        cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
        cache.delete(cache_key)
        logger.info(f"[CACHE] INVALIDATE for category {slug}")

    @staticmethod
    def invalidate_post_list(thread_id: str) -> None:
        """
        Invalidate all post list pages for a thread.

        Called by signals when:
        - Post is created/deleted in thread
        - Post is edited

        Args:
            thread_id: Thread UUID to invalidate
        """
        try:
            cache.delete_pattern(f"{CACHE_PREFIX_FORUM_POST}:list:{thread_id}:*")
            logger.info(f"[CACHE] INVALIDATE all post pages for thread {thread_id}")
        except AttributeError:
            logger.warning(f"[CACHE] Cache backend doesn't support delete_pattern, skipping post list invalidation for thread {thread_id}")

    @staticmethod
    def clear_all_forum_caches() -> None:
        """
        Nuclear option: clear ALL forum caches.

        Use cases:
        - Manual cache flush via management command
        - Major data migrations
        - Emergency cache clearing

        Warning:
            This will cause temporary performance degradation
            as caches are rebuilt from cold state.
        """
        try:
            cache.delete_pattern(f"{CACHE_PREFIX_FORUM_THREAD}:*")
            cache.delete_pattern(f"{CACHE_PREFIX_FORUM_LIST}:*")
            cache.delete_pattern(f"{CACHE_PREFIX_FORUM_CATEGORY}:*")
            cache.delete_pattern(f"{CACHE_PREFIX_FORUM_POST}:*")
            logger.warning("[CACHE] CLEARED all forum caches (nuclear option)")
        except AttributeError:
            logger.warning("[CACHE] Cache backend doesn't support delete_pattern, manual flush required")

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache performance metrics

        Usage:
            stats = ForumCacheService.get_cache_stats()
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
