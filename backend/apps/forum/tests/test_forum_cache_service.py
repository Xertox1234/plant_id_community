"""
Test suite for Forum Cache Service.

Tests caching operations for threads, thread lists, categories, and posts
with focus on cache hit/miss patterns, TTL expiration, and invalidation.

Follows patterns from:
- test_blog_cache_service.py: Cache testing patterns
- forum_cache_service.py: Dual-strategy invalidation
- constants.py: Cache timeouts and prefixes

Test Coverage:
- Thread caching (get/set/invalidate)
- Thread list caching with filters (hash generation)
- Category caching (24h TTL)
- Post list caching
- Pattern-based invalidation (Redis + fallback)
- Key tracking for non-Redis backends
- Cache clearing (nuclear option)
- TTL expiration verification
"""

from unittest.mock import patch, MagicMock
from django.core.cache import cache
from django.test import TestCase, override_settings

from ..services.forum_cache_service import ForumCacheService
from ..constants import (
    CACHE_TIMEOUT_1_HOUR,
    CACHE_TIMEOUT_6_HOURS,
    CACHE_TIMEOUT_24_HOURS,
    CACHE_PREFIX_FORUM_THREAD,
    CACHE_PREFIX_FORUM_LIST,
    CACHE_PREFIX_FORUM_CATEGORY,
    CACHE_PREFIX_FORUM_POST,
)


class ThreadCachingTests(TestCase):
    """
    Test thread caching operations.

    Covers:
    - Cache miss returns None
    - Cache set stores data
    - Cache hit returns data
    - Cache invalidation
    - TTL: 1 hour
    """

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_get_thread_cache_miss(self):
        """
        Test that get_thread returns None on cache miss.

        Scenario:
        1. Thread not in cache
        2. get_thread returns None
        3. Signals DB query is needed
        """
        result = ForumCacheService.get_thread('test-thread-slug')

        self.assertIsNone(result)

    def test_set_and_get_thread(self):
        """
        Test that set_thread stores data and get_thread retrieves it.

        Scenario:
        1. set_thread with data
        2. get_thread retrieves same data
        3. Cache key format: forum:thread:{slug}
        """
        slug = 'test-thread'
        data = {
            'id': '123',
            'title': 'Test Thread',
            'author': 'testuser',
            'content': 'Test content'
        }

        # Set cache
        ForumCacheService.set_thread(slug, data)

        # Get cache
        result = ForumCacheService.get_thread(slug)

        # Should retrieve exact data
        self.assertEqual(result, data)

    def test_invalidate_thread(self):
        """
        Test that invalidate_thread removes cached data.

        Scenario:
        1. Thread in cache
        2. invalidate_thread called
        3. get_thread returns None
        """
        slug = 'test-thread'
        data = {'title': 'Test Thread'}

        # Set and verify cache
        ForumCacheService.set_thread(slug, data)
        self.assertIsNotNone(ForumCacheService.get_thread(slug))

        # Invalidate
        ForumCacheService.invalidate_thread(slug)

        # Should be None
        self.assertIsNone(ForumCacheService.get_thread(slug))

    def test_thread_cache_ttl_1_hour(self):
        """
        Test that thread cache uses 1-hour TTL.

        Verifies: CACHE_TIMEOUT_1_HOUR constant
        """
        slug = 'test-thread'
        data = {'title': 'Test Thread'}

        # Mock cache.set to verify TTL
        with patch.object(cache, 'set', wraps=cache.set) as mock_set:
            ForumCacheService.set_thread(slug, data)

            # Verify TTL argument
            cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
            mock_set.assert_called_once_with(cache_key, data, CACHE_TIMEOUT_1_HOUR)


