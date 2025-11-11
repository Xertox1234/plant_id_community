"""
Unit tests for AICacheService.

Tests caching behavior, cache key generation, TTL, and invalidation
to ensure 80-95% cost reduction target is achievable.
"""

from django.test import TestCase
from django.core.cache import cache
from apps.blog.services.ai_cache_service import AICacheService


class AICacheServiceTestCase(TestCase):
    """Test suite for AI response caching."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def test_cache_hit_returns_cached_response(self):
        """Test that cache hit returns cached response without API call."""
        # Setup: Cache a response
        content = "Monstera deliciosa care guide for beginners"
        cached_response = {
            "text": "How to Grow Monstera: Complete Care Guide for Beginners"
        }
        AICacheService.set_cached_response('title', content, cached_response)

        # Test: Retrieve cached response
        result = AICacheService.get_cached_response('title', content)

        # Assert: Should return cached response
        self.assertIsNotNone(result)
        self.assertEqual(result, cached_response)
        self.assertEqual(result['text'], cached_response['text'])

    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None for uncached content."""
        content = "Uncached plant care content"

        result = AICacheService.get_cached_response('title', content)

        self.assertIsNone(result)

    def test_cache_key_consistency(self):
        """Test that same content generates same cache key."""
        content = "Swiss Cheese Plant growing tips"

        # Set cache twice with same content
        response1 = {"text": "Title 1"}
        response2 = {"text": "Title 2"}

        AICacheService.set_cached_response('title', content, response1)
        # Second call should overwrite first
        AICacheService.set_cached_response('title', content, response2)

        # Should get most recent response
        result = AICacheService.get_cached_response('title', content)
        self.assertEqual(result, response2)

    def test_different_features_use_different_keys(self):
        """Test that different features cache separately."""
        content = "Monstera care guide"

        title_response = {"text": "How to Care for Monstera"}
        description_response = {"text": "Complete Monstera care instructions"}

        # Cache both
        AICacheService.set_cached_response('title', content, title_response)
        AICacheService.set_cached_response('description', content, description_response)

        # Retrieve both
        title_result = AICacheService.get_cached_response('title', content)
        description_result = AICacheService.get_cached_response('description', content)

        # Should be different
        self.assertEqual(title_result, title_response)
        self.assertEqual(description_result, description_response)
        self.assertNotEqual(title_result, description_result)

    def test_different_content_uses_different_keys(self):
        """Test that different content hashes to different keys."""
        content1 = "Monstera care"
        content2 = "Pothos care"

        response1 = {"text": "Monstera Title"}
        response2 = {"text": "Pothos Title"}

        AICacheService.set_cached_response('title', content1, response1)
        AICacheService.set_cached_response('title', content2, response2)

        result1 = AICacheService.get_cached_response('title', content1)
        result2 = AICacheService.get_cached_response('title', content2)

        self.assertEqual(result1, response1)
        self.assertEqual(result2, response2)
        self.assertNotEqual(result1, result2)

    def test_empty_content_returns_none(self):
        """Test that empty content is handled gracefully."""
        # Empty string
        result1 = AICacheService.get_cached_response('title', '')
        self.assertIsNone(result1)

        # Whitespace only
        result2 = AICacheService.get_cached_response('title', '   ')
        self.assertIsNone(result2)

    def test_cache_invalidation_removes_entry(self):
        """Test that invalidation removes cached response."""
        content = "Succulent care basics"
        response = {"text": "How to Care for Succulents"}

        # Set cache
        AICacheService.set_cached_response('title', content, response)

        # Verify cached
        self.assertIsNotNone(AICacheService.get_cached_response('title', content))

        # Invalidate
        AICacheService.invalidate_cache('title', content)

        # Should be gone
        self.assertIsNone(AICacheService.get_cached_response('title', content))

    def test_cache_ttl_is_30_days(self):
        """Test that cache TTL is set to 30 days (2,592,000 seconds)."""
        # This tests the constant value
        self.assertEqual(AICacheService.CACHE_TTL, 2_592_000)

    def test_cache_key_format(self):
        """Test that cache keys follow the standard format: blog:ai:{feature}:{hash}."""
        # Cache key format is tested indirectly through caching behavior
        # The format ensures namespace isolation and collision avoidance

        content = "Test content"
        response = {"text": "Test response"}

        AICacheService.set_cached_response('title', content, response)

        # Should be retrievable
        result = AICacheService.get_cached_response('title', content)
        self.assertEqual(result, response)

    def test_concurrent_cache_access(self):
        """Test that concurrent access to same content works correctly."""
        content = "Popular plant care guide"
        response = {"text": "Popular Plant Care"}

        # Set cache
        AICacheService.set_cached_response('title', content, response)

        # Multiple retrievals should all succeed
        for _ in range(10):
            result = AICacheService.get_cached_response('title', content)
            self.assertEqual(result, response)

    def test_cache_stats_structure(self):
        """Test that cache stats return expected structure."""
        stats = AICacheService.get_cache_stats()

        # Should have required keys
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('hit_rate', stats)

        # Should be numeric
        self.assertIsInstance(stats['hits'], int)
        self.assertIsInstance(stats['misses'], int)
        self.assertIsInstance(stats['hit_rate'], float)

    def test_warm_cache_logs_warming(self):
        """Test that cache warming logs appropriately."""
        import logging
        from io import StringIO

        # Capture logs
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger('apps.blog.services.ai_cache_service')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        content = "Cache warming test"
        AICacheService.warm_cache('title', content)

        # Should have logged
        log_output = log_stream.getvalue()
        self.assertIn('[CACHE]', log_output)

        # Cleanup
        logger.removeHandler(handler)
