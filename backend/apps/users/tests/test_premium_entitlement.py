"""Tests for the premium entitlement primitive (todo 255, slice 1).

Covers ``User.has_premium_access()`` and the ``IsPremiumUser`` DRF permission.
"""

from apps.users.permissions import IsPremiumUser
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

User = get_user_model()


class HasPremiumAccessTests(TestCase):
    """Unit tests for the User.has_premium_access() entitlement gate."""

    def test_plain_user_has_no_premium_access(self):
        user = User.objects.create_user(username="free")
        self.assertFalse(user.is_premium)
        self.assertFalse(user.has_premium_access())

    def test_premium_flag_grants_access(self):
        user = User.objects.create_user(username="premium", is_premium=True)
        self.assertTrue(user.has_premium_access())

    def test_staff_granted_access_implicitly(self):
        """Staff get premium-equivalent access without the is_premium flag."""
        user = User.objects.create_user(username="staff", is_staff=True)
        self.assertFalse(user.is_premium)
        self.assertTrue(user.has_premium_access())

    def test_superuser_granted_access_implicitly(self):
        # is_superuser alone (not staff, not premium) must grant access.
        user = User.objects.create_user(username="root", is_superuser=True)
        self.assertFalse(user.is_premium)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.has_premium_access())


class IsPremiumUserPermissionTests(TestCase):
    """Unit tests for the IsPremiumUser DRF permission class."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsPremiumUser()

    def _allowed(self, user) -> bool:
        request = self.factory.get("/")
        request.user = user
        return self.permission.has_permission(request, None)

    def test_premium_user_allowed(self):
        user = User.objects.create_user(username="premium", is_premium=True)
        self.assertTrue(self._allowed(user))

    def test_staff_user_allowed(self):
        user = User.objects.create_user(username="staff", is_staff=True)
        self.assertTrue(self._allowed(user))

    def test_free_user_denied(self):
        user = User.objects.create_user(username="free")
        self.assertFalse(self._allowed(user))

    def test_anonymous_user_denied(self):
        self.assertFalse(self._allowed(AnonymousUser()))
