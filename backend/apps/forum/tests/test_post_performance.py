"""
Test performance optimization for post reaction counts.

Tests the N+1 query optimization implemented in Issue #96.
"""

from django.test import TestCase, override_settings
from django.db import connection
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory
from apps.forum.models import Category, Thread, Post, Reaction
from apps.forum.viewsets import PostViewSet
from apps.forum.serializers import PostSerializer

User = get_user_model()


class PostPerformanceTestCase(TestCase):
    """Test N+1 query optimization for post list view (Issue #96)"""

    def setUp(self):
        """Set up test data with posts and reactions."""
        self.client = APIClient()
        self.factory = APIRequestFactory()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create category and thread
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        self.thread = Thread.objects.create(
            title='Test Thread',
            slug='test-thread',
            author=self.user,
            category=self.category
        )

        # Create 20 posts with reactions
        self.posts = []
        for i in range(20):
            post = Post.objects.create(
                thread=self.thread,
                author=self.user,
                content_raw=f'Test post {i}',
                content_format='plain'
            )
            self.posts.append(post)

            # Add 3 reactions to each post (different types)
            for reaction_type in ['like', 'love', 'helpful']:
                Reaction.objects.create(
                    post=post,
                    user=self.user,
                    reaction_type=reaction_type,
                    is_active=True
                )

    @override_settings(DEBUG=True)
    def test_list_view_query_count(self):
        """
        List view should use database annotations (1 query).

        Without optimization: 21 queries (1 main + 20 reaction queries)
        With optimization: 1 query (annotations included)
        """
        # Reset query counter
        connection.queries_log.clear()

        # Make list request
        response = self.client.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')

        self.assertEqual(response.status_code, 200)

        # Count queries (allow some overhead for auth/session)
        query_count = len(connection.queries)

        # Should be much less than 21 queries
        # Allow up to 5 queries for auth/session overhead
        self.assertLess(
            query_count,
            10,
            f"Expected <10 queries, got {query_count}. N+1 query issue still exists!"
        )

        # Verify reaction counts are present in response
        first_post = response.data['results'][0]
        self.assertIn('reaction_counts', first_post)
        self.assertIsInstance(first_post['reaction_counts'], dict)
        self.assertIn('like', first_post['reaction_counts'])

    def test_annotations_correct_counts(self):
        """Annotated counts should match actual reaction counts."""
        post = self.posts[0]

        # Create viewset instance and get annotated queryset
        request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        request.user = self.user

        viewset = PostViewSet()
        viewset.action = 'list'
        viewset.request = request
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        annotated_post = qs.filter(id=post.id).first()

        # Verify annotations exist
        self.assertTrue(hasattr(annotated_post, 'like_count'))
        self.assertTrue(hasattr(annotated_post, 'love_count'))
        self.assertTrue(hasattr(annotated_post, 'helpful_count'))
        self.assertTrue(hasattr(annotated_post, 'thanks_count'))

        # Verify counts match actual
        actual_like_count = post.reactions.filter(
            reaction_type='like',
            is_active=True
        ).count()
        self.assertEqual(annotated_post.like_count, actual_like_count)
        self.assertEqual(annotated_post.like_count, 1)  # We created 1 like per post

        actual_love_count = post.reactions.filter(
            reaction_type='love',
            is_active=True
        ).count()
        self.assertEqual(annotated_post.love_count, actual_love_count)
        self.assertEqual(annotated_post.love_count, 1)  # We created 1 love per post

    def test_serializer_uses_annotations(self):
        """Serializer should use pre-computed annotations when available."""
        # Get annotated queryset
        request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        request.user = self.user

        viewset = PostViewSet()
        viewset.action = 'list'
        viewset.request = request
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        post = qs.first()

        # Serialize with annotations
        serializer = PostSerializer(post, context={'request': request})
        counts = serializer.data['reaction_counts']

        # Should have all reaction types
        self.assertIn('like', counts)
        self.assertIn('love', counts)
        self.assertIn('helpful', counts)
        self.assertIn('thanks', counts)

        # Counts should be integers
        self.assertIsInstance(counts['like'], int)
        self.assertIsInstance(counts['love'], int)

        # Verify counts match what we created
        self.assertEqual(counts['like'], 1)
        self.assertEqual(counts['love'], 1)
        self.assertEqual(counts['helpful'], 1)
        self.assertEqual(counts['thanks'], 0)  # We didn't create any thanks

    def test_serializer_fallback_without_annotations(self):
        """Serializer should fall back to counting when annotations not present."""
        post = self.posts[0]

        # Get post WITHOUT annotations (simulates detail view)
        request = self.factory.get(f'/api/v1/forum/posts/{post.id}/')
        request.user = self.user

        viewset = PostViewSet()
        viewset.action = 'retrieve'
        viewset.request = request
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        post_detail = qs.filter(id=post.id).first()

        # Verify annotations DON'T exist (detail view uses prefetch)
        self.assertFalse(hasattr(post_detail, 'like_count'))

        # Serialize without annotations
        serializer = PostSerializer(post_detail, context={'request': request})
        counts = serializer.data['reaction_counts']

        # Should still work with fallback logic
        self.assertIn('like', counts)
        self.assertEqual(counts['like'], 1)
        self.assertEqual(counts['love'], 1)
        self.assertEqual(counts['helpful'], 1)
        self.assertEqual(counts['thanks'], 0)

    def test_inactive_reactions_not_counted(self):
        """Inactive reactions should not be included in counts."""
        post = self.posts[0]

        # Add inactive reaction
        Reaction.objects.create(
            post=post,
            user=self.user,
            reaction_type='like',
            is_active=False
        )

        # Get annotated queryset
        request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        request.user = self.user

        viewset = PostViewSet()
        viewset.action = 'list'
        viewset.request = request
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        annotated_post = qs.filter(id=post.id).first()

        # Should still count only 1 like (the active one)
        self.assertEqual(annotated_post.like_count, 1)

    def test_distinct_counts_with_multiple_joins(self):
        """Count should use distinct=True to prevent duplicate counting."""
        post = self.posts[0]

        # Get annotated queryset
        request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        request.user = self.user

        viewset = PostViewSet()
        viewset.action = 'list'
        viewset.request = request
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        annotated_post = qs.filter(id=post.id).first()

        # Verify counts are correct (not doubled due to joins)
        self.assertEqual(annotated_post.like_count, 1)
        self.assertEqual(annotated_post.love_count, 1)
        self.assertEqual(annotated_post.helpful_count, 1)

    @override_settings(DEBUG=True)
    def test_detail_view_still_uses_prefetch(self):
        """Detail view should still use prefetch_related for reactions."""
        post = self.posts[0]

        # Reset query counter
        connection.queries_log.clear()

        # Make detail request
        response = self.client.get(f'/api/v1/forum/posts/{post.id}/')

        self.assertEqual(response.status_code, 200)

        # Detail view should prefetch reactions (not annotate)
        # Should be 2-4 queries (post + prefetches + auth)
        query_count = len(connection.queries)
        self.assertLess(
            query_count,
            10,
            f"Detail view query count should be low: {query_count}"
        )

        # Verify reaction counts are present
        self.assertIn('reaction_counts', response.data)
        self.assertEqual(response.data['reaction_counts']['like'], 1)
