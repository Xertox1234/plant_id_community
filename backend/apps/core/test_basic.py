"""
Basic tests to demonstrate testing infrastructure.
"""

from django.test import TestCase
from django.urls import reverse


class BasicTestCase(TestCase):
    """Basic tests to verify testing infrastructure works."""
    
    def test_addition(self):
        """Test that basic math works (sanity check)."""
        self.assertEqual(2 + 2, 4)
    
    def test_string_operations(self):
        """Test string operations."""
        test_string = "Plant Community"
        self.assertTrue(test_string.startswith("Plant"))
        self.assertIn("Community", test_string)
    
    def test_list_operations(self):
        """Test list operations."""
        plants = ["Rose", "Tulip", "Sunflower"]
        self.assertEqual(len(plants), 3)
        plants.append("Lily")
        self.assertEqual(len(plants), 4)
        self.assertIn("Rose", plants)


class DjangoBasicTestCase(TestCase):
    """Basic Django-specific tests."""
    
    def test_database_access(self):
        """Test that we can access the test database."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Create a test user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('testpass123'))
    
    def test_settings_accessible(self):
        """Test that Django settings are accessible."""
        from django.conf import settings
        
        self.assertTrue(hasattr(settings, 'DEBUG'))
        self.assertTrue(hasattr(settings, 'INSTALLED_APPS'))
        self.assertIn('django.contrib.auth', settings.INSTALLED_APPS)