class ThreadListCachingTests(TestCase):
    """
    Test thread list caching with pagination and filters.

    Covers:
    - Filter hash generation (deterministic)
    - Cache miss/hit with filters
    - Key tracking for invalidation
    - TTL: 6 hours
    """

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_get_thread_list_cache_miss(self):
        """
        Test that get_thread_list returns None on cache miss.
        """
        result = ForumCacheService.get_thread_list(
            page=1,
            limit=25,
            category_id='cat-123',
            filters={'search': 'plant'}
        )

        self.assertIsNone(result)

    def test_set_and_get_thread_list(self):
        """
        Test that set_thread_list stores and retrieves data.

        Scenario:
        1. set_thread_list with pagination + filters
        2. get_thread_list retrieves same data
        3. Cache key includes: page, limit, category_id, filters_hash
        """
        page = 1
        limit = 25
        category_id = 'cat-123'
        filters = {'search': 'monstera', 'is_pinned': True}
        data = {
            'results': [{'id': '1', 'title': 'Test Thread'}],
            'count': 1,
            'next': None,
            'previous': None
        }

        # Set cache
        ForumCacheService.set_thread_list(page, limit, category_id, filters, data)

        # Get cache
        result = ForumCacheService.get_thread_list(page, limit, category_id, filters)

        # Should retrieve exact data
        self.assertEqual(result, data)

    def test_filter_hash_deterministic(self):
        """
        Test that identical filters produce identical cache keys.

        Scenario:
        1. Cache with filters {'a': 1, 'b': 2}
        2. Retrieve with filters {'b': 2, 'a': 1} (different order)
        3. Should hit same cache key (filters sorted before hashing)
        """
        page = 1
        limit = 25
        category_id = None
        filters1 = {'search': 'plant', 'is_pinned': False}
        filters2 = {'is_pinned': False, 'search': 'plant'}  # Different order
        data = {'results': []}

        # Set with filters1
        ForumCacheService.set_thread_list(page, limit, category_id, filters1, data)

        # Get with filters2 (different order)
        result = ForumCacheService.get_thread_list(page, limit, category_id, filters2)

        # Should hit cache (deterministic hash)
        self.assertEqual(result, data)

    def test_different_filters_different_cache_keys(self):
        """
        Test that different filters create different cache keys.

        Scenario:
        1. Cache with filters {'search': 'plant'}
        2. Get with filters {'search': 'flower'}
        3. Should cache miss (different hash)
        """
        page = 1
        limit = 25
        category_id = None
        filters1 = {'search': 'plant'}
        filters2 = {'search': 'flower'}
        data = {'results': []}

        # Set with filters1
        ForumCacheService.set_thread_list(page, limit, category_id, filters1, data)

        # Get with filters2
        result = ForumCacheService.get_thread_list(page, limit, category_id, filters2)

        # Should cache miss
        self.assertIsNone(result)

    def test_thread_list_key_tracking(self):
        """
        Test that thread list keys are tracked for non-Redis invalidation.

        Scenario:
        1. set_thread_list adds key to tracked set
        2. Tracked set stored in cache: forum:list:_keys
        3. Used for fallback invalidation when Redis unavailable
        """
        page = 1
        limit = 25
        category_id = None
        filters = {}
        data = {'results': []}

        # Set cache
        ForumCacheService.set_thread_list(page, limit, category_id, filters, data)

        # Check tracked keys
        cache_key_set = f"{CACHE_PREFIX_FORUM_LIST}:_keys"
        tracked_keys = cache.get(cache_key_set)

        # Should have tracked key
        self.assertIsInstance(tracked_keys, set)
        self.assertGreater(len(tracked_keys), 0)

    def test_thread_list_ttl_6_hours(self):
        """
        Test that thread list cache uses 6-hour TTL.

        Verifies: CACHE_TIMEOUT_6_HOURS constant
        """
        page = 1
        limit = 25
        category_id = None
        filters = {}
        data = {'results': []}

        # Mock cache.set to verify TTL
        with patch.object(cache, 'set', wraps=cache.set) as mock_set:
            ForumCacheService.set_thread_list(page, limit, category_id, filters, data)

            # Verify TTL argument (first call is for data, may have second for tracking)
            calls = mock_set.call_args_list
            # First call should be for the actual data with 6h TTL
            first_call_timeout = calls[0][0][2]  # Third positional arg is timeout
            self.assertEqual(first_call_timeout, CACHE_TIMEOUT_6_HOURS)


