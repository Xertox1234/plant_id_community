"""
Test rate limiting integration for forum viewsets.

Tests Phase 4.3: TrustLevelService integration into Thread, Post, and Reaction viewsets.
Verifies that daily action limits are enforced based on user trust levels.
"""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.forum.models import UserProfile, Category, Thread, Post
from apps.forum.services.trust_level_service import TrustLevelService
from .factories import UserFactory, CategoryFactory, ThreadFactory, PostFactory

User = get_user_model()


class RateLimitingBaseTestCase(APITestCase):
    """Base test case for rate limiting tests with trust level setup."""

    def setUp(self):
        """Set up test environment with users at different trust levels."""
        # Clear cache to ensure clean state
        cache.clear()

        # Mock spam detection to prevent false positives in rate limiting tests
        # Rate limiting tests should test rate limiting, not spam detection
        self.spam_patcher = patch('apps.forum.services.spam_detection_service.SpamDetectionService.is_spam')
        self.mock_spam = self.spam_patcher.start()
        self.mock_spam.return_value = {
            'is_spam': False,
            'spam_score': 0,
            'reasons': [],
            'details': {}
        }

        # Create API client
        self.client = APIClient()

        # Create category for testing
        self.category = CategoryFactory.create(name='Test Category')

        # Create NEW user (10 posts/day, 3 threads/day, 50 reactions/day)
        # NEW: 0 days, 0 posts requirement
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        self.new_user.date_joined = timezone.now()  # Just joined
        self.new_user.save()
        self.new_profile = UserProfile.objects.create(
            user=self.new_user,
            trust_level='new',
            post_count=1,
            thread_count=0
        )

        # Create BASIC user (50 posts/day, 10 threads/day, 200 reactions/day)
        # BASIC: 7 days, 5 posts requirement
        self.basic_user = User.objects.create_user(username='basicuser', password='pass')
        self.basic_user.date_joined = timezone.now() - timedelta(days=10)  # 10 days ago
        self.basic_user.save()
        self.basic_profile = UserProfile.objects.create(
            user=self.basic_user,
            trust_level='basic',
            post_count=10,
            thread_count=2
        )

        # Create TRUSTED user (100 posts/day, 25 threads/day, 500 reactions/day)
        # TRUSTED: 30 days, 25 posts requirement
        self.trusted_user = User.objects.create_user(username='trusteduser', password='pass')
        self.trusted_user.date_joined = timezone.now() - timedelta(days=35)  # 35 days ago
        self.trusted_user.save()
        self.trusted_profile = UserProfile.objects.create(
            user=self.trusted_user,
            trust_level='trusted',
            post_count=50,
            thread_count=10
        )

        # Create VETERAN user (unlimited)
        # VETERAN: 90 days, 100 posts requirement
        self.veteran_user = User.objects.create_user(username='veteranuser', password='pass')
        self.veteran_user.date_joined = timezone.now() - timedelta(days=100)  # 100 days ago
        self.veteran_user.save()
        self.veteran_profile = UserProfile.objects.create(
            user=self.veteran_user,
            trust_level='veteran',
            post_count=200,
            thread_count=50
        )

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()
        self.spam_patcher.stop()

    def create_thread_via_api(self, user, title="Test Thread"):
        """Helper to create thread via API."""
        self.client.force_authenticate(user=user)
        return self.client.post('/api/v1/forum/threads/', {
            'title': title,
            'category': str(self.category.id),
            'first_post_content': 'Test content'
        })

    def create_post_via_api(self, user, thread):
        """Helper to create post via API."""
        self.client.force_authenticate(user=user)
        return self.client.post('/api/v1/forum/posts/', {
            'thread': str(thread.id),
            'content_raw': 'Test post content',
            'content_format': 'plain'
        })

    def toggle_reaction_via_api(self, user, post, reaction_type='like'):
        """Helper to toggle reaction via API."""
        self.client.force_authenticate(user=user)
        return self.client.post('/api/v1/forum/reactions/toggle/', {
            'post': str(post.id),
            'reaction_type': reaction_type
        })


