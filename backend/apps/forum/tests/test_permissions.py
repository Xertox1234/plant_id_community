"""
Test forum permission classes.

Tests IsAuthorOrReadOnly, IsModerator, and CanCreateThread permissions.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

from ..permissions import IsAuthorOrReadOnly, IsModerator, CanCreateThread, CanUploadImages
from ..models import Thread, Post, Category, UserProfile

User = get_user_model()


class IsAuthorOrReadOnlyTests(TestCase):
    """Test IsAuthorOrReadOnly permission class."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.permission = IsAuthorOrReadOnly()

        # Create users
        self.author = User.objects.create_user(username='author', password='pass')
        self.other_user = User.objects.create_user(username='other', password='pass')

        # Create category and thread
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.thread = Thread.objects.create(
            title='Test Thread',
            slug='test-thread',
            author=self.author,
            category=self.category
        )

    def test_safe_methods_allowed_for_anyone(self):
        """GET/HEAD/OPTIONS allowed for anyone."""
        request = self.factory.get('/api/v1/forum/threads/test-thread/')
        request.user = self.other_user

        has_permission = self.permission.has_object_permission(
            request, None, self.thread
        )

        self.assertTrue(has_permission)

    def test_author_can_edit_own_content(self):
        """Author can PUT/PATCH/DELETE their own thread."""
        request = self.factory.patch('/api/v1/forum/threads/test-thread/')
        request.user = self.author

        has_permission = self.permission.has_object_permission(
            request, None, self.thread
        )

        self.assertTrue(has_permission)

    def test_non_author_cannot_edit(self):
        """Non-author cannot edit others' content."""
        request = self.factory.patch('/api/v1/forum/threads/test-thread/')
        request.user = self.other_user

        has_permission = self.permission.has_object_permission(
            request, None, self.thread
        )

        self.assertFalse(has_permission)

    def test_anonymous_can_read(self):
        """Anonymous users can read content."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/api/v1/forum/threads/test-thread/')
        request.user = AnonymousUser()

        has_permission = self.permission.has_object_permission(
            request, None, self.thread
        )

        self.assertTrue(has_permission)

    def test_anonymous_cannot_edit(self):
        """Anonymous users cannot edit content."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.patch('/api/v1/forum/threads/test-thread/')
        request.user = AnonymousUser()

        has_permission = self.permission.has_object_permission(
            request, None, self.thread
        )

        self.assertFalse(has_permission)


class IsModeratorTests(TestCase):
    """Test IsModerator permission class."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.permission = IsModerator()

        # Create users
        self.staff_user = User.objects.create_user(
            username='staff', password='pass', is_staff=True
        )
        self.moderator_group, _ = Group.objects.get_or_create(name='Moderators')
        self.group_moderator = User.objects.create_user(
            username='moderator', password='pass'
        )
        self.group_moderator.groups.add(self.moderator_group)

        self.regular_user = User.objects.create_user(
            username='regular', password='pass'
        )

    def test_staff_user_is_moderator(self):
        """Staff users pass moderator check."""
        request = self.factory.post('/api/v1/forum/categories/')
        request.user = self.staff_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_moderators_group_member_is_moderator(self):
        """Users in 'Moderators' group pass moderator check."""
        request = self.factory.post('/api/v1/forum/categories/')
        request.user = self.group_moderator

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_regular_user_is_not_moderator(self):
        """Regular users fail moderator check."""
        request = self.factory.post('/api/v1/forum/categories/')
        request.user = self.regular_user

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)

    def test_anonymous_is_not_moderator(self):
        """Anonymous users fail moderator check."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.post('/api/v1/forum/categories/')
        request.user = AnonymousUser()

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)


class CanCreateThreadTests(TestCase):
    """Test CanCreateThread permission class."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.permission = CanCreateThread()

        # Create users with different trust levels
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        UserProfile.objects.create(user=self.new_user, trust_level='new')

        self.basic_user = User.objects.create_user(username='basic', password='pass')
        UserProfile.objects.create(user=self.basic_user, trust_level='basic')

        self.trusted_user = User.objects.create_user(username='trusted', password='pass')
        UserProfile.objects.create(user=self.trusted_user, trust_level='trusted')

        self.veteran_user = User.objects.create_user(username='veteran', password='pass')
        UserProfile.objects.create(user=self.veteran_user, trust_level='veteran')

        self.expert_user = User.objects.create_user(username='expert', password='pass')
        UserProfile.objects.create(user=self.expert_user, trust_level='expert')

    def test_new_users_cannot_create_threads(self):
        """Users with trust_level='new' denied."""
        request = self.factory.post('/api/v1/forum/threads/')
        request.user = self.new_user

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)

    def test_basic_users_can_create_threads(self):
        """Users with trust_level='basic' allowed."""
        request = self.factory.post('/api/v1/forum/threads/')
        request.user = self.basic_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_trusted_users_can_create_threads(self):
        """Users with trust_level='trusted' allowed."""
        request = self.factory.post('/api/v1/forum/threads/')
        request.user = self.trusted_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_veteran_users_can_create_threads(self):
        """Users with trust_level='veteran' allowed."""
        request = self.factory.post('/api/v1/forum/threads/')
        request.user = self.veteran_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_expert_users_can_create_threads(self):
        """Users with trust_level='expert' allowed."""
        request = self.factory.post('/api/v1/forum/threads/')
        request.user = self.expert_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_missing_profile_denies_thread_creation(self):
        """Users without forum_profile denied (fail-secure)."""
        user_no_profile = User.objects.create_user(username='noprofile', password='pass')
        # Deliberately don't create UserProfile

        request = self.factory.post('/api/v1/forum/threads/')
        request.user = user_no_profile

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)

    def test_non_post_methods_allowed(self):
        """GET/PUT/PATCH/DELETE allowed regardless of trust level."""
        request = self.factory.get('/api/v1/forum/threads/')
        request.user = self.new_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_anonymous_cannot_create_threads(self):
        """Anonymous users cannot create threads."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.post('/api/v1/forum/threads/')
        request.user = AnonymousUser()

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)