class CategoryCachingTests(TestCase):
    """
    Test category caching operations.

    Covers:
    - Cache miss/hit
    - Long TTL (24 hours - rarely change)
    - Invalidation
    """

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_get_category_cache_miss(self):
        """
        Test that get_category returns None on cache miss.
        """
        result = ForumCacheService.get_category('plant-care')

        self.assertIsNone(result)

    def test_set_and_get_category(self):
        """
        Test that set_category stores and retrieves data.

        Scenario:
        1. set_category with data
        2. get_category retrieves same data
        3. Cache key format: forum:category:{slug}
        """
        slug = 'plant-care'
        data = {
            'id': '123',
            'name': 'Plant Care',
            'description': 'Tips for caring for plants',
            'thread_count': 42
        }

        # Set cache
        ForumCacheService.set_category(slug, data)

        # Get cache
        result = ForumCacheService.get_category(slug)

        # Should retrieve exact data
        self.assertEqual(result, data)

    def test_invalidate_category(self):
        """
        Test that invalidate_category removes cached data.

        Called when:
        - Category is updated
        - Thread count changes
        """
        slug = 'plant-care'
        data = {'name': 'Plant Care'}

        # Set and verify cache
        ForumCacheService.set_category(slug, data)
        self.assertIsNotNone(ForumCacheService.get_category(slug))

        # Invalidate
        ForumCacheService.invalidate_category(slug)

        # Should be None
        self.assertIsNone(ForumCacheService.get_category(slug))

    def test_category_ttl_24_hours(self):
        """
        Test that category cache uses 24-hour TTL.

        Rationale: Categories rarely change, long TTL acceptable.
        Verifies: CACHE_TIMEOUT_24_HOURS constant
        """
        slug = 'plant-care'
        data = {'name': 'Plant Care'}

        # Mock cache.set to verify TTL
        with patch.object(cache, 'set', wraps=cache.set) as mock_set:
            ForumCacheService.set_category(slug, data)

            # Verify TTL argument
            cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
            mock_set.assert_called_once_with(cache_key, data, CACHE_TIMEOUT_24_HOURS)


class PostListCachingTests(TestCase):
    """
    Test post list caching for threads.

    Covers:
    - Cache miss/hit with pagination
    - Invalidation for specific thread
    - TTL: 1 hour
    """

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_get_post_list_cache_miss(self):
        """
        Test that get_post_list returns None on cache miss.
        """
        result = ForumCacheService.get_post_list(
            thread_id='thread-123',
            page=1,
            limit=20
        )

        self.assertIsNone(result)

    def test_set_and_get_post_list(self):
        """
        Test that set_post_list stores and retrieves data.

        Scenario:
        1. set_post_list with pagination
        2. get_post_list retrieves same data
        3. Cache key format: forum:post:list:{thread_id}:{page}:{limit}
        """
        thread_id = 'thread-123'
        page = 1
        limit = 20
        data = {
            'results': [
                {'id': '1', 'content': 'First post'},
                {'id': '2', 'content': 'Second post'}
            ],
            'count': 2
        }

        # Set cache
        ForumCacheService.set_post_list(thread_id, page, limit, data)

        # Get cache
        result = ForumCacheService.get_post_list(thread_id, page, limit)

        # Should retrieve exact data
        self.assertEqual(result, data)

    def test_different_pages_different_cache_keys(self):
        """
        Test that different pages have different cache keys.

        Scenario:
        1. Cache page 1
        2. Get page 2
        3. Should cache miss
        """
        thread_id = 'thread-123'
        limit = 20
        data_page_1 = {'results': [{'id': '1'}]}
        data_page_2 = {'results': [{'id': '2'}]}

        # Cache page 1
        ForumCacheService.set_post_list(thread_id, 1, limit, data_page_1)

        # Get page 2
        result = ForumCacheService.get_post_list(thread_id, 2, limit)

        # Should cache miss
        self.assertIsNone(result)

    def test_post_list_ttl_1_hour(self):
        """
        Test that post list cache uses 1-hour TTL.

        Verifies: CACHE_TIMEOUT_1_HOUR constant
        """
        thread_id = 'thread-123'
        page = 1
        limit = 20
        data = {'results': []}

        # Mock cache.set to verify TTL
        with patch.object(cache, 'set', wraps=cache.set) as mock_set:
            ForumCacheService.set_post_list(thread_id, page, limit, data)

            # Verify TTL argument
            cache_key = f"{CACHE_PREFIX_FORUM_POST}:list:{thread_id}:{page}:{limit}"
            mock_set.assert_called_once_with(cache_key, data, CACHE_TIMEOUT_1_HOUR)


