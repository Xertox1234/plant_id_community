"""
Test forum CategoryViewSet.

Tests CRUD operations, hierarchical structure, permissions, and query parameters.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework import status

from ..models import Category

User = get_user_model()


class CategoryViewSetTests(TestCase):
    """Test CategoryViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users
        self.regular_user = User.objects.create_user(
            username='regular', password='pass'
        )
        self.moderator_group = Group.objects.get_or_create(name="Moderators")[0]
        self.moderator = User.objects.create_user(
            username='moderator', password='pass'
        )
        self.moderator.groups.add(self.moderator_group)

        self.staff_user = User.objects.create_user(
            username='staff', password='pass', is_staff=True
        )

        # Create category hierarchy
        self.root_category = Category.objects.create(
            name='Plant Care',
            slug='plant-care',
            description='General plant care topics',
            display_order=1,
            is_active=True
        )

        self.child_category = Category.objects.create(
            name='Watering',
            slug='watering',
            description='Watering techniques and schedules',
            parent=self.root_category,
            display_order=1,
            is_active=True
        )

        self.grandchild_category = Category.objects.create(
            name='Drought Resistant',
            slug='drought-resistant',
            description='Watering drought-resistant plants',
            parent=self.child_category,
            display_order=1,
            is_active=True
        )

        self.inactive_category = Category.objects.create(
            name='Inactive Category',
            slug='inactive',
            description='This category is inactive',
            display_order=99,
            is_active=False
        )

    def test_list_categories_flat(self):
        """GET /categories/ returns flat list by default."""
        response = self.client.get('/api/v1/forum/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        # Should return only active categories
        active_slugs = [cat['slug'] for cat in response.data['results']]
        self.assertIn('plant-care', active_slugs)
        self.assertIn('watering', active_slugs)
        self.assertIn('drought-resistant', active_slugs)
        self.assertNotIn('inactive', active_slugs)

    def test_list_categories_with_children(self):
        """GET /categories/?include_children=true prefetches children."""
        response = self.client.get('/api/v1/forum/categories/?include_children=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find root category in results
        root_cat = next(
            (cat for cat in response.data['results'] if cat['slug'] == 'plant-care'),
            None
        )

        self.assertIsNotNone(root_cat)
        self.assertIn('children', root_cat)
        self.assertTrue(len(root_cat['children']) > 0)

        # Verify child is in children list
        child_slugs = [child['slug'] for child in root_cat['children']]
        self.assertIn('watering', child_slugs)

    def test_retrieve_category_by_slug(self):
        """GET /categories/{slug}/ returns single category."""
        response = self.client.get('/api/v1/forum/categories/watering/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'watering')
        self.assertEqual(response.data['name'], 'Watering')
        self.assertIn('parent', response.data)
        self.assertIn('children', response.data)

        # Verify grandchild is in children
        child_slugs = [child['slug'] for child in response.data['children']]
        self.assertIn('drought-resistant', child_slugs)

    def test_tree_action_returns_hierarchy(self):
        """GET /categories/tree/ returns root categories with nested children."""
        response = self.client.get('/api/v1/forum/categories/tree/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        # Should only return root categories (parent=None)
        root_slugs = [cat['slug'] for cat in response.data]
        self.assertIn('plant-care', root_slugs)
        self.assertNotIn('watering', root_slugs)  # Not a root
        self.assertNotIn('drought-resistant', root_slugs)  # Not a root

        # Find root category
        root_cat = next(
            (cat for cat in response.data if cat['slug'] == 'plant-care'),
            None
        )

        self.assertIsNotNone(root_cat)
        self.assertIn('children', root_cat)

        # Verify nested structure
        child_slugs = [child['slug'] for child in root_cat['children']]
        self.assertIn('watering', child_slugs)

        # Find child category
        child_cat = next(
            (child for child in root_cat['children'] if child['slug'] == 'watering'),
            None
        )

        self.assertIsNotNone(child_cat)
        self.assertIn('children', child_cat)

        # Verify grandchild
        grandchild_slugs = [gc['slug'] for gc in child_cat['children']]
        self.assertIn('drought-resistant', grandchild_slugs)

    def test_inactive_categories_excluded_by_default(self):
        """GET /categories/ excludes inactive categories by default."""
        response = self.client.get('/api/v1/forum/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        slugs = [cat['slug'] for cat in response.data['results']]
        self.assertNotIn('inactive', slugs)

    def test_inactive_categories_included_with_parameter(self):
        """GET /categories/?is_active=false includes inactive categories."""
        response = self.client.get('/api/v1/forum/categories/?is_active=false')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        slugs = [cat['slug'] for cat in response.data['results']]
        self.assertIn('inactive', slugs)

    def test_ordering_by_display_order_and_name(self):
        """Categories are ordered by display_order, then name."""
        # Create categories with different display orders
        Category.objects.create(
            name='Zebra Category',
            slug='zebra',
            display_order=1,
            is_active=True
        )
        Category.objects.create(
            name='Apple Category',
            slug='apple',
            display_order=2,
            is_active=True
        )
        Category.objects.create(
            name='Beta Category',
            slug='beta',
            display_order=1,
            is_active=True
        )

        response = self.client.get('/api/v1/forum/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['results']
        # Find our test categories
        zebra_idx = next(i for i, cat in enumerate(results) if cat['slug'] == 'zebra')
        apple_idx = next(i for i, cat in enumerate(results) if cat['slug'] == 'apple')
        beta_idx = next(i for i, cat in enumerate(results) if cat['slug'] == 'beta')

        # display_order=1 should come before display_order=2
        self.assertLess(zebra_idx, apple_idx)
        self.assertLess(beta_idx, apple_idx)

        # Within display_order=1, 'Beta' should come before 'Zebra' (alphabetical)
        self.assertLess(beta_idx, zebra_idx)

    def test_create_category_requires_moderator(self):
        """POST /categories/ requires moderator permission."""
        # Regular user denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(
            '/api/v1/forum/categories/',
            {
                'name': 'Test Category',
                'slug': 'test-category',
                'description': 'Test description'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Moderator allowed
        self.client.force_authenticate(user=self.moderator)
        response = self.client.post(
            '/api/v1/forum/categories/',
            {
                'name': 'Test Category',
                'slug': 'test-category',
                'description': 'Test description'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['slug'], 'test-category')

    def test_update_category_requires_moderator(self):
        """PUT/PATCH /categories/{slug}/ requires moderator permission."""
        # Regular user denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch(
            f'/api/v1/forum/categories/{self.root_category.slug}/',
            {'description': 'Updated description'}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Staff user (also moderator) allowed
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.patch(
            f'/api/v1/forum/categories/{self.root_category.slug}/',
            {'description': 'Updated description'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated description')

    def test_delete_category_requires_moderator(self):
        """DELETE /categories/{slug}/ requires moderator permission."""
        test_category = Category.objects.create(
            name='To Delete',
            slug='to-delete',
            description='Will be deleted',
            is_active=True
        )

        # Regular user denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(f'/api/v1/forum/categories/{test_category.slug}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Moderator allowed
        self.client.force_authenticate(user=self.moderator)
        response = self.client.delete(f'/api/v1/forum/categories/{test_category.slug}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        self.assertFalse(Category.objects.filter(slug='to-delete').exists())

    def test_anonymous_can_read_categories(self):
        """Anonymous users can list and retrieve categories."""
        # Unauthenticated client
        response = self.client.get('/api/v1/forum/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f'/api/v1/forum/categories/{self.root_category.slug}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/categories/tree/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_write_categories(self):
        """Anonymous users cannot create, update, or delete categories."""
        # Unauthenticated client

        # Create denied
        response = self.client.post(
            '/api/v1/forum/categories/',
            {'name': 'Test', 'slug': 'test', 'description': 'Test'}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Update denied
        response = self.client.patch(
            f'/api/v1/forum/categories/{self.root_category.slug}/',
            {'description': 'Updated'}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Delete denied
        response = self.client.delete(f'/api/v1/forum/categories/{self.root_category.slug}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