class CanUploadImagesTests(TestCase):
    """
    Test CanUploadImages permission class.

    Phase 6.1: Trust Level Service - ViewSet Integration
    Tests image upload permissions based on trust levels.
    """

    def setUp(self):
        """Set up test data."""
        from django.utils import timezone
        from datetime import timedelta

        self.factory = APIRequestFactory()
        self.permission = CanUploadImages()

        # Create users with different trust levels
        # NEW user: 0 days, 0 posts
        self.new_user = User.objects.create_user(username='newuser', password='pass')
        self.new_user.date_joined = timezone.now()
        self.new_user.save()
        UserProfile.objects.create(user=self.new_user, trust_level='new', post_count=0)

        # BASIC user: 7 days, 5 posts (meets BASIC requirements)
        self.basic_user = User.objects.create_user(username='basic', password='pass')
        self.basic_user.date_joined = timezone.now() - timedelta(days=7)
        self.basic_user.save()
        UserProfile.objects.create(user=self.basic_user, trust_level='basic', post_count=5)

        # TRUSTED user: 30 days, 25 posts (meets TRUSTED requirements)
        self.trusted_user = User.objects.create_user(username='trusted', password='pass')
        self.trusted_user.date_joined = timezone.now() - timedelta(days=30)
        self.trusted_user.save()
        UserProfile.objects.create(user=self.trusted_user, trust_level='trusted', post_count=25)

        # VETERAN user: 90 days, 100 posts (meets VETERAN requirements)
        self.veteran_user = User.objects.create_user(username='veteran', password='pass')
        self.veteran_user.date_joined = timezone.now() - timedelta(days=90)
        self.veteran_user.save()
        UserProfile.objects.create(user=self.veteran_user, trust_level='veteran', post_count=100)

        # EXPERT user: Manually set (ignores activity requirements)
        self.expert_user = User.objects.create_user(username='expert', password='pass')
        UserProfile.objects.create(user=self.expert_user, trust_level='expert', post_count=0)

        # Staff user (bypasses trust level checks)
        self.staff_user = User.objects.create_user(
            username='staff', password='pass', is_staff=True
        )

        # Superuser (bypasses trust level checks)
        self.superuser = User.objects.create_user(
            username='superuser', password='pass', is_superuser=True
        )

    def test_new_users_cannot_upload_images(self):
        """
        NEW users denied image upload (can_upload_images=False).

        Trust level requirements:
        - NEW: CANNOT upload images
        - BASIC+: CAN upload images

        Expected: 403 Forbidden with helpful error message
        """
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.new_user

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)
        # Verify error message is helpful
        self.assertIn('BASIC trust level or higher', self.permission.message)
        self.assertIn('NEW', self.permission.message)

    def test_basic_users_can_upload_images(self):
        """BASIC users can upload images (can_upload_images=True)."""
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.basic_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_trusted_users_can_upload_images(self):
        """TRUSTED users can upload images (can_upload_images=True)."""
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.trusted_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_veteran_users_can_upload_images(self):
        """VETERAN users can upload images (can_upload_images=True)."""
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.veteran_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_expert_users_can_upload_images(self):
        """EXPERT users can upload images (can_upload_images=True)."""
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.expert_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_staff_users_bypass_trust_level(self):
        """
        Staff users can upload images regardless of trust level.

        Security: Staff should have all permissions for moderation.
        """
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.staff_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_superusers_bypass_trust_level(self):
        """
        Superusers can upload images regardless of trust level.

        Security: Superusers should have all permissions.
        """
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.superuser

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)

    def test_anonymous_users_denied(self):
        """
        Anonymous users cannot upload images.

        Expected: 403 Forbidden with "Authentication required" message
        """
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = AnonymousUser()

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)
        self.assertIn('Authentication required', self.permission.message)

    def test_error_message_includes_progression_info(self):
        """
        Error message includes progression requirements for BASIC level.

        Example: "Requirements for BASIC: 7 days active, 5 posts. Your progress: 2 days, 1 posts."
        """
        request = self.factory.post('/api/v1/forum/posts/1/upload_image/')
        request.user = self.new_user

        has_permission = self.permission.has_permission(request, None)

        self.assertFalse(has_permission)
        # Check that error message includes specific requirements
        self.assertIn('7 days active', self.permission.message)
        self.assertIn('5 posts', self.permission.message)
        self.assertIn('Your progress:', self.permission.message)

    def test_non_post_methods_allowed(self):
        """
        Non-POST methods allowed regardless of trust level.

        Note: This is defensive - upload_image should only accept POST,
        but permission class shouldn't break on other methods.
        """
        request = self.factory.get('/api/v1/forum/posts/1/upload_image/')
        request.user = self.new_user

        has_permission = self.permission.has_permission(request, None)

        self.assertTrue(has_permission)