class ThreadRateLimitingTestCase(RateLimitingBaseTestCase):
    """Test rate limiting for ThreadViewSet.create action."""

    def test_new_user_cannot_create_threads(self):
        """
        NEW users are blocked by CanCreateThread permission (not rate limiting).

        CanCreateThread permission requires trust_level != 'new', so NEW users
        get 403 Forbidden before rate limiting is checked.
        """
        response = self.create_thread_via_api(self.new_user, 'Thread 1')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # This is a permission denial, not rate limiting

    def test_basic_user_thread_limit_10_per_day(self):
        """BASIC users can create 10 threads per day, 11th is blocked."""
        # Create 10 threads (should succeed)
        for i in range(10):
            response = self.create_thread_via_api(self.basic_user, f'Thread {i+1}')
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Thread {i+1} should be created successfully"
            )

        # 11th thread should be blocked
        response = self.create_thread_via_api(self.basic_user, 'Thread 11')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['trust_level'], 'basic')
        self.assertEqual(response.data['daily_limit'], 10)

    def test_trusted_user_thread_limit_25_per_day(self):
        """TRUSTED users can create 25 threads per day, 26th is blocked."""
        # Create 25 threads (should succeed)
        for i in range(25):
            response = self.create_thread_via_api(self.trusted_user, f'Thread {i+1}')
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Thread {i+1} should be created successfully"
            )

        # 26th thread should be blocked
        response = self.create_thread_via_api(self.trusted_user, 'Thread 26')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['trust_level'], 'trusted')
        self.assertEqual(response.data['daily_limit'], 25)

    def test_veteran_user_unlimited_threads(self):
        """VETERAN users have unlimited thread creation."""
        # Create 30 threads (well above TRUSTED limit of 25)
        for i in range(30):
            response = self.create_thread_via_api(self.veteran_user, f'Thread {i+1}')
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Thread {i+1} should be created successfully (unlimited)"
            )

    def test_rate_limit_error_response_structure(self):
        """Rate limit error response has correct structure."""
        # Exhaust limit for BASIC user (10 threads)
        for i in range(10):
            self.create_thread_via_api(self.basic_user, f'Thread {i+1}')

        # Check error response structure
        response = self.create_thread_via_api(self.basic_user, 'Thread 11')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Verify response has all required fields
        self.assertIn('error', response.data)
        self.assertIn('detail', response.data)
        self.assertIn('trust_level', response.data)
        self.assertIn('daily_limit', response.data)

        # Verify field types
        self.assertIsInstance(response.data['error'], str)
        self.assertIsInstance(response.data['detail'], str)
        self.assertIsInstance(response.data['trust_level'], str)
        self.assertIsInstance(response.data['daily_limit'], int)


class PostRateLimitingTestCase(RateLimitingBaseTestCase):
    """Test rate limiting for PostViewSet.create action."""

    def setUp(self):
        """Set up test environment with a thread for posting."""
        super().setUp()
        # Create thread for testing posts
        self.test_thread = ThreadFactory.create(
            author=self.new_user,
            category=self.category
        )

    def test_new_user_post_limit_10_per_day(self):
        """NEW users can create 10 posts per day, 11th is blocked."""
        # Create 10 posts (should succeed)
        for i in range(10):
            response = self.create_post_via_api(self.new_user, self.test_thread)
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Post {i+1} should be created successfully"
            )

        # 11th post should be blocked
        response = self.create_post_via_api(self.new_user, self.test_thread)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
        self.assertIn('Daily post limit exceeded', response.data['error'])
        self.assertEqual(response.data['trust_level'], 'new')
        self.assertEqual(response.data['daily_limit'], 10)

    def test_basic_user_post_limit_50_per_day(self):
        """BASIC users can create 50 posts per day, 51st is blocked."""
        # Create 50 posts (should succeed)
        for i in range(50):
            response = self.create_post_via_api(self.basic_user, self.test_thread)
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Post {i+1} should be created successfully"
            )

        # 51st post should be blocked
        response = self.create_post_via_api(self.basic_user, self.test_thread)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['trust_level'], 'basic')
        self.assertEqual(response.data['daily_limit'], 50)

    def test_trusted_user_post_limit_100_per_day(self):
        """TRUSTED users can create 100 posts per day, 101st is blocked."""
        # Create 100 posts (should succeed)
        for i in range(100):
            response = self.create_post_via_api(self.trusted_user, self.test_thread)
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Post {i+1} should be created successfully"
            )

        # 101st post should be blocked
        response = self.create_post_via_api(self.trusted_user, self.test_thread)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['trust_level'], 'trusted')
        self.assertEqual(response.data['daily_limit'], 100)

    def test_veteran_user_unlimited_posts(self):
        """VETERAN users have unlimited post creation."""
        # Create 110 posts (well above TRUSTED limit of 100)
        for i in range(110):
            response = self.create_post_via_api(self.veteran_user, self.test_thread)
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Post {i+1} should be created successfully (unlimited)"
            )


