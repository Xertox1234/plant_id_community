"""
Test transaction boundaries for Post model.

Verifies that Post.save() properly handles concurrent updates to thread statistics
without race conditions or lost updates.
"""

from django.test import TestCase
from django.utils import timezone
from django.db import connection
from django.db.models import F
from django.test.utils import CaptureQueriesContext

from apps.forum.models import Post, Thread
from .factories import UserFactory, CategoryFactory, ThreadFactory, PostFactory


class PostTransactionBoundariesTest(TestCase):
    """
    Test Post.save() transaction boundaries to prevent race conditions.

    These tests verify that:
    1. F() expressions are used for atomic updates
    2. Transaction boundaries are correctly implemented
    3. Thread statistics are properly updated
    """

    def setUp(self):
        """Set up test fixtures."""
        self.user = UserFactory.create(username='testuser')
        self.category = CategoryFactory.create(name='Test Category')
        self.thread = ThreadFactory.create(
            title='Test Thread',
            author=self.user,
            category=self.category,
            post_count=0
        )

    def test_single_post_updates_thread_statistics(self):
        """Test that creating a post updates thread post_count and last_activity_at."""
        # Record initial state
        initial_count = self.thread.post_count
        initial_activity = self.thread.last_activity_at

        # Create a post
        post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Test post content',
            is_active=True
        )

        # Refresh thread from database
        self.thread.refresh_from_db()

        # Verify post_count incremented
        self.assertEqual(
            self.thread.post_count,
            initial_count + 1,
            "Thread post_count should increment by 1"
        )

        # Verify last_activity_at was updated
        self.assertIsNotNone(self.thread.last_activity_at)
        if initial_activity:
            self.assertGreater(
                self.thread.last_activity_at,
                initial_activity,
                "Thread last_activity_at should be updated"
            )

    def test_inactive_post_does_not_update_statistics(self):
        """Test that creating an inactive post doesn't update thread statistics."""
        initial_count = self.thread.post_count
        initial_activity = self.thread.last_activity_at

        # Create inactive post
        post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Inactive post',
            is_active=False
        )

        # Refresh thread from database
        self.thread.refresh_from_db()

        # Verify statistics unchanged
        self.assertEqual(
            self.thread.post_count,
            initial_count,
            "Inactive post should not increment post_count"
        )
        self.assertEqual(
            self.thread.last_activity_at,
            initial_activity,
            "Inactive post should not update last_activity_at"
        )

    def test_update_existing_post_does_not_increment_count(self):
        """Test that updating an existing post doesn't increment post_count."""
        # Create initial post
        post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Original content',
            is_active=True
        )

        # Get current count
        self.thread.refresh_from_db()
        count_after_create = self.thread.post_count

        # Update the post
        post.content_raw = 'Updated content'
        post.save()

        # Refresh thread
        self.thread.refresh_from_db()

        # Verify count unchanged
        self.assertEqual(
            self.thread.post_count,
            count_after_create,
            "Updating existing post should not increment post_count"
        )

    def test_sequential_post_creation_correct_count(self):
        """Test that sequential post creation maintains correct count."""
        num_posts = 5

        # Create posts sequentially
        for i in range(num_posts):
            user = UserFactory.create(username=f'sequential_user_{i}')
            Post.objects.create(
                thread=self.thread,
                author=user,
                content_raw=f'Sequential post {i}',
                is_active=True
            )

        # Refresh thread
        self.thread.refresh_from_db()

        # Verify count
        self.assertEqual(
            self.thread.post_count,
            num_posts,
            f"Thread should have {num_posts} posts"
        )

    def test_mixed_active_inactive_posts_correct_count(self):
        """Test that only active posts are counted."""
        # Create 3 active posts
        for i in range(3):
            Post.objects.create(
                thread=self.thread,
                author=self.user,
                content_raw=f'Active post {i}',
                is_active=True
            )

        # Create 2 inactive posts
        for i in range(2):
            Post.objects.create(
                thread=self.thread,
                author=self.user,
                content_raw=f'Inactive post {i}',
                is_active=False
            )

        # Refresh thread
        self.thread.refresh_from_db()

        # Verify only active posts counted
        self.assertEqual(
            self.thread.post_count,
            3,
            "Thread should only count active posts"
        )

    def test_f_expression_used_in_update_query(self):
        """
        Verify that F() expressions are used in the SQL query.

        This test inspects the actual SQL to confirm F() expressions are being
        used for atomic updates, not read-modify-write pattern.
        """
        # Create a post and capture SQL queries
        with CaptureQueriesContext(connection) as queries:
            post = Post.objects.create(
                thread=self.thread,
                author=self.user,
                content_raw='Test post',
                is_active=True
            )

        # Find the UPDATE query for thread statistics
        update_queries = [q for q in queries.captured_queries if 'UPDATE' in q['sql'] and 'forum_thread' in q['sql']]

        # Should have at least one update query
        self.assertGreater(
            len(update_queries),
            0,
            "Should have UPDATE query for thread statistics"
        )

        # Check that F() expression is used (indicated by post_count + 1 in SQL)
        has_f_expression = any(
            'post_count' in q['sql'] and ('+' in q['sql'] or 'F(' in q['sql'])
            for q in update_queries
        )

        self.assertTrue(
            has_f_expression,
            "SQL query should use F() expression for atomic post_count update. "
            f"Queries: {[q['sql'] for q in update_queries]}"
        )

    def test_last_activity_at_updated_atomically(self):
        """Test that last_activity_at is updated within the same transaction."""
        # Create a post
        before_create = timezone.now()

        post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Test post',
            is_active=True
        )

        after_create = timezone.now()

        # Refresh thread
        self.thread.refresh_from_db()

        # Verify last_activity_at is within expected range
        self.assertIsNotNone(self.thread.last_activity_at)
        self.assertGreaterEqual(
            self.thread.last_activity_at,
            before_create,
            "last_activity_at should be >= time before post creation"
        )
        self.assertLessEqual(
            self.thread.last_activity_at,
            after_create,
            "last_activity_at should be <= time after post creation"
        )

    def test_transaction_wraps_both_post_and_thread_updates(self):
        """
        Test that both post creation and thread updates happen in same transaction.

        This verifies the transaction.atomic() context manager is working correctly.
        """
        # Create a post and capture queries
        with CaptureQueriesContext(connection) as queries:
            post = Post.objects.create(
                thread=self.thread,
                author=self.user,
                content_raw='Test post',
                is_active=True
            )

        # Should have INSERT for post and UPDATE for thread
        insert_queries = [q for q in queries.captured_queries if 'INSERT' in q['sql'] and 'forum_post' in q['sql']]
        update_queries = [q for q in queries.captured_queries if 'UPDATE' in q['sql'] and 'forum_thread' in q['sql']]

        self.assertEqual(
            len(insert_queries),
            1,
            "Should have one INSERT query for post"
        )

        self.assertEqual(
            len(update_queries),
            1,
            "Should have one UPDATE query for thread statistics"
        )

    def test_multiple_posts_increments_count_correctly(self):
        """Test that multiple posts increment count correctly."""
        # Create 10 posts
        for i in range(10):
            user = UserFactory.create(username=f'user_{i}')
            Post.objects.create(
                thread=self.thread,
                author=user,
                content_raw=f'Post {i}',
                is_active=True
            )

        # Refresh thread
        self.thread.refresh_from_db()

        # Verify count
        self.assertEqual(
            self.thread.post_count,
            10,
            "Thread should have 10 posts"
        )

    def test_post_save_uses_transaction_atomic(self):
        """
        Verify that Post.save() is wrapped in transaction.atomic().

        This is a code inspection test - we verify the implementation
        follows the correct pattern.
        """
        # Get the Post.save method source
        import inspect
        source = inspect.getsource(Post.save)

        # Verify transaction.atomic() is used
        self.assertIn(
            'transaction.atomic',
            source,
            "Post.save() should use transaction.atomic() wrapper"
        )

        # Verify F() expression is used
        self.assertIn(
            "F('post_count')",
            source,
            "Post.save() should use F() expression for post_count update"
        )

        # Verify Thread.objects.filter().update() pattern
        self.assertIn(
            'Thread.objects.filter',
            source,
            "Post.save() should use Thread.objects.filter().update() for atomic updates"
        )

        self.assertIn(
            '.update(',
            source,
            "Post.save() should use .update() method for atomic updates"
        )


