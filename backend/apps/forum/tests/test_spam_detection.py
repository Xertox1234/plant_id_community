"""
Test spam detection integration for forum viewsets.

Tests Phase 4.4: SpamDetectionService integration into Thread and Post viewsets.
Verifies that spam content is detected and blocked based on multiple heuristics.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.forum.models import UserProfile, Category, Thread, Post
from apps.forum.services.spam_detection_service import SpamDetectionService
from apps.forum.constants import (
    SPAM_SCORE_DUPLICATE,
    SPAM_SCORE_RAPID_POST,
    SPAM_SCORE_LINK_SPAM,
    SPAM_SCORE_KEYWORD_SPAM,
    SPAM_SCORE_PATTERN_SPAM,
    SPAM_SCORE_THRESHOLD,
)
from .factories import UserFactory, CategoryFactory, ThreadFactory, PostFactory

User = get_user_model()


class SpamDetectionBaseTestCase(APITestCase):
    """Base test case for spam detection tests with user setup."""

    def setUp(self):
        """Set up test environment with users at different trust levels."""
        # Clear cache to ensure clean state
        cache.clear()

        # Create API client
        self.client = APIClient()

        # Create category for testing
        self.category = CategoryFactory.create(name='Test Category')

        # Create NEW user (trust_level='new')
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        self.new_user.date_joined = timezone.now()
        self.new_user.save()
        self.new_profile = UserProfile.objects.create(
            user=self.new_user,
            trust_level='new',
            post_count=1,
            thread_count=0
        )

        # Create BASIC user (trust_level='basic')
        self.basic_user = User.objects.create_user(username='basicuser', password='pass')
        self.basic_user.date_joined = timezone.now() - timedelta(days=10)
        self.basic_user.save()
        self.basic_profile = UserProfile.objects.create(
            user=self.basic_user,
            trust_level='basic',
            post_count=10,
            thread_count=2
        )

        # Create TRUSTED user (trust_level='trusted')
        self.trusted_user = User.objects.create_user(username='trusteduser', password='pass')
        self.trusted_user.date_joined = timezone.now() - timedelta(days=35)
        self.trusted_user.save()
        self.trusted_profile = UserProfile.objects.create(
            user=self.trusted_user,
            trust_level='trusted',
            post_count=50,
            thread_count=10
        )

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def create_post_via_api(self, user, thread, content):
        """Helper to create post via API."""
        self.client.force_authenticate(user=user)
        return self.client.post('/api/v1/forum/posts/', {
            'thread': str(thread.id),
            'content_raw': content,
            'content_format': 'plain'
        })

    def create_thread_via_api(self, user, title, first_post_content):
        """Helper to create thread via API."""
        self.client.force_authenticate(user=user)
        return self.client.post('/api/v1/forum/threads/', {
            'title': title,
            'category': str(self.category.id),
            'first_post_content': first_post_content
        })


class DuplicateContentDetectionTestCase(SpamDetectionBaseTestCase):
    """Test duplicate content detection."""

    def test_exact_duplicate_post_blocked(self):
        """Posting exact duplicate content is blocked."""
        # Create thread
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Create first post via model (so it's saved in DB before spam check)
        content = "This is my original post content."
        first_post = PostFactory.create(
            thread=thread,
            author=self.basic_user,
            content_raw=content
        )

        # Try to create exact duplicate via API (should be blocked)
        response2 = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('spam', response2.data['error'].lower())
        self.assertIn('duplicate_content', response2.data['reasons'])

    def test_fuzzy_duplicate_post_blocked(self):
        """Posting very similar content (85%+ similarity) is blocked."""
        # Create thread
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Create first post via model
        content1 = "This is my original post about plant identification tips."
        first_post = PostFactory.create(
            thread=thread,
            author=self.basic_user,
            content_raw=content1
        )

        # Try to create fuzzy duplicate via API (same content with minor changes)
        content2 = "This is my original post about plant identification tips!"
        response2 = self.create_post_via_api(self.basic_user, thread, content2)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duplicate_content', response2.data['reasons'])

    def test_different_content_allowed(self):
        """Posting different content is allowed."""
        # Create thread
        thread = ThreadFactory.create(author=self.trusted_user, category=self.category)

        # Create first post (use TRUSTED user to avoid rapid posting detection)
        content1 = "This is my first post about succulents."
        response1 = self.create_post_via_api(self.trusted_user, thread, content1)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Create different post (should succeed - different content, no spam)
        content2 = "Now I want to discuss indoor ferns."
        response2 = self.create_post_via_api(self.trusted_user, thread, content2)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)


class RapidPostingDetectionTestCase(SpamDetectionBaseTestCase):
    """Test rapid posting detection."""

    def test_new_user_rapid_posting_blocked(self):
        """NEW users cannot post within 10 seconds of previous post."""
        # Create thread
        thread = ThreadFactory.create(author=self.new_user, category=self.category)

        # Create first post via model (not API) to set timestamp
        first_post = PostFactory.create(
            thread=thread,
            author=self.new_user,
            content_raw="First post"
        )

        # Immediately try second post via API (should be blocked)
        response2 = self.create_post_via_api(self.new_user, thread, "Second post immediately after")
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rapid_posting', response2.data['reasons'])

    def test_basic_user_rapid_posting_blocked(self):
        """BASIC users cannot post within 10 seconds of previous post."""
        # Create thread
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Create first post via model to set timestamp
        first_post = PostFactory.create(
            thread=thread,
            author=self.basic_user,
            content_raw="First post"
        )

        # Immediately try second post via API (should be blocked)
        response2 = self.create_post_via_api(self.basic_user, thread, "Second post rapidly")
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rapid_posting', response2.data['reasons'])

    def test_trusted_user_rapid_posting_allowed(self):
        """TRUSTED users are exempt from rapid posting detection."""
        # Create thread
        thread = ThreadFactory.create(author=self.trusted_user, category=self.category)

        # Create first post
        response1 = self.create_post_via_api(self.trusted_user, thread, "First post")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Immediately try second post (should succeed for TRUSTED user)
        response2 = self.create_post_via_api(self.trusted_user, thread, "Second post immediately after")
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)


class LinkSpamDetectionTestCase(SpamDetectionBaseTestCase):
    """Test link spam detection."""

    def test_new_user_excessive_urls_blocked(self):
        """NEW users cannot post more than 2 URLs."""
        thread = ThreadFactory.create(author=self.new_user, category=self.category)

        # Post with 3 URLs (exceeds NEW user limit of 2)
        content = "Check out these sites: http://spam1.com http://spam2.com http://spam3.com"
        response = self.create_post_via_api(self.new_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('link_spam', response.data['reasons'])

    def test_basic_user_excessive_urls_blocked(self):
        """BASIC users cannot post more than 5 URLs."""
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Post with 6 URLs (exceeds BASIC user limit of 5)
        urls = " ".join([f"http://link{i}.com" for i in range(6)])
        content = f"Here are many links: {urls}"
        response = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('link_spam', response.data['reasons'])

    def test_trusted_user_many_urls_allowed(self):
        """TRUSTED users can post up to 10 URLs."""
        thread = ThreadFactory.create(author=self.trusted_user, category=self.category)

        # Post with 8 URLs (within TRUSTED user limit of 10)
        urls = " ".join([f"http://resource{i}.com" for i in range(8)])
        content = f"Useful resources: {urls}"
        response = self.create_post_via_api(self.trusted_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class KeywordSpamDetectionTestCase(SpamDetectionBaseTestCase):
    """Test keyword spam detection."""

    def test_multiple_spam_keywords_blocked(self):
        """Content with 2+ spam keywords is blocked."""
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Post with multiple spam keywords (lowercase for matching)
        content = "buy now! limited time offer! click here for free money!"
        response = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('keyword_spam', response.data['reasons'])

    def test_single_spam_keyword_allowed(self):
        """Content with only 1 spam keyword is allowed (not spam threshold)."""
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Post with single spam keyword (not enough to trigger)
        content = "I want to buy now some plant seeds for my garden."
        response = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PatternSpamDetectionTestCase(SpamDetectionBaseTestCase):
    """Test spam pattern detection."""

    def test_patterns_plus_keywords_blocked(self):
        """Content with spam patterns + keywords reaches threshold."""
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Post with ALL CAPS + repetition + phishing keywords (45 pattern + 60 keyword = 105 >= 50)
        # Using phishing keywords (30 points each): "verify your account", "suspended account"
        content = "VERIFY YOUR ACCOUNT!!!! YOUR ACCOUNT IS SUSPENDED!!!!! URGENT!!!!!"
        response = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('spam_patterns', response.data['reasons'])
        self.assertIn('keyword_spam', response.data['reasons'])

    def test_single_pattern_allowed(self):
        """Content with single pattern is allowed (below threshold)."""
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Post with only caps (single pattern, not enough for spam)
        content = "HELLO EVERYONE THIS IS A NORMAL POST"
        response = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class SpamScoreIntegrationTestCase(SpamDetectionBaseTestCase):
    """Test spam scoring system integration."""

    def test_spam_score_calculation(self):
        """Spam score is calculated correctly from multiple checks."""
        # Direct service call for precise score testing
        # Using 3 financial keywords (20 pts each = 60 pts): "free money", "bitcoin", "claim your prize"
        content = "FREE MONEY! WIN BITCOIN! CLAIM YOUR PRIZE! http://spam1.com http://spam2.com http://spam3.com !!!!!!"

        result = SpamDetectionService.is_spam(self.new_user, content, content_type='post')

        # Should detect: link_spam (50) + keyword_spam (60 from 3 financial keywords) + spam_patterns (45) = 155 >= 50
        self.assertTrue(result['is_spam'])
        self.assertGreaterEqual(result['spam_score'], SPAM_SCORE_THRESHOLD)
        self.assertIn('link_spam', result['reasons'])
        self.assertIn('keyword_spam', result['reasons'])

    def test_below_threshold_allowed(self):
        """Content below spam threshold is allowed."""
        thread = ThreadFactory.create(author=self.basic_user, category=self.category)

        # Content with minor suspicious patterns but below threshold
        content = "Check out this plant guide: http://example.com - great resource!"
        response = self.create_post_via_api(self.basic_user, thread, content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ThreadSpamDetectionTestCase(SpamDetectionBaseTestCase):
    """Test spam detection for thread creation."""

    def test_thread_spam_blocked(self):
        """Spam threads are blocked."""
        # Thread with phishing keywords (30 pts each) + links (use BASIC user - NEW can't create threads)
        # Using phishing keywords: "verify your account", "urgent", "account locked"
        title = "Verify Your Account - Urgent!"
        content = "Your account locked! Verify now: http://spam.com http://spam2.com http://spam3.com"

        response = self.create_thread_via_api(self.basic_user, title, content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('spam', response.data['error'].lower())

    def test_thread_duplicate_blocked(self):
        """Duplicate threads are blocked."""
        title = "My Succulent Care Question"
        content = "How often should I water my succulents in winter?"

        # Create first thread via factory (use TRUSTED user to avoid rapid posting)
        first_thread = ThreadFactory.create(
            author=self.trusted_user,
            category=self.category,
            title=title
        )
        # Create first post for thread
        first_post = PostFactory.create(
            thread=first_thread,
            author=self.trusted_user,
            content_raw=content
        )

        # Try to create duplicate thread via API (should be blocked for duplicate)
        response2 = self.create_thread_via_api(self.trusted_user, title, content)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duplicate_content', response2.data['reasons'])
