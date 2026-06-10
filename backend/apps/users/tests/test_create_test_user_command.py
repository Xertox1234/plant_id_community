"""Tests for the create_test_user management command's production guard."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

User = get_user_model()


class CreateTestUserCommandTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_false(self):
        with self.assertRaises(CommandError):
            call_command("create_test_user")
        self.assertEqual(User.objects.filter(username="e2e_test_user").count(), 0)

    @override_settings(DEBUG=True)
    def test_creates_test_user_when_debug_true(self):
        call_command("create_test_user")
        user = User.objects.get(username="e2e_test_user")
        self.assertEqual(user.email, "e2e@test.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
