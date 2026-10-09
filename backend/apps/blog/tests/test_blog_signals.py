"""
Tests for blog signal handlers and cache invalidation.

Validates:
- Cache invalidation on publish/unpublish/delete
- Non-blog page filtering (signals should ignore non-BlogPostPage instances)
- Signal error handling and logging

The handlers invalidate from `transaction.on_commit` (todo 442), and a
`TestCase` body runs inside a transaction that never commits, so each trigger
is wrapped in `captureOnCommitCallbacks(execute=True)`; the deferral itself is
pinned with `execute=False`.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_delete
from django.test import TestCase
from wagtail.models import Page
from wagtail.signals import page_published, page_unpublished

from .. import signals  # noqa: F401  (import registers the signal receivers)
from ..models import BlogCategory, BlogComment, BlogIndexPage, BlogPostPage
from ..services.blog_cache_service import BlogCacheService

User = get_user_model()


class BlogSignalTestCase(TestCase):
    """Test suite for blog signal handlers."""

    def setUp(self):
        """Set up test data and clear cache."""
        cache.clear()

        # Create test user for blog posts
        self.user = User.objects.create_user(
            username="testauthor", email="author@example.com", password="testpass123"
        )

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
            author=self.user,
            publish_date=date.today(),
            introduction="<p>Test intro</p>",
            content_blocks=[],
        )
        self.blog_index.add_child(instance=self.blog_post)

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    # ===== page_published Signal Tests =====

    def test_page_published_invalidates_post_cache(self):
        """Publishing a blog post should invalidate its cache."""
        # Pre-cache the post
        test_data = {"title": "Test Post", "slug": "test-post"}
        BlogCacheService.set_blog_post("test-post", test_data)

        # Verify it's cached
        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

        # Trigger publish signal (simulates publishing the page)
        with self.captureOnCommitCallbacks(execute=True):
            page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # Cache should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))

    def test_page_published_invalidates_all_list_caches(self):
        """Publishing a blog post should invalidate all list caches."""
        # Pre-cache multiple lists
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})
        BlogCacheService.set_blog_list(page=2, limit=10, filters={}, data={"items": []})
        BlogCacheService.set_blog_list(
            page=1, limit=10, filters={"category": "1"}, data={"items": []}
        )

        # Verify they're cached
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={})
        )
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=2, limit=10, filters={})
        )
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={"category": "1"})
        )

        # Trigger publish signal
        with self.captureOnCommitCallbacks(execute=True):
            page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # All list caches should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
        self.assertIsNone(BlogCacheService.get_blog_list(page=2, limit=10, filters={}))
        self.assertIsNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={"category": "1"})
        )

    def test_page_published_ignores_non_blog_pages(self):
        """Publishing non-blog pages should NOT trigger cache invalidation."""
        # Cache a blog post
        test_data = {"title": "Test Post", "slug": "test-post"}
        BlogCacheService.set_blog_post("test-post", test_data)

        # Trigger signal with a non-BlogPostPage instance
        with self.captureOnCommitCallbacks(execute=True):
            page_published.send(sender=BlogIndexPage, instance=self.blog_index)

        # Cache should remain intact
        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

    def test_publish_invalidation_waits_for_the_commit(self):
        """Todo 442: the keys go AFTER the publishing transaction commits.

        `page_published` fires inside the publisher's `transaction.atomic()`
        (Wagtail's admin edit view, `save_spotlight_updates`). Deleting the keys
        there lets a concurrent GET re-cache the old row before the commit; the
        handler must defer to `on_commit`.
        """
        BlogCacheService.set_blog_post("test-post", {"title": "Test Post"})
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            page_published.send(sender=BlogPostPage, instance=self.blog_post)
            # Still cached: nothing has committed yet.
            self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))
            self.assertIsNotNone(
                BlogCacheService.get_blog_list(page=1, limit=10, filters={})
            )

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    def test_a_payload_cached_under_the_old_key_is_not_served(self):
        """Todo 442 review: plant_spotlight gained credit_lead/unsplash_href.

        A payload cached before the deploy lacks them, and the web renders such
        a credit without Unsplash's referral link for the rest of its 24h TTL.
        The versioned prefix makes those entries unreachable at deploy.
        """
        cache.set("blog:post:test-post", {"title": "cached before todo 442"})

        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))
        BlogCacheService.set_blog_post("test-post", {"title": "fresh"})
        self.assertEqual(
            BlogCacheService.get_blog_post("test-post"), {"title": "fresh"}
        )

    def test_every_other_invalidation_waits_for_the_commit(self):
        """Todo 442 review: the other receivers defer to `on_commit` too.

        Each trigger's own test runs its callbacks with `execute=True`, so it
        would pass just as well if that receiver deleted the keys at once.
        """
        comment = BlogComment.objects.create(
            post=self.blog_post, author=self.user, content="to delete"
        )

        def get_post():
            return BlogCacheService.get_blog_post("test-post")

        def get_list():
            return BlogCacheService.get_blog_list(page=1, limit=10, filters={})

        triggers = [
            (
                "unpublish",
                lambda: page_unpublished.send(
                    sender=BlogPostPage, instance=self.blog_post
                ),
                get_post,
            ),
            (
                "post_delete",
                lambda: post_delete.send(sender=BlogPostPage, instance=self.blog_post),
                get_post,
            ),
            (
                "comment save",
                lambda: BlogComment.objects.create(
                    post=self.blog_post, author=self.user, content="Nice post"
                ),
                get_post,
            ),
            ("comment delete", comment.delete, get_post),
            (
                "category save",
                lambda: BlogCategory.objects.create(name="Herbs", slug="herbs"),
                get_list,
            ),
        ]
        for name, trigger, cached in triggers:
            with self.subTest(trigger=name):
                BlogCacheService.set_blog_post("test-post", {"title": "Test Post"})
                BlogCacheService.set_blog_list(
                    page=1, limit=10, filters={}, data={"items": []}
                )
                with self.captureOnCommitCallbacks(execute=False) as callbacks:
                    trigger()
                    self.assertIsNotNone(cached(), "invalidated before the commit")
                for callback in callbacks:
                    callback()
                self.assertIsNone(cached())

    # ===== page_unpublished Signal Tests =====

    def test_page_unpublished_invalidates_post_cache(self):
        """Unpublishing a blog post should invalidate its cache."""
        test_data = {"title": "Test Post", "slug": "test-post"}
        BlogCacheService.set_blog_post("test-post", test_data)

        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

        with self.captureOnCommitCallbacks(execute=True):
            page_unpublished.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))

    def test_page_unpublished_invalidates_all_list_caches(self):
        """Unpublishing a blog post should invalidate all list caches."""
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})

        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={})
        )

        with self.captureOnCommitCallbacks(execute=True):
            page_unpublished.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    def test_page_unpublished_ignores_non_blog_pages(self):
        """Unpublishing non-blog pages should NOT trigger cache invalidation."""
        test_data = {"title": "Test Post", "slug": "test-post"}
        BlogCacheService.set_blog_post("test-post", test_data)

        with self.captureOnCommitCallbacks(execute=True):
            page_unpublished.send(sender=BlogIndexPage, instance=self.blog_index)

        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

    # ===== post_delete Signal Tests =====

    def test_post_delete_invalidates_post_cache(self):
        """Deleting a blog post should invalidate its cache."""
        test_data = {"title": "Test Post", "slug": "test-post"}
        BlogCacheService.set_blog_post("test-post", test_data)

        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

        with self.captureOnCommitCallbacks(execute=True):
            post_delete.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))

    def test_post_delete_invalidates_all_list_caches(self):
        """Deleting a blog post should invalidate all list caches."""
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})
        BlogCacheService.set_blog_list(
            page=2, limit=10, filters={"category": "1"}, data={"items": []}
        )

        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={})
        )
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=2, limit=10, filters={"category": "1"})
        )

        with self.captureOnCommitCallbacks(execute=True):
            post_delete.send(sender=BlogPostPage, instance=self.blog_post)

        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))
        self.assertIsNone(
            BlogCacheService.get_blog_list(page=2, limit=10, filters={"category": "1"})
        )

    def test_post_delete_ignores_non_blog_pages(self):
        """Deleting non-blog pages should NOT trigger cache invalidation."""
        test_data = {"title": "Test Post", "slug": "test-post"}
        BlogCacheService.set_blog_post("test-post", test_data)

        with self.captureOnCommitCallbacks(execute=True):
            post_delete.send(sender=BlogIndexPage, instance=self.blog_index)

        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

    # ===== Error Handling Tests =====

    @patch("apps.blog.services.blog_cache_service.logger")
    def test_signal_error_handling_doesnt_crash(self, mock_logger):
        """Signal errors should be logged but not crash the application."""
        # Mock cache to raise an exception
        with patch("apps.blog.services.blog_cache_service.cache.delete") as mock_delete:
            mock_delete.side_effect = Exception("Cache connection failed")

            # This should log the error but not raise
            try:
                with self.captureOnCommitCallbacks(execute=True):
                    page_published.send(sender=BlogPostPage, instance=self.blog_post)
            except Exception:
                self.fail("Signal handler should not raise exceptions")

    @patch("apps.blog.signals.logger")
    def test_signal_logs_cache_invalidation(self, mock_logger):
        """Signal handlers should log cache invalidation actions."""
        # Cache some data
        BlogCacheService.set_blog_post("test-post", {"title": "Test"})

        # Trigger signal
        with self.captureOnCommitCallbacks(execute=True):
            page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # Check that invalidation was logged (at the service level)
        # Note: We can't directly check signal handler logs without importing the module

    # ===== Integration Tests =====

    def test_full_publish_workflow_invalidates_caches(self):
        """Full publish workflow should invalidate all relevant caches."""
        # Cache post and lists
        BlogCacheService.set_blog_post("test-post", {"title": "Test Post"})
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})

        # Verify cached
        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={})
        )

        # Publish the page (triggers signal)
        with self.captureOnCommitCallbacks(execute=True):
            page_published.send(sender=BlogPostPage, instance=self.blog_post)

        # Both should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    def test_full_delete_workflow_invalidates_caches(self):
        """Full delete workflow should invalidate all relevant caches."""
        # Cache post and lists
        BlogCacheService.set_blog_post("test-post", {"title": "Test Post"})
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})

        # Delete (triggers signal)
        with self.captureOnCommitCallbacks(execute=True):
            post_delete.send(sender=BlogPostPage, instance=self.blog_post)

        # All should be invalidated
        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))
        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    # ===== BlogComment / BlogCategory invalidation (audit H4 / M8) =====
    # These exercise the NEW receivers via real model writes + the real cache —
    # if a receiver fails to invalidate (its try/except swallows errors silently),
    # the cached value survives and the test fails.

    def test_comment_save_invalidates_parent_post_cache(self):
        """Creating/approving a comment must invalidate the parent post cache (H4)."""
        BlogCacheService.set_blog_post("test-post", {"title": "Test Post"})
        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

        with self.captureOnCommitCallbacks(execute=True):
            BlogComment.objects.create(
                post=self.blog_post, author=self.user, content="Nice post"
            )

        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))

    def test_comment_save_invalidates_list_caches(self):
        """comment_count is embedded in list responses — a comment write must
        invalidate list caches (H4)."""
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={})
        )

        with self.captureOnCommitCallbacks(execute=True):
            BlogComment.objects.create(
                post=self.blog_post, author=self.user, content="Another"
            )

        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))

    def test_comment_delete_invalidates_parent_post_cache(self):
        """Deleting a comment must invalidate the parent post cache (H4)."""
        comment = BlogComment.objects.create(
            post=self.blog_post, author=self.user, content="to delete"
        )
        BlogCacheService.set_blog_post("test-post", {"title": "Test Post"})
        self.assertIsNotNone(BlogCacheService.get_blog_post("test-post"))

        with self.captureOnCommitCallbacks(execute=True):
            comment.delete()

        self.assertIsNone(BlogCacheService.get_blog_post("test-post"))

    def test_category_save_invalidates_list_caches(self):
        """Category name/slug/color are embedded in blog responses — a category
        write must invalidate list caches (M8)."""
        BlogCacheService.set_blog_list(page=1, limit=10, filters={}, data={"items": []})
        self.assertIsNotNone(
            BlogCacheService.get_blog_list(page=1, limit=10, filters={})
        )

        with self.captureOnCommitCallbacks(execute=True):
            BlogCategory.objects.create(name="Herbs", slug="herbs")

        self.assertIsNone(BlogCacheService.get_blog_list(page=1, limit=10, filters={}))


class InvalidationHookIsRobustTest(TestCase):
    """Todo 530: Django stops running a commit's remaining hooks when a
    non-robust one raises, so the blog's invalidation registers robust, and so
    does forum_host's BlogChunks enqueue, which shares the publish's queue."""

    def test_blog_invalidation_registers_a_robust_hook(self):
        from types import SimpleNamespace

        with patch("apps.blog.signals.transaction.on_commit") as on_commit:
            signals.invalidate_blog_cache_on_category_change(
                sender=BlogCategory, instance=SimpleNamespace(slug="ferns")
            )
        on_commit.assert_called_once()
        self.assertIs(on_commit.call_args.kwargs.get("robust"), True)

    def test_forum_rag_enqueue_registers_a_robust_hook(self):
        from apps.forum_host import signals as forum_signals

        page = BlogPostPage(pk=1, title="t", slug="t")
        with (
            patch("apps.forum_host.vector_indexes.rag_enabled", return_value=True),
            patch("apps.forum_host.signals.transaction.on_commit") as on_commit,
        ):
            forum_signals._enqueue_blog_chunk_sync(page, "publish")
        on_commit.assert_called_once()
        self.assertIs(on_commit.call_args.kwargs.get("robust"), True)
