"""
Tests for user app migrations.

Ensures data migrations handle edge cases properly and maintain data integrity.
"""

from django.test import TestCase


class TestMigrationDataIntegrity(TestCase):
    """Test that migrations maintain data integrity."""

    def test_email_field_constraints(self):
        """Test email field allows empty string but not NULL."""
        from apps.users.models import User

        # Should work with empty string
        user1 = User.objects.create(
            username='empty_email_user',
            email='',
            password='testpass123'
        )
        self.assertEqual(user1.email, '')

        # Should work with valid email
        user2 = User.objects.create(
            username='valid_email_user',
            email='valid@example.com',
            password='testpass123'
        )
        self.assertEqual(user2.email, 'valid@example.com')

        # NULL should be handled (converted to empty string by model)
        user3 = User.objects.create(
            username='null_email_user',
            password='testpass123'
        )
        # Django's EmailField with blank=True defaults to empty string, not NULL
        self.assertEqual(user3.email, '')

    def test_trust_level_field_constraints(self):
        """Test trust_level field has correct default and choices."""
        from apps.users.models import User

        user = User.objects.create(
            username='trust_default_user',
            email='trust@example.com',
            password='testpass123'
        )

        # Should default to 'new'
        self.assertEqual(user.trust_level, 'new')

        # Should accept valid trust levels
        valid_levels = ['new', 'basic', 'trusted', 'veteran']
        for level in valid_levels:
            user.trust_level = level
            user.save()
            user.refresh_from_db()
            self.assertEqual(user.trust_level, level)
