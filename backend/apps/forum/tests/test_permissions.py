"""
Test forum permission classes.

Tests IsAuthorOrReadOnly, IsModerator, and CanCreateThread permissions.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

from ..permissions import IsAuthorOrReadOnly, IsModerator, CanCreateThread
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
