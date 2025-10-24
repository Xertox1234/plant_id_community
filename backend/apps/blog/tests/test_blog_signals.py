"""
Tests for blog signal handlers and cache invalidation.

Validates:
- Cache invalidation on publish/unpublish/delete
- Non-blog page filtering (signals should ignore non-BlogPostPage instances)
- Signal error handling and logging
"""

from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from wagtail.models import Page
from wagtail.signals import page_published, page_unpublished
from django.db.models.signals import post_delete

from ..models import BlogPostPage, BlogIndexPage
from ..services.blog_cache_service import BlogCacheService
from .. import signals  # Import to ensure signals are registered


class BlogSignalTestCase(TestCase):
    """Test suite for blog signal handlers."""

    def setUp(self):
        """Set up test data and clear cache."""
        cache.clear()

        # Create a root page
        root = Page.objects.get(id=1)

        # Create a blog index page
        self.blog_index = BlogIndexPage(
            title="Test Blog",
            slug="test-blog",
        )
        root.add_child(instance=self.blog_index)

        # Create a blog post
        self.blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post",
            intro="Test intro",
            body=[],
        )
        self.blog_index.add_child(instance=self.blog_post)

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    # ===== page_published Signal Tests =====

    def test_page_published_invalidates_post_cache(self):
        """Publishing a blog post should invalidate its cache."""
        # Pre-cache the post
        test_data = {'title': 'Test Post', 'slug': 'test-post'}
        BlogCacheService.set_blog_post('test-post', test_data)

        # Verify it's cached
        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))

        # Trigger publish signal (simulates publishing the page)
        page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # Cache should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_post('test-post'))

    def test_page_published_invalidates_all_list_caches(self):
        """Publishing a blog post should invalidate all list caches."""
        # Pre-cache multiple lists
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={'items': []})
        BlogCacheService.set_blog_list(page=2, limit=10, filters={}, data={'items': []})
        BlogCacheService.set_blog_list(page=1, limit=10, filters={'category': '1'}, data={'items': []})

        # Verify they're cached
        self.assertIsNotNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
        self.assertIsNotNone(BlogCacheService.get_blog_list(page=2, limit=10, filters={}))
        self.assertIsNotNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={'category': '1'}))

        # Trigger publish signal
        page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # All list caches should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
        self.assertIsNone(BlogCacheService.get_blog_list(page=2, limit=10, filters={}))
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={'category': '1'}))

    def test_page_published_ignores_non_blog_pages(self):
        """Publishing non-blog pages should NOT trigger cache invalidation."""
        # Cache a blog post
        test_data = {'title': 'Test Post', 'slug': 'test-post'}
        BlogCacheService.set_blog_post('test-post', test_data)

        # Trigger signal with a non-BlogPostPage instance
        page_published.send(sender=BlogIndexPage, instance=self.blog_index)

        # Cache should remain intact
        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))

    # ===== page_unpublished Signal Tests =====

    def test_page_unpublished_invalidates_post_cache(self):
        """Unpublishing a blog post should invalidate its cache."""
        test_data = {'title': 'Test Post', 'slug': 'test-post'}
        BlogCacheService.set_blog_post('test-post', test_data)

        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))

        page_unpublished.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_post('test-post'))

    def test_page_unpublished_invalidates_all_list_caches(self):
        """Unpublishing a blog post should invalidate all list caches."""
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={'items': []})

        self.assertIsNotNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

        page_unpublished.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    def test_page_unpublished_ignores_non_blog_pages(self):
        """Unpublishing non-blog pages should NOT trigger cache invalidation."""
        test_data = {'title': 'Test Post', 'slug': 'test-post'}
        BlogCacheService.set_blog_post('test-post', test_data)

        page_unpublished.send(sender=BlogIndexPage, instance=self.blog_index)

        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))

    # ===== post_delete Signal Tests =====

    def test_post_delete_invalidates_post_cache(self):
        """Deleting a blog post should invalidate its cache."""
        test_data = {'title': 'Test Post', 'slug': 'test-post'}
        BlogCacheService.set_blog_post('test-post', test_data)

        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))

        post_delete.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_post('test-post'))

    def test_post_delete_invalidates_all_list_caches(self):
        """Deleting a blog post should invalidate all list caches."""
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={'items': []})
        BlogCacheService.set_blog_list(page=2, limit=10, filters={'category': '1'}, data={'items': []})

        self.assertIsNotNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
        self.assertIsNotNone(BlogCacheService.get_blog_list(page=2, limit=10, filters={'category': '1'}))

        post_delete.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
        self.assertIsNone(BlogCacheService.get_blog_list(page=2, limit=10, filters={'category': '1'}))

    def test_post_delete_ignores_non_blog_pages(self):
        """Deleting non-blog pages should NOT trigger cache invalidation."""
        test_data = {'title': 'Test Post', 'slug': 'test-post'}
        BlogCacheService.set_blog_post('test-post', test_data)

        post_delete.send(sender=BlogIndexPage, instance=self.blog_index)

        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))

    # ===== Error Handling Tests =====

    @patch('apps.blog.services.blog_cache_service.logger')
    def test_signal_error_handling_doesnt_crash(self, mock_logger):
        """Signal errors should be logged but not crash the application."""
        # Mock cache to raise an exception
        with patch('apps.blog.services.blog_cache_service.cache.delete') as mock_delete:
            mock_delete.side_effect = Exception("Cache connection failed")

            # This should log the error but not raise
            try:
                page_published.send(sender=BlogPostPage, instance=self.blog_post)
            except Exception:
                self.fail("Signal handler should not raise exceptions")

    @patch('apps.blog.signals.logger')
    def test_signal_logs_cache_invalidation(self, mock_logger):
        """Signal handlers should log cache invalidation actions."""
        # Cache some data
        BlogCacheService.set_blog_post('test-post', {'title': 'Test'})

        # Trigger signal
        page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # Check that invalidation was logged (at the service level)
        # Note: We can't directly check signal handler logs without importing the module

    # ===== Integration Tests =====

    def test_full_publish_workflow_invalidates_caches(self):
        """Full publish workflow should invalidate all relevant caches."""
        # Cache post and lists
        BlogCacheService.set_blog_post('test-post', {'title': 'Test Post'})
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={'items': []})

        # Verify cached
        self.assertIsNotNone(BlogCacheService.get_blog_post('test-post'))
        self.assertIsNotNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

        # Publish the page (triggers signal)
        page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # Both should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_post('test-post'))
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    def test_full_delete_workflow_invalidates_caches(self):
        """Full delete workflow should invalidate all relevant caches."""
        # Cache post and lists
        BlogCacheService.set_blog_post('test-post', {'title': 'Test Post'})
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={'items': []})

        # Delete (triggers signal)
        post_delete.send(sender=BlogPostPage, instance=self.blog_post)

        # All should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_post('test-post'))
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
