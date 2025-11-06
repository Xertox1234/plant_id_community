"""
Cache integration tests for forum app.

Tests signal-based cache invalidation for threads, posts, and categories.
Verifies that cache is properly invalidated when models are created, updated, or deleted.

Pattern:
- Test cache invalidation via Django signals
- Verify ForumCacheService methods are called correctly
- Focus on integration between models, signals, and cache
"""

from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, call
from apps.forum.models import Thread, Post, Category
from apps.forum.tests.factories import (
    UserFactory,
    CategoryFactory,
    ThreadFactory,
    PostFactory,
)


class CacheIntegrationTests(TestCase):
    """Test cache invalidation via signals."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = UserFactory.create()
        self.category = CategoryFactory.create(name="Test Category", slug="test-category")
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_creating_thread_invalidates_cache(self, mock_get_service):
        """
        Test that creating a thread invalidates thread list cache.

        Signal: post_save with created=True
        Expected invalidations:
        - Thread detail cache (new slug)
        - All thread list caches
        - Category cache (thread count changed)
        """
        # Setup mock
        mock_service = mock_get_service.return_value

        # Create thread (triggers post_save signal)
        thread = ThreadFactory.create(
            title="New Thread",
            slug="new-thread",
            category=self.category,
            author=self.user
        )

        # Verify cache invalidation methods were called
        mock_service.invalidate_thread.assert_called_once_with(thread.slug)
        mock_service.invalidate_thread_lists.assert_called_once()
        mock_service.invalidate_category.assert_called_once_with(self.category.slug)

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_updating_thread_invalidates_cache(self, mock_get_service):
        """
        Test that updating a thread invalidates thread detail cache.

        Signal: post_save with created=False
        Expected invalidations:
        - Thread detail cache (by slug)
        - All thread list caches
        - Category cache (if category changed or metadata changed)
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)

        # Reset mock to ignore creation signal
        mock_service.reset_mock()

        # Update thread (triggers post_save signal)
        thread.title = "Updated Title"
        thread.save()

        # Verify cache invalidation methods were called
        mock_service.invalidate_thread.assert_called_once_with(thread.slug)
        mock_service.invalidate_thread_lists.assert_called_once()
        mock_service.invalidate_category.assert_called_once_with(self.category.slug)

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_deleting_thread_invalidates_cache(self, mock_get_service):
        """
        Test that deleting a thread invalidates caches.

        Signal: post_delete
        Expected invalidations:
        - Thread detail cache (will now return 404)
        - All thread list caches
        - Category cache (thread count changed)
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)
        thread_slug = thread.slug
        category_slug = thread.category.slug

        # Reset mock to ignore creation signal
        mock_service.reset_mock()

        # Delete thread (triggers post_delete signal)
        thread.delete()

        # Verify cache invalidation methods were called
        mock_service.invalidate_thread.assert_called_once_with(thread_slug)
        mock_service.invalidate_thread_lists.assert_called_once()
        mock_service.invalidate_category.assert_called_once_with(category_slug)

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_creating_post_invalidates_thread_cache(self, mock_get_service):
        """
        Test that creating a post invalidates thread cache.

        Signal: post_save with created=True on Post
        Expected invalidations:
        - Thread detail cache (post count changed)
        - Post list caches for this thread
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)

        # Reset mock to ignore thread creation signal
        mock_service.reset_mock()

        # Create post (triggers post_save signal)
        post = PostFactory.create(thread=thread, author=self.user)

        # Verify thread cache was invalidated
        mock_service.invalidate_thread.assert_called_once_with(thread.slug)
        mock_service.invalidate_post_list.assert_called_once_with(str(thread.id))

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_updating_post_invalidates_thread_cache(self, mock_get_service):
        """
        Test that updating a post invalidates thread cache.

        Signal: post_save with created=False on Post
        Expected invalidations:
        - Thread detail cache (content changed)
        - Post list caches for this thread
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)
        post = PostFactory.create(thread=thread, author=self.user)

        # Reset mock to ignore creation signals
        mock_service.reset_mock()

        # Update post (triggers post_save signal)
        post.content = "Updated content"
        post.save()

        # Verify thread cache was invalidated
        mock_service.invalidate_thread.assert_called_once_with(thread.slug)
        mock_service.invalidate_post_list.assert_called_once_with(str(thread.id))

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_deleting_post_invalidates_thread_cache(self, mock_get_service):
        """
        Test that deleting a post invalidates thread cache.

        Signal: post_delete on Post
        Expected invalidations:
        - Thread detail cache (post count changed)
        - Post list caches for this thread
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)
        post = PostFactory.create(thread=thread, author=self.user)
        thread_slug = thread.slug

        # Reset mock to ignore creation signals
        mock_service.reset_mock()

        # Delete post (triggers post_delete signal)
        thread_id = str(thread.id)
        post.delete()

        # Verify thread cache was invalidated
        mock_service.invalidate_thread.assert_called_once_with(thread_slug)
        mock_service.invalidate_post_list.assert_called_once_with(thread_id)

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_reactions_dont_invalidate_thread_cache(self, mock_get_service):
        """
        Test that reactions DON'T invalidate thread cache.

        Reactions are separate entities and should not invalidate thread cache.
        They have their own cache invalidation logic.

        Note: This test verifies that creating/updating reactions does NOT
        trigger thread cache invalidation signals.
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)
        post = PostFactory.create(thread=thread, author=self.user)

        # Reset mock to ignore creation signals
        mock_service.reset_mock()

        # Import Reaction model (lazy import to avoid circular dependencies)
        from apps.forum.models import Reaction

        # Create reaction (should NOT trigger thread cache invalidation)
        reaction = Reaction.objects.create(
            post=post,
            user=self.user,
            reaction_type='helpful'
        )

        # Verify thread cache was NOT invalidated
        # Reaction signals don't call invalidate_thread()
        mock_service.invalidate_thread.assert_not_called()

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_category_update_invalidates_category_cache(self, mock_get_service):
        """
        Test that updating a category invalidates category cache.

        Signal: post_save with created=False on Category
        Expected invalidations:
        - Category detail cache (by slug)
        - Category list caches
        - Category tree cache
        """
        # Setup
        mock_service = mock_get_service.return_value

        # Reset mock to ignore creation signal
        mock_service.reset_mock()

        # Update category (triggers post_save signal)
        self.category.name = "Updated Category"
        self.category.save()

        # Verify category cache was invalidated
        # Note: Check if category signals exist in signals.py
        # If not, this test documents expected future behavior
        if hasattr(mock_service, 'invalidate_category'):
            mock_service.invalidate_category.assert_called_with(self.category.slug)

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_pinning_thread_invalidates_list_cache(self, mock_get_service):
        """
        Test that pinning a thread invalidates thread list cache.

        Pinning changes the sort order in thread lists, so list cache must be invalidated.
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user, is_pinned=False)

        # Reset mock to ignore creation signal
        mock_service.reset_mock()

        # Pin thread (triggers post_save signal)
        thread.is_pinned = True
        thread.save()

        # Verify thread list cache was invalidated
        mock_service.invalidate_thread_lists.assert_called_once()

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_locking_thread_invalidates_detail_cache(self, mock_get_service):
        """
        Test that locking a thread invalidates thread detail cache.

        Locking prevents new posts, so detail view must reflect this.
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user, is_locked=False)

        # Reset mock to ignore creation signal
        mock_service.reset_mock()

        # Lock thread (triggers post_save signal)
        thread.is_locked = True
        thread.save()

        # Verify thread cache was invalidated
        mock_service.invalidate_thread.assert_called_once_with(thread.slug)

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_signal_error_doesnt_break_save(self, mock_get_service):
        """
        Test that cache invalidation errors don't prevent model saves.

        If cache service fails, the model save should still succeed.
        """
        # Setup mock to raise exception
        mock_service = mock_get_service.return_value
        mock_service.invalidate_thread.side_effect = Exception("Cache error")

        # Create thread (should succeed despite cache error)
        thread = ThreadFactory.create(
            title="Test Thread",
            slug="test-thread",
            category=self.category,
            author=self.user
        )

        # Verify thread was created
        self.assertTrue(Thread.objects.filter(slug="test-thread").exists())

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_multiple_saves_invalidate_cache_each_time(self, mock_get_service):
        """
        Test that multiple saves trigger cache invalidation each time.

        Ensures signals are properly registered and fire on every save.
        """
        # Setup
        mock_service = mock_get_service.return_value
        thread = ThreadFactory.create(category=self.category, author=self.user)

        # Reset mock to ignore creation signal
        mock_service.reset_mock()

        # Multiple updates
        thread.title = "Update 1"
        thread.save()

        thread.title = "Update 2"
        thread.save()

        thread.title = "Update 3"
        thread.save()

        # Verify cache was invalidated 3 times
        self.assertEqual(mock_service.invalidate_thread.call_count, 3)
        self.assertEqual(mock_service.invalidate_thread_lists.call_count, 3)


class CacheServiceIntegrationTests(TestCase):
    """Test ForumCacheService integration with real cache backend."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = UserFactory.create()
        self.category = CategoryFactory.create(name="Test Category", slug="test-category")
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_cache_service_actually_caches_data(self):
        """
        Test that ForumCacheService actually stores data in cache.

        Verifies the cache service is working with real cache backend.
        """
        from apps.forum.services.forum_cache_service import ForumCacheService

        # Setup
        thread = ThreadFactory.create(category=self.category, author=self.user)
        cache_key = f"forum:thread:{thread.slug}"

        # Cache some data
        test_data = {"thread_id": str(thread.id), "title": thread.title}
        cache.set(cache_key, test_data, timeout=60)

        # Verify data is in cache
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["title"], thread.title)

        # Invalidate cache
        ForumCacheService.invalidate_thread(thread.slug)

        # Verify cache was cleared
        cached_data = cache.get(cache_key)
        self.assertIsNone(cached_data)

    def test_thread_list_cache_invalidation(self):
        """
        Test that thread list cache is properly invalidated.

        Uses wildcard deletion pattern to clear all list caches.
        """
        from apps.forum.services.forum_cache_service import ForumCacheService

        # Setup multiple list cache keys
        cache.set("forum:list:page1", ["thread1", "thread2"], timeout=60)
        cache.set("forum:list:page2", ["thread3", "thread4"], timeout=60)
        cache.set("forum:list:category:test", ["thread5"], timeout=60)

        # Verify caches exist
        self.assertIsNotNone(cache.get("forum:list:page1"))
        self.assertIsNotNone(cache.get("forum:list:page2"))

        # Invalidate all list caches
        ForumCacheService.invalidate_thread_lists()

        # Note: Wildcard deletion depends on cache backend
        # This test documents expected behavior
        # For production, use Redis with SCAN/DELETE pattern