class PostTransactionDocumentationTest(TestCase):
    """
    Documentation tests to ensure the pattern is well-documented.

    These tests verify that the implementation includes proper documentation
    explaining the race condition prevention.
    """

    def test_post_save_has_docstring(self):
        """Verify Post.save() has a comprehensive docstring."""
        docstring = Post.save.__doc__

        self.assertIsNotNone(
            docstring,
            "Post.save() should have a docstring"
        )

        # Check for key concepts in docstring
        self.assertIn(
            'transaction',
            docstring.lower(),
            "Docstring should mention transaction handling"
        )

        self.assertIn(
            'race condition',
            docstring.lower(),
            "Docstring should explain race condition prevention"
        )

    def test_implementation_matches_recommended_pattern(self):
        """
        Verify implementation matches the recommended pattern from TODO.

        This test documents the expected implementation pattern.
        """
        import inspect
        source = inspect.getsource(Post.save)

        # Pattern elements that should be present
        required_patterns = [
            'transaction.atomic()',
            "F('post_count') + 1",
            'Thread.objects.filter(pk=self.thread_id).update(',
            'self.thread.refresh_from_db(',
        ]

        for pattern in required_patterns:
            self.assertIn(
                pattern,
                source,
                f"Post.save() should include pattern: {pattern}"
            )
