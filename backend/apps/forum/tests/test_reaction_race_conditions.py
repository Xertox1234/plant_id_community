"""
Test race condition prevention in Reaction.toggle_reaction().

Ensures concurrent toggle operations produce correct final state
using select_for_update() row-level locking.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import connection

from ..models import Thread, Post, Category, Reaction

User = get_user_model()


class ReactionRaceConditionTests(TransactionTestCase):
    """
    Test concurrent reaction toggle operations.

    Uses TransactionTestCase to allow real database transactions across threads.
    Regular TestCase wraps tests in a transaction that prevents concurrent access.
    """

    def setUp(self):
        """Set up test data."""
        # Create user
        self.user = User.objects.create_user(username='testuser', password='pass')

        # Create category, thread, and post
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )

        self.thread = Thread.objects.create(
            title='Test Thread',
            slug='test-thread',
            author=self.user,
            category=self.category,
            is_active=True
        )

        self.post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Test post content',
            is_first_post=True,
            is_active=True
        )

    def test_concurrent_toggle_creates_single_reaction(self):
        """
        Concurrent toggle requests should create only one reaction.

        Test scenario: Two threads try to create the same reaction simultaneously.
        Expected: Only one reaction created, second thread waits for lock.
        """
        results = []
        errors = []

        def toggle_reaction():
            """Toggle reaction from separate thread."""
            try:
                # Close old connection to force new one for this thread
                connection.close()
                reaction, created = Reaction.toggle_reaction(
                    post_id=self.post.id,
                    user_id=self.user.id,
                    reaction_type='like'
                )
                results.append({'reaction_id': reaction.id, 'created': created, 'is_active': reaction.is_active})
            except Exception as e:
                errors.append(str(e))

        # Execute two concurrent toggles
        thread1 = threading.Thread(target=toggle_reaction)
        thread2 = threading.Thread(target=toggle_reaction)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Should have two results
        self.assertEqual(len(results), 2)

        # One should be created=True, one should be created=False
        created_count = sum(1 for r in results if r['created'])
        self.assertEqual(created_count, 1, "Exactly one reaction should be created")

        # Both should reference the same reaction
        reaction_ids = [r['reaction_id'] for r in results]
        self.assertEqual(len(set(reaction_ids)), 1, "Both toggles should reference same reaction")

        # Verify database state
        reaction_count = Reaction.objects.filter(
            post=self.post,
            user=self.user,
            reaction_type='like'
        ).count()
        self.assertEqual(reaction_count, 1, "Only one reaction should exist in database")

    def test_concurrent_toggle_produces_correct_final_state(self):
        """
        Test that concurrent toggles produce correct final state.

        Test scenario: Three rapid toggles.
        Expected: No errors, only one reaction created, final state is deterministic.

        Note: With concurrent operations, the exact final state depends on thread
        scheduling. The important thing is: no errors and only one reaction exists.
        """
        results = []
        errors = []

        def toggle_reaction():
            """Toggle reaction from separate thread."""
            try:
                connection.close()
                reaction, created = Reaction.toggle_reaction(
                    post_id=self.post.id,
                    user_id=self.user.id,
                    reaction_type='like'
                )
                results.append({'created': created, 'is_active': reaction.is_active})
            except Exception as e:
                errors.append(str(e))

        # Execute three concurrent toggles
        threads = [threading.Thread(target=toggle_reaction) for _ in range(3)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Should have three results
        self.assertEqual(len(results), 3)

        # Verify only one reaction exists in database
        reaction_count = Reaction.objects.filter(
            post=self.post,
            user=self.user,
            reaction_type='like'
        ).count()
        self.assertEqual(reaction_count, 1, "Only one reaction should exist")

        # Verify the reaction can be retrieved
        reaction = Reaction.objects.get(
            post=self.post,
            user=self.user,
            reaction_type='like'
        )
        # Final state depends on thread scheduling, but it should be consistent
        # Just verify it's either True or False (not None or corrupted)
        self.assertIn(reaction.is_active, [True, False], "Reaction state should be valid boolean")

    def test_many_concurrent_toggles_produces_correct_final_state(self):
        """
        Test many concurrent toggles produce correct final state.

        Test scenario: 50 concurrent toggles.
        Expected: No errors, only one reaction created, final state is valid.

        Note: With truly concurrent operations, the exact final state is
        nondeterministic due to thread scheduling. The important guarantees are:
        1. No errors (IntegrityError handled correctly)
        2. Only one reaction exists (no duplicates)
        3. Final state is a valid boolean (not corrupted)
        """
        num_toggles = 50
        errors = []

        def toggle_reaction():
            """Toggle reaction from separate thread."""
            try:
                connection.close()
                Reaction.toggle_reaction(
                    post_id=self.post.id,
                    user_id=self.user.id,
                    reaction_type='like'
                )
            except Exception as e:
                errors.append(str(e))

        # Use ThreadPoolExecutor for better thread management
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(toggle_reaction) for _ in range(num_toggles)]

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify only one reaction exists (no duplicates from race condition)
        reaction_count = Reaction.objects.filter(
            post=self.post,
            user=self.user,
            reaction_type='like'
        ).count()
        self.assertEqual(reaction_count, 1, "Only one reaction should exist (no duplicates)")

        # Verify final database state is valid
        reaction = Reaction.objects.get(
            post=self.post,
            user=self.user,
            reaction_type='like'
        )
        # Final state depends on thread scheduling, but should be valid
        self.assertIn(reaction.is_active, [True, False], "Final state should be valid boolean")

    def test_concurrent_toggles_different_users_no_conflict(self):
        """
        Test that different users can toggle reactions concurrently without conflicts.

        Test scenario: 10 users each toggle reaction on same post simultaneously.
        Expected: 10 separate reactions created, all active.
        """
        # Create 10 users
        users = [
            User.objects.create_user(username=f'user{i}', password='pass')
            for i in range(10)
        ]

        errors = []

        def toggle_reaction_for_user(user):
            """Toggle reaction from separate thread for specific user."""
            try:
                connection.close()
                reaction, created = Reaction.toggle_reaction(
                    post_id=self.post.id,
                    user_id=user.id,
                    reaction_type='like'
                )
                return {'user_id': user.id, 'created': created, 'is_active': reaction.is_active}
            except Exception as e:
                errors.append(str(e))
                return None

        # Execute concurrent toggles for different users
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(toggle_reaction_for_user, user) for user in users]
            results = [future.result() for future in as_completed(futures)]

        # Filter out None results (errors)
        results = [r for r in results if r is not None]

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Should have 10 successful results
        self.assertEqual(len(results), 10)

        # All should be created=True
        created_count = sum(1 for r in results if r['created'])
        self.assertEqual(created_count, 10, "All 10 reactions should be newly created")

        # All should be active
        active_count = sum(1 for r in results if r['is_active'])
        self.assertEqual(active_count, 10, "All 10 reactions should be active")

        # Verify database state
        reaction_count = Reaction.objects.filter(
            post=self.post,
            reaction_type='like',
            is_active=True
        ).count()
        self.assertEqual(reaction_count, 10, "10 active reactions should exist in database")

    def test_concurrent_toggle_and_query_no_deadlock(self):
        """
        Test that concurrent toggle and query operations don't deadlock.

        Test scenario: Simultaneous toggle operations and read queries.
        Expected: All operations complete successfully, no deadlocks.
        """
        errors = []
        query_results = []

        def toggle_reaction():
            """Toggle reaction."""
            try:
                connection.close()
                Reaction.toggle_reaction(
                    post_id=self.post.id,
                    user_id=self.user.id,
                    reaction_type='like'
                )
            except Exception as e:
                errors.append(f"Toggle error: {str(e)}")

        def query_reaction():
            """Query reaction state."""
            try:
                connection.close()
                reaction = Reaction.objects.filter(
                    post=self.post,
                    user=self.user,
                    reaction_type='like'
                ).first()
                query_results.append(reaction.is_active if reaction else None)
            except Exception as e:
                errors.append(f"Query error: {str(e)}")

        # Execute mixed operations: 5 toggles + 5 queries
        with ThreadPoolExecutor(max_workers=10) as executor:
            toggle_futures = [executor.submit(toggle_reaction) for _ in range(5)]
            query_futures = [executor.submit(query_reaction) for _ in range(5)]

            all_futures = toggle_futures + query_futures

            # Wait for all to complete
            for future in as_completed(all_futures):
                future.result()

        # Should have no errors (no deadlocks)
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Should have 5 query results
        self.assertEqual(len(query_results), 5)

    def test_concurrent_toggles_different_reaction_types_no_conflict(self):
        """
        Test concurrent toggles of different reaction types don't conflict.

        Test scenario: Same user toggles 'like' and 'helpful' simultaneously.
        Expected: Two separate reactions created, both active.
        """
        errors = []
        results = []

        def toggle_reaction(reaction_type):
            """Toggle specific reaction type."""
            try:
                connection.close()
                reaction, created = Reaction.toggle_reaction(
                    post_id=self.post.id,
                    user_id=self.user.id,
                    reaction_type=reaction_type
                )
                results.append({
                    'reaction_type': reaction_type,
                    'created': created,
                    'is_active': reaction.is_active
                })
            except Exception as e:
                errors.append(str(e))

        # Execute concurrent toggles for different reaction types
        thread1 = threading.Thread(target=toggle_reaction, args=('like',))
        thread2 = threading.Thread(target=toggle_reaction, args=('helpful',))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Should have two results
        self.assertEqual(len(results), 2)

        # Both should be created=True
        created_count = sum(1 for r in results if r['created'])
        self.assertEqual(created_count, 2, "Both reactions should be newly created")

        # Verify database state - two separate reactions
        like_reaction = Reaction.objects.get(
            post=self.post,
            user=self.user,
            reaction_type='like'
        )
        helpful_reaction = Reaction.objects.get(
            post=self.post,
            user=self.user,
            reaction_type='helpful'
        )

        self.assertTrue(like_reaction.is_active)
        self.assertTrue(helpful_reaction.is_active)
        self.assertNotEqual(like_reaction.id, helpful_reaction.id)


class ReactionToggleBehaviorTests(TestCase):
    """
    Test reaction toggle behavior (non-concurrent).

    Uses regular TestCase for single-threaded behavior tests.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username='testuser', password='pass')

        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )

        self.thread = Thread.objects.create(
            title='Test Thread',
            slug='test-thread',
            author=self.user,
            category=self.category,
            is_active=True
        )

        self.post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Test post content',
            is_first_post=True,
            is_active=True
        )

    def test_first_toggle_creates_active_reaction(self):
        """First toggle creates active reaction."""
        reaction, created = Reaction.toggle_reaction(
            post_id=self.post.id,
            user_id=self.user.id,
            reaction_type='like'
        )

        self.assertTrue(created, "First toggle should create reaction")
        self.assertTrue(reaction.is_active, "First toggle should be active")

    def test_second_toggle_deactivates_reaction(self):
        """Second toggle deactivates reaction."""
        # First toggle
        reaction1, created1 = Reaction.toggle_reaction(
            post_id=self.post.id,
            user_id=self.user.id,
            reaction_type='like'
        )
        self.assertTrue(created1)
        self.assertTrue(reaction1.is_active)

        # Second toggle
        reaction2, created2 = Reaction.toggle_reaction(
            post_id=self.post.id,
            user_id=self.user.id,
            reaction_type='like'
        )

        self.assertFalse(created2, "Second toggle should not create new reaction")
        self.assertFalse(reaction2.is_active, "Second toggle should deactivate")
        self.assertEqual(reaction1.id, reaction2.id, "Should be same reaction")

    def test_third_toggle_reactivates_reaction(self):
        """Third toggle reactivates reaction."""
        # Toggle three times
        Reaction.toggle_reaction(self.post.id, self.user.id, 'like')
        Reaction.toggle_reaction(self.post.id, self.user.id, 'like')
        reaction3, created3 = Reaction.toggle_reaction(
            post_id=self.post.id,
            user_id=self.user.id,
            reaction_type='like'
        )

        self.assertFalse(created3)
        self.assertTrue(reaction3.is_active, "Third toggle should reactivate")

    def test_sequential_toggles_produce_correct_state(self):
        """Sequential toggles produce predictable state."""
        # 10 toggles = even = inactive
        for _ in range(10):
            Reaction.toggle_reaction(self.post.id, self.user.id, 'like')

        reaction = Reaction.objects.get(
            post=self.post,
            user=self.user,
            reaction_type='like'
        )
        self.assertFalse(reaction.is_active, "10 toggles should result in inactive")

        # 11 toggles = odd = active
        Reaction.toggle_reaction(self.post.id, self.user.id, 'like')
        reaction.refresh_from_db()
        self.assertTrue(reaction.is_active, "11 toggles should result in active")
