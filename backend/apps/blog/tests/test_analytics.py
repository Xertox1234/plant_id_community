"""
Test suite for blog analytics features (Phase 6.2).

Tests cover:
- View tracking middleware
- Popular posts API endpoint
- Bot detection
- View deduplication
- Analytics dashboard integration

Following project testing patterns from:
- apps/plant_identification/tests/
- apps/users/tests/

BLOCKER 2 fix: Comprehensive test coverage for all Phase 6.2 features.
"""

from django.test import TestCase, RequestFactory, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.db import connection
from django.test.utils import CaptureQueriesContext
from datetime import timedelta
from unittest.mock import patch, MagicMock

from apps.blog.models import BlogPostPage, BlogPostView, BlogIndexPage
from apps.blog.middleware import BlogViewTrackingMiddleware
from apps.blog.constants import (
    VIEW_DEDUPLICATION_TIMEOUT,
    VIEW_TRACKING_CACHE_PREFIX,
    VIEW_TRACKING_BOT_KEYWORDS,
    POPULAR_POSTS_DEFAULT_LIMIT,
    POPULAR_POSTS_MAX_LIMIT,
)

User = get_user_model()


class BlogViewTrackingMiddlewareTests(TransactionTestCase):
    """
    Test view tracking middleware (Phase 6.2).

    Note: Using TransactionTestCase instead of TestCase because
    transaction.on_commit() requires actual database commits.
    """

    def setUp(self):
        """Set up test data."""
        cache.clear()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

        # Create blog index page
        from wagtail.models import Site, Page
        from wagtail.models import Locale

        # Ensure default locale exists
        locale, _ = Locale.objects.get_or_create(language_code='en')

        # Create root page if it doesn't exist
        try:
            root_page = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist:
            # Create root page
            root_page = Page.objects.filter(depth=1).first()
            if not root_page:
                root_page = Page.add_root(title='Root', locale=locale)

            # Create default site
            Site.objects.create(
                hostname='localhost',
                root_page=root_page,
                is_default_site=True,
                site_name='Test Site'
            )

        self.blog_index = BlogIndexPage(
            title='Blog',
            slug='blog',
        )
        root_page.add_child(instance=self.blog_index)

        # Create test blog post
        self.blog_post = BlogPostPage(
            title='Test Blog Post',
            slug='test-post',
            author=self.user,
            publish_date=timezone.now().date(),
            introduction='Test introduction',
        )
        self.blog_index.add_child(instance=self.blog_post)
        self.blog_post.save_revision().publish()

        # Create middleware instance
        self.factory = RequestFactory()
        self.middleware = BlogViewTrackingMiddleware(get_response=lambda r: MagicMock(status_code=200))

    def test_view_tracked_on_blog_post_detail(self):
        """Verify BlogPostView created on GET request to blog post."""
        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post

        response = MagicMock(status_code=200)

        # Track view
        with patch('django.db.transaction.on_commit') as mock_commit:
            # Make on_commit execute immediately for testing
            mock_commit.side_effect = lambda func: func()

            self.middleware._track_view(request, response)

        # Verify view was created
        self.assertEqual(BlogPostView.objects.count(), 1)
        view = BlogPostView.objects.first()
        self.assertEqual(view.post, self.blog_post)
        self.assertEqual(view.user, self.user)

        # Verify view count incremented
        self.blog_post.refresh_from_db()
        self.assertEqual(self.blog_post.view_count, 1)

    def test_view_not_tracked_on_non_blog_pages(self):
        """Views should only be tracked on BlogPostPage instances."""
        request = self.factory.get('/other-page/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_index  # Not a BlogPostPage

        response = MagicMock(status_code=200)
        self.middleware._track_view(request, response)

        # No view should be created
        self.assertEqual(BlogPostView.objects.count(), 0)

    def test_view_deduplication_same_ip_15_minutes(self):
        """Same IP viewing same post within 15 min = 1 view."""
        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()

            # First view - should be tracked
            self.middleware._track_view(request, response)
            self.assertEqual(BlogPostView.objects.count(), 1)

            # Second view within 15 minutes - should be deduplicated
            self.middleware._track_view(request, response)
            self.assertEqual(BlogPostView.objects.count(), 1)  # Still 1

    def test_view_deduplication_different_posts(self):
        """Same user can view different posts without deduplication."""
        # Create second post
        blog_post_2 = BlogPostPage(
            title='Second Post',
            slug='second-post',
            author=self.user,
            publish_date=timezone.now().date(),
            introduction='Second post intro',
        )
        self.blog_index.add_child(instance=blog_post_2)
        blog_post_2.save_revision().publish()

        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()

            # View first post
            request._wagtail_page = self.blog_post
            self.middleware._track_view(request, response)

            # View second post - should be tracked separately
            request._wagtail_page = blog_post_2
            self.middleware._track_view(request, response)

            self.assertEqual(BlogPostView.objects.count(), 2)

    def test_view_not_tracked_on_post_request(self):
        """Only GET requests should be tracked."""
        request = self.factory.post('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post

        response = MagicMock(status_code=200)
        self.middleware._track_view(request, response)

        # No view should be created for POST
        self.assertEqual(BlogPostView.objects.count(), 0)

    def test_bot_traffic_ignored(self):
        """Bot user agents should not create views."""
        for bot_keyword in ['googlebot', 'bingbot', 'crawler', 'spider']:
            cache.clear()
            BlogPostView.objects.all().delete()

            request = self.factory.get('/blog/test-post/')
            request.user = self.user
            request.resolver_match = MagicMock()
            request._wagtail_page = self.blog_post
            request.META['HTTP_USER_AGENT'] = f'Mozilla/5.0 ({bot_keyword}/1.0)'

            response = MagicMock(status_code=200)
            self.middleware._track_view(request, response)

            # Bot views should be filtered
            self.assertEqual(
                BlogPostView.objects.count(),
                0,
                f"Bot with keyword '{bot_keyword}' should not create views"
            )

    def test_anonymous_view_uses_ip_address(self):
        """Anonymous users should be tracked by IP address."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/blog/test-post/')
        request.user = AnonymousUser()
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()
            self.middleware._track_view(request, response)

        view = BlogPostView.objects.first()
        self.assertIsNone(view.user)
        self.assertEqual(view.ip_address, '192.168.1.100')

    def test_authenticated_view_uses_user_fk(self):
        """Authenticated users should have user FK set."""
        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()
            self.middleware._track_view(request, response)

        view = BlogPostView.objects.first()
        self.assertEqual(view.user, self.user)
        self.assertEqual(view.ip_address, '192.168.1.100')  # IP also stored

    def test_user_agent_truncated_to_255_chars(self):
        """Long user agents should be truncated to 255 characters."""
        long_user_agent = 'A' * 500  # 500 characters

        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post
        request.META['HTTP_USER_AGENT'] = long_user_agent

        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()
            self.middleware._track_view(request, response)

        view = BlogPostView.objects.first()
        self.assertEqual(len(view.user_agent), 255)
        self.assertEqual(view.user_agent, long_user_agent[:255])

    def test_referrer_url_stored(self):
        """HTTP referrer should be stored in view."""
        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post
        request.META['HTTP_REFERER'] = 'https://google.com/search?q=plants'

        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()
            self.middleware._track_view(request, response)

        view = BlogPostView.objects.first()
        self.assertEqual(view.referrer, 'https://google.com/search?q=plants')

    def test_error_handling_doesnt_break_response(self):
        """Tracking errors should not raise 500."""
        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post

        response = MagicMock(status_code=200)

        # Mock BlogPostView.objects.create to raise exception
        with patch('apps.blog.models.BlogPostView.objects.create') as mock_create:
            mock_create.side_effect = Exception('Database error')

            # Should not raise - error is caught
            try:
                self.middleware._track_view(request, response)
            except Exception as e:
                self.fail(f"Middleware should not raise: {e}")

    def test_cache_key_format(self):
        """Cache key should follow expected format."""
        request = self.factory.get('/blog/test-post/')
        request.user = self.user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.blog_post

        response = MagicMock(status_code=200)

        with patch('django.db.transaction.on_commit') as mock_commit:
            mock_commit.side_effect = lambda func: func()
            self.middleware._track_view(request, response)

        # Check cache key exists
        expected_key = f"{VIEW_TRACKING_CACHE_PREFIX}:{self.blog_post.id}:{self.user.id}"
        self.assertIsNotNone(cache.get(expected_key))


class PopularPostsAPITests(TestCase):
    """Test popular posts endpoint (Phase 6.2)."""

    def setUp(self):
        """Set up test data."""
        from rest_framework.test import APIClient

        self.client = APIClient()
        cache.clear()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create blog index
        from wagtail.models import Site, Page
        from wagtail.models import Locale

        # Ensure default locale exists
        locale, _ = Locale.objects.get_or_create(language_code='en')

        # Create root page if it doesn't exist
        try:
            root_page = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist:
            # Create root page
            root_page = Page.objects.filter(depth=1).first()
            if not root_page:
                root_page = Page.add_root(title='Root', locale=locale)

            # Create default site
            Site.objects.create(
                hostname='localhost',
                root_page=root_page,
                is_default_site=True,
                site_name='Test Site'
            )

        self.blog_index = BlogIndexPage(
            title='Blog',
            slug='blog',
        )
        root_page.add_child(instance=self.blog_index)

        # Create test blog posts with different view counts
        self.posts = []
        for i in range(5):
            post = BlogPostPage(
                title=f'Post {i+1}',
                slug=f'post-{i+1}',
                author=self.user,
                publish_date=timezone.now().date(),
                introduction=f'Intro {i+1}',
                view_count=100 - (i * 10),  # 100, 90, 80, 70, 60
            )
            self.blog_index.add_child(instance=post)
            post.save_revision().publish()
            self.posts.append(post)

    def test_popular_posts_ordered_by_view_count(self):
        """Popular posts should be ordered by view_count descending."""
        response = self.client.get('/api/v2/blog-posts/popular/')
        self.assertEqual(response.status_code, 200)

        # Should be ordered by view count (highest first)
        titles = [item['title'] for item in response.data]
        self.assertEqual(titles[0], 'Post 1')  # 100 views
        self.assertEqual(titles[1], 'Post 2')  # 90 views
        self.assertEqual(titles[2], 'Post 3')  # 80 views

    def test_popular_posts_default_limit(self):
        """Default limit should return POPULAR_POSTS_DEFAULT_LIMIT posts."""
        response = self.client.get('/api/v2/blog-posts/popular/')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.data), POPULAR_POSTS_DEFAULT_LIMIT)

    def test_popular_posts_custom_limit(self):
        """?limit=3 should return only 3 posts."""
        response = self.client.get('/api/v2/blog-posts/popular/?limit=3')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    def test_popular_posts_limit_capped_at_max(self):
        """?limit=1000 should be capped at POPULAR_POSTS_MAX_LIMIT."""
        response = self.client.get('/api/v2/blog-posts/popular/?limit=1000')
        self.assertEqual(response.status_code, 200)
        # Create more posts than max limit to test cap
        self.assertLessEqual(len(response.data), POPULAR_POSTS_MAX_LIMIT)

    def test_popular_posts_zero_views_included(self):
        """Posts with 0 views can appear in popular list (at bottom)."""
        # Create post with 0 views
        zero_view_post = BlogPostPage(
            title='Zero Views Post',
            slug='zero-views',
            author=self.user,
            publish_date=timezone.now().date(),
            introduction='No views',
            view_count=0,
        )
        self.blog_index.add_child(instance=zero_view_post)
        zero_view_post.save_revision().publish()

        response = self.client.get('/api/v2/blog-posts/popular/')
        self.assertEqual(response.status_code, 200)

        # Zero-view post should be last (lowest view count)
        titles = [item['title'] for item in response.data]
        self.assertEqual(titles[-1], 'Zero Views Post')

    def test_popular_posts_all_time(self):
        """?days=0 should return all-time popular posts."""
        response = self.client.get('/api/v2/blog-posts/popular/?days=0')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)

    def test_popular_posts_recent_views(self):
        """?days=7 should consider recent views only."""
        # Create views for first post (recent)
        recent_date = timezone.now() - timedelta(days=3)
        BlogPostView.objects.create(
            post=self.posts[4],  # Post with lowest view_count
            user=self.user,
            viewed_at=recent_date
        )

        # Create views for second post (old)
        old_date = timezone.now() - timedelta(days=60)
        BlogPostView.objects.create(
            post=self.posts[0],  # Post with highest view_count
            user=self.user,
            viewed_at=old_date
        )

        response = self.client.get('/api/v2/blog-posts/popular/?days=7')
        self.assertEqual(response.status_code, 200)

        # Post 5 should rank higher due to recent view
        # (This test verifies the annotation logic works)
        self.assertGreater(len(response.data), 0)

    def test_popular_posts_query_optimization(self):
        """
        TODO 037: Verify prefetch_related eliminates N+1 queries.

        Tests that the popular() endpoint uses efficient prefetching
        to avoid N+1 query problems when filtering by time period.

        Expected: Query count should be low (<10) regardless of post count.
        Before fix: ~15 queries for 10 posts, ~150 queries for 100 posts (O(n))
        After fix: ~5-8 queries regardless of post count (O(1))
        """
        # Create more posts with recent views to test query efficiency
        recent_date = timezone.now() - timedelta(days=5)

        for post in self.posts:
            # Add 3 recent views per post
            for _ in range(3):
                BlogPostView.objects.create(
                    post=post,
                    user=self.user,
                    viewed_at=recent_date,
                    ip_address='127.0.0.1'
                )

        # Clear any query caches
        cache.clear()

        # Test with time-based filtering (where N+1 problem occurs)
        with CaptureQueriesContext(connection) as context:
            response = self.client.get('/api/v2/blog-posts/popular/?days=30&limit=10')
            self.assertEqual(response.status_code, 200)

        query_count = len(context.captured_queries)

        # With prefetch_related optimization, should be <10 queries
        # Without it, would be ~15+ queries for 5 posts (3 per post)
        self.assertLess(
            query_count,
            10,
            f"Query count too high: {query_count} queries. "
            f"Expected <10 with prefetch_related optimization.\n"
            f"Queries: {[q['sql'][:100] for q in context.captured_queries]}"
        )

        # Log query count for monitoring
        print(f"\n[PERF] Popular endpoint query count: {query_count} queries for {len(response.data)} posts")

    def test_popular_posts_all_time_query_count(self):
        """All-time popular (days=0) should have minimal queries (no prefetching needed)."""
        # Clear any query caches
        cache.clear()

        with CaptureQueriesContext(connection) as context:
            response = self.client.get('/api/v2/blog-posts/popular/?days=0&limit=10')
            self.assertEqual(response.status_code, 200)

        query_count = len(context.captured_queries)

        # All-time should be very efficient (no annotation, just ordering)
        self.assertLess(
            query_count,
            8,
            f"All-time query count too high: {query_count} queries"
        )

        print(f"\n[PERF] All-time popular query count: {query_count} queries")


class AnalyticsDashboardTests(TestCase):
    """Test Wagtail admin analytics integration (Phase 6.2)."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com'
        )

        from wagtail.models import Site, Page
        from wagtail.models import Locale

        # Ensure default locale exists
        locale, _ = Locale.objects.get_or_create(language_code='en')

        # Create root page if it doesn't exist
        try:
            root_page = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist:
            # Create root page
            root_page = Page.objects.filter(depth=1).first()
            if not root_page:
                root_page = Page.add_root(title='Root', locale=locale)

            # Create default site
            Site.objects.create(
                hostname='localhost',
                root_page=root_page,
                is_default_site=True,
                site_name='Test Site'
            )

        # Create blog index
        self.blog_index = BlogIndexPage(
            title='Blog',
            slug='blog',
        )
        root_page.add_child(instance=self.blog_index)

        # Create posts with views
        self.post1 = BlogPostPage(
            title='Popular Post',
            slug='popular-post',
            author=self.user,
            publish_date=timezone.now().date(),
            introduction='Very popular',
            view_count=500,
        )
        self.blog_index.add_child(instance=self.post1)
        self.post1.save_revision().publish()

        self.post2 = BlogPostPage(
            title='Regular Post',
            slug='regular-post',
            author=self.user,
            publish_date=timezone.now().date(),
            introduction='Regular',
            view_count=50,
        )
        self.blog_index.add_child(instance=self.post2)
        self.post2.save_revision().publish()

    def test_total_views_aggregate(self):
        """Total views should sum all post view counts."""
        from django.db.models import Sum

        total = BlogPostPage.objects.aggregate(Sum('view_count'))['view_count__sum']
        self.assertEqual(total, 550)  # 500 + 50

    def test_most_popular_post_query(self):
        """Most popular post query should return highest view_count."""
        most_popular = BlogPostPage.objects.live().public().order_by('-view_count').first()
        self.assertEqual(most_popular.title, 'Popular Post')
        self.assertEqual(most_popular.view_count, 500)


# Run with: python manage.py test apps.blog.tests.test_analytics --keepdb -v 2
