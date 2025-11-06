"""
Test performance optimization for post reaction counts.

Tests the N+1 query optimization implemented in Issue #96.
"""

from django.test import TestCase, override_settings
from django.db import connection
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.request import Request
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

    @override_settings(
        DEBUG=True,
        DEBUG_TOOLBAR_CONFIG={'SHOW_TOOLBAR_CALLBACK': lambda request: False},
        # Disable debug toolbar middleware to prevent URL resolution errors in tests
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ]
    )
    def test_list_view_query_count(self):
        """
        List view should use optimized queries with annotations and prefetch.

        Regression protection: Ensures conditional annotations are used (Issue #113).
        Any increase from 3 queries indicates N+1 or missing optimization.

        Without optimization: 41+ queries (1 count + 1 main + 20 reaction + 20 attachment queries)
        With optimization: 3 queries (1 count + 1 annotated main + 1 attachment prefetch)
        """
        # Reset query counter
        connection.queries_log.clear()

        # Make list request
        response = self.client.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')

        self.assertEqual(response.status_code, 200)

        # Count queries
        query_count = len(connection.queries)

        # STRICT: Expect exactly 3 queries (pagination count + main + attachments prefetch)
        # Query 1: COUNT for pagination
        # Query 2: Main SELECT with reaction count annotations
        # Query 3: Prefetch attachments (one query for all posts)
        self.assertEqual(
            query_count,
            3,
            f"Performance regression detected! Expected 3 queries (1 count + 1 main + 1 prefetch), got {query_count}. "
            f"This indicates N+1 problem or missing optimization in PostViewSet. "
            f"See Issue #113 for details."
        )

        # ADDITIONAL: Verify annotations present in response
        first_post = response.data['results'][0]
        self.assertIn('reaction_counts', first_post)
        self.assertIsInstance(first_post['reaction_counts'], dict)
        self.assertIn('like', first_post['reaction_counts'])

    def test_annotations_correct_counts(self):
        """Annotated counts should match actual reaction counts."""
        post = self.posts[0]

        # Create viewset instance and get annotated queryset
        django_request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        django_request.user = self.user

        # Wrap Django request in DRF Request for query_params support
        request = Request(django_request)

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
        django_request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        django_request.user = self.user
        request = Request(django_request)

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
        django_request = self.factory.get(f'/api/v1/forum/posts/{post.id}/')
        django_request.user = self.user
        request = Request(django_request)

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

        # Create another user for the inactive reaction (unique constraint on post+user+type)
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        # Add inactive reaction from different user
        Reaction.objects.create(
            post=post,
            user=other_user,
            reaction_type='like',
            is_active=False
        )

        # Get annotated queryset
        django_request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        django_request.user = self.user
        request = Request(django_request)

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
        django_request = self.factory.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        django_request.user = self.user
        request = Request(django_request)

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

    @override_settings(
        DEBUG=True,
        DEBUG_TOOLBAR_CONFIG={'SHOW_TOOLBAR_CALLBACK': lambda request: False},
        # Disable debug toolbar middleware to prevent URL resolution errors in tests
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ]
    )
    def test_detail_view_query_count(self):
        """
        Detail view can use 2-3 queries (main + prefetch).

        Less strict than list view since prefetch_related uses separate queries.
        This is acceptable for detail views as they retrieve a single object.

        Expected queries:
        1. Main post query
        2. Prefetch reactions
        3. Possibly one more for related data

        Regression protection: Ensures prefetch_related is used efficiently.
        """
        post = self.posts[0]

        # Reset query counter
        connection.queries_log.clear()

        # Make detail request
        response = self.client.get(f'/api/v1/forum/posts/{post.id}/')

        self.assertEqual(response.status_code, 200)

        # Detail view: 1 main query + 1-2 prefetch queries
        query_count = len(connection.queries)
        self.assertLessEqual(
            query_count,
            3,
            f"Detail view query count too high: {query_count} (expected ≤3). "
            f"Ensure prefetch_related is used in PostViewSet.get_queryset() for detail action."
        )

        # Verify reaction counts are present
        self.assertIn('reaction_counts', response.data)
        self.assertEqual(response.data['reaction_counts']['like'], 1)