class ReactionRateLimitingTestCase(RateLimitingBaseTestCase):
    """Test rate limiting for ReactionViewSet.toggle action."""

    def setUp(self):
        """Set up test environment with posts for reactions."""
        super().setUp()
        # Create thread and posts for testing reactions
        self.test_thread = ThreadFactory.create(
            author=self.new_user,
            category=self.category
        )
        # Create 600 posts (enough for testing all limits)
        self.test_posts = []
        for i in range(600):
            post = PostFactory.create(
                thread=self.test_thread,
                author=self.new_user
            )
            self.test_posts.append(post)

    def test_new_user_reaction_limit_50_per_day(self):
        """NEW users can create 50 reactions per day, 51st is blocked."""
        # Create 50 reactions (should succeed)
        for i in range(50):
            response = self.toggle_reaction_via_api(self.new_user, self.test_posts[i])
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Reaction {i+1} should be created successfully"
            )

        # 51st reaction should be blocked
        response = self.toggle_reaction_via_api(self.new_user, self.test_posts[50])
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
        self.assertIn('Daily reaction limit exceeded', response.data['error'])
        self.assertEqual(response.data['trust_level'], 'new')
        self.assertEqual(response.data['daily_limit'], 50)

    def test_basic_user_reaction_limit_200_per_day(self):
        """BASIC users can create 200 reactions per day, 201st is blocked."""
        # Create 200 reactions (should succeed)
        for i in range(200):
            response = self.toggle_reaction_via_api(self.basic_user, self.test_posts[i])
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Reaction {i+1} should be created successfully"
            )

        # 201st reaction should be blocked
        response = self.toggle_reaction_via_api(self.basic_user, self.test_posts[200])
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['trust_level'], 'basic')
        self.assertEqual(response.data['daily_limit'], 200)

    def test_trusted_user_reaction_limit_500_per_day(self):
        """TRUSTED users can create 500 reactions per day, 501st is blocked."""
        # Create 500 reactions (should succeed)
        for i in range(500):
            response = self.toggle_reaction_via_api(self.trusted_user, self.test_posts[i])
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Reaction {i+1} should be created successfully"
            )

        # 501st reaction should be blocked
        response = self.toggle_reaction_via_api(self.trusted_user, self.test_posts[500])
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['trust_level'], 'trusted')
        self.assertEqual(response.data['daily_limit'], 500)

    def test_veteran_user_unlimited_reactions(self):
        """VETERAN users have unlimited reaction creation."""
        # Create 510 reactions (well above TRUSTED limit of 500)
        for i in range(510):
            response = self.toggle_reaction_via_api(self.veteran_user, self.test_posts[i])
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Reaction {i+1} should be created successfully (unlimited)"
            )


class RateLimitingIntegrationTestCase(RateLimitingBaseTestCase):
    """Integration tests for rate limiting across multiple viewsets."""

    def test_separate_limits_for_different_actions(self):
        """Posts, threads, and reactions have separate daily limits."""
        # Use BASIC user for threads (NEW users can't create threads)
        # Create thread for posts (counts toward limit)
        thread = ThreadFactory.create(
            author=self.basic_user,
            category=self.category
        )

        # BASIC user: 10 threads, 50 posts, 200 reactions per day
        # Already created 1 thread, so can create 9 more
        # Note: Each API thread creation also creates a first post

        # Create 9 more threads (10 total, exhaust thread limit)
        # This also creates 9 posts (threads have first_post_content)
        for i in range(9):
            response = self.create_thread_via_api(self.basic_user, f'Thread {i+2}')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Create 41 more posts (50 total including the 9 from threads, exhaust post limit)
        for i in range(41):
            response = self.create_post_via_api(self.basic_user, thread)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Create 200 reactions (exhaust reaction limit)
        for i in range(200):
            new_post = PostFactory.create(thread=thread, author=self.veteran_user)
            response = self.toggle_reaction_via_api(self.basic_user, new_post)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # All limits should be exhausted independently
        thread_response = self.create_thread_via_api(self.basic_user, 'Thread 10')
        self.assertEqual(thread_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        post_response = self.create_post_via_api(self.basic_user, thread)
        self.assertEqual(post_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        new_post = PostFactory.create(thread=thread, author=self.veteran_user)
        reaction_response = self.toggle_reaction_via_api(self.basic_user, new_post)
        self.assertEqual(reaction_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