class BulkInvalidationTests(TestCase):
    """
    Test bulk invalidation strategies.

    Covers:
    - invalidate_thread_lists (all list caches)
    - invalidate_post_list (all pages for thread)
    - Pattern matching (Redis)
    - Tracked key deletion (fallback)
    """

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_invalidate_thread_lists_pattern_matching(self):
        """
        Test that invalidate_thread_lists uses Redis pattern matching.

        Scenario:
        1. Cache multiple thread lists (different pages/filters)
        2. Call invalidate_thread_lists
        3. All thread list caches cleared
        """
        # Cache multiple thread lists
        ForumCacheService.set_thread_list(1, 25, None, {}, {'results': []})
        ForumCacheService.set_thread_list(2, 25, None, {}, {'results': []})
        ForumCacheService.set_thread_list(1, 25, 'cat-1', {}, {'results': []})

        # Verify caches exist
        self.assertIsNotNone(ForumCacheService.get_thread_list(1, 25, None, {}))

        # Invalidate all
        ForumCacheService.invalidate_thread_lists()

        # All should be None
        self.assertIsNone(ForumCacheService.get_thread_list(1, 25, None, {}))
        self.assertIsNone(ForumCacheService.get_thread_list(2, 25, None, {}))
        self.assertIsNone(ForumCacheService.get_thread_list(1, 25, 'cat-1', {}))

    @patch('apps.forum.services.forum_cache_service.cache')
    def test_invalidate_thread_lists_fallback_tracked_keys(self, mock_cache):
        """
        Test that invalidate_thread_lists falls back to tracked keys.

        Scenario:
        1. Redis pattern matching unavailable (AttributeError)
        2. Uses tracked keys for deletion
        3. Deletes each key individually
        """
        # Mock cache without delete_pattern
        mock_cache.get.return_value = {'key1', 'key2', 'key3'}
        mock_cache.delete.return_value = None
        mock_cache.delete_pattern.side_effect = AttributeError('Not supported')

        # Call invalidation
        ForumCacheService.invalidate_thread_lists()

        # Should call delete for each tracked key
        self.assertGreaterEqual(mock_cache.delete.call_count, 3)

    def test_invalidate_post_list_pattern_matching(self):
        """
        Test that invalidate_post_list invalidates all pages.

        Scenario:
        1. Cache multiple pages for same thread
        2. Call invalidate_post_list
        3. All pages cleared
        """
        thread_id = 'thread-123'

        # Cache multiple pages
        ForumCacheService.set_post_list(thread_id, 1, 20, {'results': []})
        ForumCacheService.set_post_list(thread_id, 2, 20, {'results': []})
        ForumCacheService.set_post_list(thread_id, 3, 20, {'results': []})

        # Verify caches exist
        self.assertIsNotNone(ForumCacheService.get_post_list(thread_id, 1, 20))

        # Invalidate all pages for thread
        ForumCacheService.invalidate_post_list(thread_id)

        # All pages should be None
        self.assertIsNone(ForumCacheService.get_post_list(thread_id, 1, 20))
        self.assertIsNone(ForumCacheService.get_post_list(thread_id, 2, 20))
        self.assertIsNone(ForumCacheService.get_post_list(thread_id, 3, 20))


class NuclearClearTests(TestCase):
    """
    Test clear_all_forum_caches (nuclear option).

    Use cases:
    - Manual cache flush
    - Major data migrations
    - Emergency cache clearing
    """

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_clear_all_forum_caches(self):
        """
        Test that clear_all_forum_caches removes all forum caches.

        Scenario:
        1. Cache threads, lists, categories, posts
        2. Call clear_all_forum_caches
        3. All caches cleared
        """
        # Cache various types
        ForumCacheService.set_thread('thread-1', {'title': 'Thread 1'})
        ForumCacheService.set_thread_list(1, 25, None, {}, {'results': []})
        ForumCacheService.set_category('cat-1', {'name': 'Category 1'})
        ForumCacheService.set_post_list('thread-1', 1, 20, {'results': []})

        # Verify caches exist
        self.assertIsNotNone(ForumCacheService.get_thread('thread-1'))
        self.assertIsNotNone(ForumCacheService.get_category('cat-1'))

        # Nuclear clear
        ForumCacheService.clear_all_forum_caches()

        # All should be None
        self.assertIsNone(ForumCacheService.get_thread('thread-1'))
        self.assertIsNone(ForumCacheService.get_thread_list(1, 25, None, {}))
        self.assertIsNone(ForumCacheService.get_category('cat-1'))
        self.assertIsNone(ForumCacheService.get_post_list('thread-1', 1, 20))


class CacheStatsTests(TestCase):
    """
    Test get_cache_stats placeholder.

    Note: Full implementation requires ViewSet instrumentation.
    """

    def test_get_cache_stats_returns_dict(self):
        """
        Test that get_cache_stats returns placeholder dict.

        Future: Will contain real hit rate metrics from ViewSets.
        """
        stats = ForumCacheService.get_cache_stats()

        # Should return dict with expected keys
        self.assertIsInstance(stats, dict)
        self.assertIn('hit_rate', stats)
        self.assertIn('total_requests', stats)
        self.assertIn('cache_hits', stats)
        self.assertIn('cache_misses', stats)
        self.assertIn('note', stats)
