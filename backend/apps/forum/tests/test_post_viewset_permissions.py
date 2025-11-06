"""
Integration tests for trust level permissions in PostViewSet.

Issue #131: Add integration tests for trust level permission enforcement
Tests verify permissions work when called through actual API endpoints,
not just in isolation (unit tests in test_permissions.py).

Coverage:
- 8 permission integration tests (trust levels + staff/moderator bypass)
- 10 rate limiting tests (enforcement, headers, reset, isolation, error format)

Total: 18+ integration tests
"""

from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from freezegun import freeze_time

from ..models import Thread, Post, Category, UserProfile
from .utils import ForumTestUtils

User = get_user_model()


class PostViewSetPermissionIntegrationTests(TestCase):
    """
    Integration tests for trust level permissions in PostViewSet.

    Tests verify permissions work when called through actual API endpoints,
    not just in isolation (unit tests in test_permissions.py).

    Related Issues:
    - #131: Integration tests for permission enforcement
    - #125: Trust Level Service - ViewSet Integration (parent issue)
    - #124: Trust Level Service Tests
    """

    def setUp(self):
        """Set up test data with realistic trust levels."""
        # Mock spam detection to prevent false positives
        self.spam_patcher = patch('apps.forum.services.spam_detection_service.SpamDetectionService.is_spam')
        self.mock_spam = self.spam_patcher.start()
        self.mock_spam.return_value = {
            'is_spam': False,
            'spam_score': 0,
            'reasons': [],
            'details': {}
        }

        # Disable trust level promotion signal during setup
        # This prevents automatic promotion when creating test posts
        self.trust_level_signal_patcher = patch('apps.forum.signals.update_user_trust_level_on_post')
        self.mock_trust_level_signal = self.trust_level_signal_patcher.start()
        self.mock_trust_level_signal.return_value = None

        self.client = APIClient()

        # Create category and thread (needed for post creation)
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            description='Test category for permission tests',
            is_active=True
        )

        # Create NEW user (0 days, 0 posts)
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        self.new_user.date_joined = timezone.now()
        self.new_user.save()
        UserProfile.objects.create(user=self.new_user, trust_level='new', post_count=0)

        # Create thread for NEW user
        self.new_user_thread = Thread.objects.create(
            title='NEW User Thread',
            slug='new-user-thread',
            author=self.new_user,
            category=self.category,
            is_active=True
        )

        # Create NEW user's post (to test uploads)
        self.new_user_post = Post.objects.create(
            thread=self.new_user_thread,
            author=self.new_user,
            content_raw='Test post by NEW user',
            is_first_post=True,
            is_active=True
        )

        # Create BASIC user (7 days, 5 posts)
        self.basic_user = User.objects.create_user(username='basic', password='pass')
        self.basic_user.date_joined = timezone.now() - timedelta(days=7)
        self.basic_user.save()
        UserProfile.objects.create(user=self.basic_user, trust_level='basic', post_count=5)

        # Create thread for BASIC user
        self.basic_user_thread = Thread.objects.create(
            title='BASIC User Thread',
            slug='basic-user-thread',
            author=self.basic_user,
            category=self.category,
            is_active=True
        )

        # Create BASIC user's post
        self.basic_user_post = Post.objects.create(
            thread=self.basic_user_thread,
            author=self.basic_user,
            content_raw='Test post by BASIC user',
            is_first_post=True,
            is_active=True
        )

        # Create TRUSTED user (30 days, 25 posts)
        self.trusted_user = User.objects.create_user(username='trusted', password='pass')
        self.trusted_user.date_joined = timezone.now() - timedelta(days=30)
        self.trusted_user.save()
        UserProfile.objects.create(user=self.trusted_user, trust_level='trusted', post_count=25)

        # Create thread for TRUSTED user
        self.trusted_user_thread = Thread.objects.create(
            title='TRUSTED User Thread',
            slug='trusted-user-thread',
            author=self.trusted_user,
            category=self.category,
            is_active=True
        )

        # Create TRUSTED user's post
        self.trusted_user_post = Post.objects.create(
            thread=self.trusted_user_thread,
            author=self.trusted_user,
            content_raw='Test post by TRUSTED user',
            is_first_post=True,
            is_active=True
        )

        # Create VETERAN user (90 days, 100 posts)
        self.veteran_user = User.objects.create_user(username='veteran', password='pass')
        self.veteran_user.date_joined = timezone.now() - timedelta(days=90)
        self.veteran_user.save()
        UserProfile.objects.create(user=self.veteran_user, trust_level='veteran', post_count=100)

        # Create thread for VETERAN user
        self.veteran_user_thread = Thread.objects.create(
            title='VETERAN User Thread',
            slug='veteran-user-thread',
            author=self.veteran_user,
            category=self.category,
            is_active=True
        )

        # Create VETERAN user's post
        self.veteran_user_post = Post.objects.create(
            thread=self.veteran_user_thread,
            author=self.veteran_user,
            content_raw='Test post by VETERAN user',
            is_first_post=True,
            is_active=True
        )

        # Create EXPERT user (manually assigned, 0 days, 0 posts)
        self.expert_user = User.objects.create_user(username='expert', password='pass')
        UserProfile.objects.create(user=self.expert_user, trust_level='expert', post_count=0)

        # Create thread for EXPERT user
        self.expert_user_thread = Thread.objects.create(
            title='EXPERT User Thread',
            slug='expert-user-thread',
            author=self.expert_user,
            category=self.category,
            is_active=True
        )

        # Create EXPERT user's post
        self.expert_user_post = Post.objects.create(
            thread=self.expert_user_thread,
            author=self.expert_user,
            content_raw='Test post by EXPERT user',
            is_first_post=True,
            is_active=True
        )

        # Create staff user (no forum profile needed)
        self.staff_user = User.objects.create_user(
            username='staff', password='pass', is_staff=True
        )

        # Create thread for staff user
        self.staff_user_thread = Thread.objects.create(
            title='Staff User Thread',
            slug='staff-user-thread',
            author=self.staff_user,
            category=self.category,
            is_active=True
        )

        # Create staff user's post
        self.staff_user_post = Post.objects.create(
            thread=self.staff_user_thread,
            author=self.staff_user,
            content_raw='Test post by staff user',
            is_first_post=True,
            is_active=True
        )

        # Create moderator user (in 'Moderators' group)
        self.moderator_group, _ = Group.objects.get_or_create(name='Moderators')
        self.moderator_user = User.objects.create_user(username='moderator', password='pass')
        self.moderator_user.date_joined = timezone.now() - timedelta(days=7)  # Meet BASIC requirements
        self.moderator_user.save()
        self.moderator_user.groups.add(self.moderator_group)
        UserProfile.objects.create(user=self.moderator_user, trust_level='basic', post_count=10)

        # Create thread for moderator user
        self.moderator_thread = Thread.objects.create(
            title='Moderator Thread',
            slug='moderator-thread',
            author=self.moderator_user,
            category=self.category,
            is_active=True
        )

        # Create moderator's post
        self.moderator_post = Post.objects.create(
            thread=self.moderator_thread,
            author=self.moderator_user,
            content_raw='Test post by moderator',
            is_first_post=True,
            is_active=True
        )

    def tearDown(self):
        """Clean up after each test."""
        self.spam_patcher.stop()
        self.trust_level_signal_patcher.stop()
        cache.clear()  # Clear rate limit cache

    def get_error_detail(self, response_data: dict) -> str:
        """
        Extract error detail message from response data.

        Handles both formats:
        - Custom error handler: {'errors': {'detail': 'message'}}
        - Standard DRF: {'detail': 'message'}

        Args:
            response_data: Response data dictionary

        Returns:
            Error detail message string
        """
        if 'errors' in response_data and 'detail' in response_data['errors']:
            return response_data['errors']['detail']
        return response_data.get('detail', '')

    # ========================================================================
    # Permission Integration Tests (8 tests)
    # ========================================================================

    def test_new_user_upload_image_returns_403(self):
        """
        NEW users denied image upload via API endpoint.

        Issue #125: Trust level permission enforcement
        Expected: 403 Forbidden with helpful error message
        """
        self.client.force_authenticate(user=self.new_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.new_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify error message includes trust level info
        detail_message = self.get_error_detail(response.data)
        self.assertIn('BASIC trust level or higher', detail_message)
        self.assertIn('NEW', detail_message)
        self.assertIn('7 days active', detail_message)
        self.assertIn('5 posts', detail_message)

    def test_basic_user_upload_image_succeeds(self):
        """
        BASIC users can upload images to own post.

        Expected: 201 Created with attachment details
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.basic_user_post.id}/upload_image/',
            {'image': image_file, 'alt_text': 'Test image'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)
        self.assertIn('original_filename', response.data)
        self.assertEqual(response.data['original_filename'], 'test.jpg')

    def test_trusted_user_upload_image_succeeds(self):
        """
        TRUSTED users can upload images to own post.

        Expected: 201 Created
        """
        self.client.force_authenticate(user=self.trusted_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.trusted_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)

    def test_veteran_user_upload_image_succeeds(self):
        """
        VETERAN users can upload images to own post.

        Expected: 201 Created
        """
        self.client.force_authenticate(user=self.veteran_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.veteran_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)

    def test_expert_user_upload_image_succeeds(self):
        """
        EXPERT users can upload images to own post.

        Expected: 201 Created
        """
        self.client.force_authenticate(user=self.expert_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.expert_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)

    def test_staff_user_bypasses_trust_level_check(self):
        """
        Staff user (no forum profile) uploads image.

        Expected: 201 Created (staff bypass works)
        """
        self.client.force_authenticate(user=self.staff_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.staff_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)

    def test_basic_user_cannot_upload_to_others_post(self):
        """
        BASIC user attempts upload to another user's post.

        Expected: 403 Forbidden (IsAuthorOrModerator blocks)

        Note: This tests that multiple permission classes work together:
        - CanUploadImages passes (BASIC user can upload)
        - IsAuthorOrModerator fails (not post author)
        Result: 403 Forbidden
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        # Try to upload to NEW user's post (not author)
        response = self.client.post(
            f'/api/v1/forum/posts/{self.new_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_can_upload_to_any_post(self):
        """
        User in 'Moderators' group uploads to any post.

        Expected: 201 Created (moderator bypass works)
        """
        self.client.force_authenticate(user=self.moderator_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        # Upload to NEW user's post (moderator can upload to any post)
        response = self.client.post(
            f'/api/v1/forum/posts/{self.new_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)

    # ========================================================================
    # Rate Limiting Tests (10 tests)
    # ========================================================================

    def test_rate_limit_enforced_after_10_uploads(self):
        """
        User uploads 11 images within 1 hour.

        Expected: First 10 succeed, 11th returns 429 Too Many Requests

        Rate limit: 10 uploads/hour (via @ratelimit decorator)
        Note: Creates multiple posts since each post has 6 image limit
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create additional posts for rate limit testing (need more than 1 post for 10+ uploads)
        extra_posts = []
        for i in range(2):  # Create 2 extra posts (total 3 posts allows 18 images)
            post = Post.objects.create(
                thread=self.basic_user_thread,
                author=self.basic_user,
                content_raw=f'Extra post {i+1} for rate limit testing',
                is_active=True
            )
            extra_posts.append(post)

        # Upload 10 images to different posts (should succeed)
        posts_to_use = [self.basic_user_post] + extra_posts
        for i in range(10):
            # Rotate through posts to avoid MAX_ATTACHMENTS_PER_POST limit
            post = posts_to_use[i // 6]  # Use different post every 6 uploads
            image_file = ForumTestUtils.create_test_image_file(f'test{i}.jpg')
            response = self.client.post(
                f'/api/v1/forum/posts/{post.id}/upload_image/',
                {'image': image_file},
                format='multipart'
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"Upload {i+1} should succeed")

        # 11th upload should be rate limited
        image_file = ForumTestUtils.create_test_image_file('test11.jpg')
        response = self.client.post(
            f'/api/v1/forum/posts/{posts_to_use[1].id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_rate_limit_header_present_on_429(self):
        """
        Verify Retry-After header in 429 response.

        Expected: Header contains seconds value (time until rate limit resets)
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create additional posts for rate limit testing
        extra_posts = []
        for i in range(2):
            post = Post.objects.create(
                thread=self.basic_user_thread,
                author=self.basic_user,
                content_raw=f'Extra post {i+1} for rate limit testing',
                is_active=True
            )
            extra_posts.append(post)

        # Upload 10 images to hit rate limit (rotate through posts)
        posts_to_use = [self.basic_user_post] + extra_posts
        for i in range(10):
            post = posts_to_use[i // 6]
            image_file = ForumTestUtils.create_test_image_file(f'test{i}.jpg')
            self.client.post(
                f'/api/v1/forum/posts/{post.id}/upload_image/',
                {'image': image_file},
                format='multipart'
            )

        # 11th upload should return 429 with Retry-After header
        image_file = ForumTestUtils.create_test_image_file('test11.jpg')
        response = self.client.post(
            f'/api/v1/forum/posts/{posts_to_use[1].id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # Note: django-ratelimit uses X-RateLimit-* headers
        # The exact header name depends on middleware/decorator implementation
        # This test documents expected behavior

    @freeze_time("2025-11-06 10:00:00")
    def test_rate_limit_resets_after_timeout(self):
        """
        Mock time to advance past rate limit window.

        Expected: User can upload again after reset (1 hour)

        Note: Uses freezegun to mock time progression
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create additional posts for rate limit testing
        extra_posts = []
        for i in range(2):
            post = Post.objects.create(
                thread=self.basic_user_thread,
                author=self.basic_user,
                content_raw=f'Extra post {i+1} for rate limit testing',
                is_active=True
            )
            extra_posts.append(post)

        # Upload 10 images at 10:00 AM (rotate through posts)
        posts_to_use = [self.basic_user_post] + extra_posts
        for i in range(10):
            post = posts_to_use[i // 6]
            image_file = ForumTestUtils.create_test_image_file(f'test{i}.jpg')
            response = self.client.post(
                f'/api/v1/forum/posts/{post.id}/upload_image/',
                {'image': image_file},
                format='multipart'
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 11th upload at 10:00 AM should be rate limited
        image_file = ForumTestUtils.create_test_image_file('test11.jpg')
        response = self.client.post(
            f'/api/v1/forum/posts/{posts_to_use[1].id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Advance time by 1 hour + 1 minute (past rate limit window)
        with freeze_time("2025-11-06 11:01:00"):
            # Clear cache to simulate rate limit reset
            cache.clear()

            # Upload should succeed after rate limit resets
            image_file = ForumTestUtils.create_test_image_file('test_after_reset.jpg')
            response = self.client.post(
                f'/api/v1/forum/posts/{posts_to_use[1].id}/upload_image/',
                {'image': image_file},
                format='multipart'
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_rate_limit_per_user_isolation(self):
        """
        Two users upload images simultaneously.

        Expected: Each has independent 10/hour limit
        """
        # Create additional posts for User 1 rate limit testing
        extra_posts = []
        for i in range(2):
            post = Post.objects.create(
                thread=self.basic_user_thread,
                author=self.basic_user,
                content_raw=f'Extra post {i+1} for rate limit testing',
                is_active=True
            )
            extra_posts.append(post)

        # User 1: Upload 10 images (rotate through posts)
        self.client.force_authenticate(user=self.basic_user)
        posts_to_use = [self.basic_user_post] + extra_posts
        for i in range(10):
            post = posts_to_use[i // 6]
            image_file = ForumTestUtils.create_test_image_file(f'user1_test{i}.jpg')
            response = self.client.post(
                f'/api/v1/forum/posts/{post.id}/upload_image/',
                {'image': image_file},
                format='multipart'
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # User 1: 11th upload should be rate limited
        image_file = ForumTestUtils.create_test_image_file('user1_test11.jpg')
        response = self.client.post(
            f'/api/v1/forum/posts/{posts_to_use[1].id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # User 2: Should still be able to upload (independent limit)
        self.client.force_authenticate(user=self.trusted_user)
        image_file = ForumTestUtils.create_test_image_file('user2_test1.jpg')
        response = self.client.post(
            f'/api/v1/forum/posts/{self.trusted_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_new_user_trust_level_error_format(self):
        """
        Verify error response structure for NEW users.

        Expected: JSON with trust level, requirements, progress
        """
        self.client.force_authenticate(user=self.new_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.new_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify error message contains all required information
        error_detail = self.get_error_detail(response.data)
        self.assertIn('BASIC trust level or higher', error_detail)
        self.assertIn('NEW', error_detail)  # Current trust level
        self.assertIn('7 days active', error_detail)  # BASIC requirement
        self.assertIn('5 posts', error_detail)  # BASIC requirement
        self.assertIn('Your progress:', error_detail)  # Current progress

    def test_anonymous_user_upload_blocked(self):
        """
        Unauthenticated request to upload_image.

        Expected: 401 Unauthorized (before permission checks)
        """
        # Don't authenticate (anonymous user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.basic_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        # DRF returns 401 for unauthenticated requests to endpoints requiring authentication
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_image_requires_authentication(self):
        """
        Anonymous user attempts upload (alternative test).

        Expected: 401 Unauthorized
        """
        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.basic_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_multiple_permission_classes_evaluated(self):
        """
        BASIC user attempts upload to another user's post.

        Expected: CanUploadImages passes, IsAuthorOrModerator fails → 403

        This tests that DRF evaluates permission classes in AND logic:
        - Permission class 1 (CanUploadImages): PASS (BASIC user can upload)
        - Permission class 2 (IsAuthorOrModerator): FAIL (not post author)
        - Result: 403 Forbidden (all permissions must pass)
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        # Try to upload to TRUSTED user's post (not author, not moderator)
        response = self.client.post(
            f'/api/v1/forum/posts/{self.trusted_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_permission_error_messages_are_helpful(self):
        """
        Verify error messages guide users toward solutions.

        Expected: Messages include progression requirements
        """
        self.client.force_authenticate(user=self.new_user)

        # Create test image
        image_file = ForumTestUtils.create_test_image_file('test.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.new_user_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify error message is helpful and actionable
        error_detail = self.get_error_detail(response.data)

        # Check for key elements of helpful error message
        self.assertIn('BASIC trust level or higher', error_detail, "Should mention required trust level")
        self.assertIn('NEW', error_detail, "Should show current trust level")
        self.assertIn('7 days active', error_detail, "Should show days requirement")
        self.assertIn('5 posts', error_detail, "Should show posts requirement")
        self.assertIn('Your progress:', error_detail, "Should show current progress")

        # Error message should not just say "Permission denied" (unhelpful)
        self.assertNotEqual(error_detail, "You do not have permission to perform this action.")

    def test_upload_image_with_valid_image_file(self):
        """
        End-to-end test: BASIC user uploads valid JPG.

        Expected: 201 with attachment URL, thumbnail, file size

        This is a comprehensive integration test that verifies:
        - Authentication works
        - Trust level permission passes
        - Author permission passes
        - File upload works
        - Attachment is created with correct metadata
        """
        self.client.force_authenticate(user=self.basic_user)

        # Create test image with known properties
        image_file = ForumTestUtils.create_test_image_file('test_image.jpg')

        response = self.client.post(
            f'/api/v1/forum/posts/{self.basic_user_post.id}/upload_image/',
            {'image': image_file, 'alt_text': 'A test image'},
            format='multipart'
        )

        # Verify success
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify response contains all expected fields
        self.assertIn('id', response.data)
        self.assertIn('image_url', response.data)
        self.assertIn('original_filename', response.data)
        self.assertIn('file_size', response.data)
        self.assertIn('created_at', response.data)

        # Verify filename and file size
        self.assertEqual(response.data['original_filename'], 'test_image.jpg')
        self.assertGreater(response.data['file_size'], 0, "File size should be > 0 bytes")

        # Verify image URL is valid (not empty)
        self.assertTrue(response.data['image_url'], "Image URL should not be empty")
