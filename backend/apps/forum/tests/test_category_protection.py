"""
Test suite for Category CASCADE protection (Issue #003).

Tests verify that:
1. PROTECT constraint prevents deletion of parent categories with children
2. Admin interface provides clear error messages
3. Categories without children can be deleted normally
4. Threads CASCADE delete with their category (intended behavior)

Pattern follows TRUST_LEVEL_PATTERNS_CODIFIED.md testing patterns.
"""

from django.test import TestCase
from django.db.models import ProtectedError
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.base import BaseStorage
from django.test import RequestFactory

from apps.forum.models import Category, Thread, Post
from apps.forum.admin import CategoryAdmin


class MessageStorage(BaseStorage):
    """
    Simple in-memory message storage for testing.

    Django messages framework requires session middleware in production,
    but tests need a simpler approach.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def _store(self, messages, response, *args, **kwargs):
        self.messages.extend(messages)
        return []

    def _get(self, *args, **kwargs):
        return self.messages, True

User = get_user_model()


class CategoryProtectionTestCase(TestCase):
    """
    Test Category CASCADE protection to prevent accidental data loss.

    Issue #003: Deleting parent category CASCADE deletes all child categories
    and 900+ threads. PROTECT constraint prevents this.
    """

    def setUp(self):
        """Create test category hierarchy and threads."""
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

        # Create category hierarchy
        # Plant Care (parent)
        #   ├─ Watering (child)
        #   └─ Fertilizing (child)
        self.parent_category = Category.objects.create(
            name='Plant Care',
            slug='plant-care',
            description='General plant care discussions'
        )

        self.child_category_1 = Category.objects.create(
            name='Watering',
            slug='watering',
            description='Watering techniques and schedules',
            parent=self.parent_category
        )

        self.child_category_2 = Category.objects.create(
            name='Fertilizing',
            slug='fertilizing',
            description='Fertilizer types and application',
            parent=self.parent_category
        )

        # Create threads in child categories
        self.thread_watering = Thread.objects.create(
            title='How often to water succulents?',
            author=self.user,
            category=self.child_category_1,
            excerpt='Need advice on watering frequency'
        )

        self.thread_fertilizing = Thread.objects.create(
            title='Best organic fertilizers?',
            author=self.user,
            category=self.child_category_2,
            excerpt='Looking for organic fertilizer recommendations'
        )

        # Create posts in threads
        Post.objects.create(
            thread=self.thread_watering,
            author=self.user,
            content_raw='What is the best watering schedule for succulents?',
            is_first_post=True
        )

        Post.objects.create(
            thread=self.thread_fertilizing,
            author=self.user,
            content_raw='Can anyone recommend good organic fertilizers?',
            is_first_post=True
        )

    def test_protect_prevents_parent_deletion_with_children(self):
        """
        Test PROTECT constraint prevents deletion of parent category with children.

        Expected: ProtectedError raised when attempting to delete parent category.
        """
        child_count_before = self.parent_category.children.count()
        self.assertEqual(child_count_before, 2, "Parent should have 2 children")

        with self.assertRaises(ProtectedError) as context:
            self.parent_category.delete()

        # Verify parent still exists
        self.assertTrue(
            Category.objects.filter(pk=self.parent_category.pk).exists(),
            "Parent category should still exist after failed deletion"
        )

        # Verify children still exist
        self.assertTrue(
            Category.objects.filter(pk=self.child_category_1.pk).exists(),
            "Child category 1 should still exist"
        )
        self.assertTrue(
            Category.objects.filter(pk=self.child_category_2.pk).exists(),
            "Child category 2 should still exist"
        )

        # Verify threads still exist
        self.assertTrue(
            Thread.objects.filter(pk=self.thread_watering.pk).exists(),
            "Thread in child category 1 should still exist"
        )
        self.assertTrue(
            Thread.objects.filter(pk=self.thread_fertilizing.pk).exists(),
            "Thread in child category 2 should still exist"
        )

    def test_leaf_category_can_be_deleted_with_cascade(self):
        """
        Test leaf categories (no children) CAN be deleted.

        Threads CASCADE delete with category (intended behavior).
        Expected: Child category and its threads deleted, parent unaffected.
        """
        child_id = self.child_category_1.pk
        thread_id = self.thread_watering.pk

        # Delete child category (has no children, only threads)
        self.child_category_1.delete()

        # Verify child category deleted
        self.assertFalse(
            Category.objects.filter(pk=child_id).exists(),
            "Child category should be deleted"
        )

        # Verify thread CASCADE deleted (intended)
        self.assertFalse(
            Thread.objects.filter(pk=thread_id).exists(),
            "Thread should CASCADE delete with category (intended behavior)"
        )

        # Verify parent still exists
        self.assertTrue(
            Category.objects.filter(pk=self.parent_category.pk).exists(),
            "Parent category should remain after child deletion"
        )

        # Verify other child still exists
        self.assertTrue(
            Category.objects.filter(pk=self.child_category_2.pk).exists(),
            "Other child category should remain"
        )

    def test_parent_can_be_deleted_after_children_removed(self):
        """
        Test parent category CAN be deleted after all children are removed.

        Expected: After deleting children, parent deletion succeeds.
        """
        # First delete children
        self.child_category_1.delete()
        self.child_category_2.delete()

        # Now parent has no children
        self.assertEqual(
            self.parent_category.children.count(), 0,
            "Parent should have no children after deletion"
        )

        # Parent deletion should succeed
        parent_id = self.parent_category.pk
        self.parent_category.delete()

        self.assertFalse(
            Category.objects.filter(pk=parent_id).exists(),
            "Parent category should be deleted after children removed"
        )

    def test_category_thread_count_method(self):
        """
        Test Category.get_thread_count() returns accurate count.

        Used by admin interface to display thread count.
        """
        # Parent category has no direct threads
        parent_count = self.parent_category.get_thread_count()
        self.assertEqual(
            parent_count, 0,
            "Parent category should have 0 direct threads"
        )

        # Child categories have 1 thread each
        child_1_count = self.child_category_1.get_thread_count()
        self.assertEqual(
            child_1_count, 1,
            "Child category 1 should have 1 thread"
        )

        child_2_count = self.child_category_2.get_thread_count()
        self.assertEqual(
            child_2_count, 1,
            "Child category 2 should have 1 thread"
        )

        # Create additional thread in child_1
        Thread.objects.create(
            title='Another watering question',
            author=self.user,
            category=self.child_category_1,
            excerpt='More watering advice needed'
        )

        # Refresh and verify count updated
        child_1_count_updated = self.child_category_1.get_thread_count()
        self.assertEqual(
            child_1_count_updated, 2,
            "Child category 1 should now have 2 threads"
        )


class CategoryAdminProtectionTestCase(TestCase):
    """
    Test CategoryAdmin interface provides clear error messages.

    Verifies admin UI guides users through proper deletion order.
    """

    def setUp(self):
        """Create test data and admin instances."""
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

        # Create category with child
        self.parent = Category.objects.create(
            name='Parent Category',
            slug='parent-category'
        )
        self.child = Category.objects.create(
            name='Child Category',
            slug='child-category',
            parent=self.parent
        )

        # Create thread in child
        self.thread = Thread.objects.create(
            title='Test Thread',
            author=self.user,
            category=self.child,
            excerpt='Test excerpt'
        )

        # Setup admin
        self.site = AdminSite()
        self.admin = CategoryAdmin(Category, self.site)
        self.factory = RequestFactory()

    def test_admin_delete_model_prevents_parent_deletion(self):
        """
        Test CategoryAdmin.delete_model() prevents deletion with clear message.

        Expected: Error message displayed, category not deleted.
        """
        # Create mock request with message storage
        request = self.factory.post('/admin/forum/category/')
        request.user = self.admin_user
        request._messages = MessageStorage(request)

        # Attempt to delete parent (has 1 child)
        self.admin.delete_model(request, self.parent)

        # Verify parent still exists (deletion prevented)
        self.assertTrue(
            Category.objects.filter(pk=self.parent.pk).exists(),
            "Parent category should still exist after admin delete attempt"
        )

        # Verify error message was added
        messages = list(request._messages)
        self.assertTrue(
            any('Cannot delete' in str(m) for m in messages),
            "Admin should display error message for protected deletion"
        )
        self.assertTrue(
            any('subcategor' in str(m).lower() for m in messages),
            "Error message should mention subcategories"
        )

    def test_admin_delete_queryset_prevents_bulk_deletion(self):
        """
        Test CategoryAdmin.delete_queryset() prevents bulk deletion.

        Expected: Error message displayed, categories not deleted.
        """
        # Create mock request with message storage
        request = self.factory.post('/admin/forum/category/')
        request.user = self.admin_user
        request._messages = MessageStorage(request)

        # Attempt bulk delete of parent
        queryset = Category.objects.filter(pk=self.parent.pk)
        self.admin.delete_queryset(request, queryset)

        # Verify parent still exists
        self.assertTrue(
            Category.objects.filter(pk=self.parent.pk).exists(),
            "Parent category should still exist after bulk delete attempt"
        )

        # Verify error message
        messages = list(request._messages)
        self.assertTrue(
            any('Cannot delete' in str(m) for m in messages),
            "Admin should display error message for bulk delete"
        )

    def test_admin_thread_count_display(self):
        """
        Test CategoryAdmin.thread_count_display() shows accurate count.

        Expected: Thread count displayed with proper pluralization.
        """
        # Parent has no direct threads
        parent_display = self.admin.thread_count_display(self.parent)
        self.assertEqual(
            parent_display, '0 threads',
            "Parent should display '0 threads'"
        )

        # Child has 1 thread
        child_display = self.admin.thread_count_display(self.child)
        self.assertEqual(
            child_display, '1 thread',
            "Child should display '1 thread' (singular)"
        )

        # Create second thread
        Thread.objects.create(
            title='Second Thread',
            author=self.user,
            category=self.child,
            excerpt='Another thread'
        )

        # Verify plural
        child_display_updated = self.admin.thread_count_display(self.child)
        self.assertEqual(
            child_display_updated, '2 threads',
            "Child should display '2 threads' (plural)"
        )

    def test_admin_allows_leaf_deletion_with_warning(self):
        """
        Test CategoryAdmin allows deletion of leaf categories with thread warning.

        Expected: Warning message about CASCADE, but deletion proceeds.
        """
        # Create mock request with message storage
        request = self.factory.post('/admin/forum/category/')
        request.user = self.admin_user
        request._messages = MessageStorage(request)

        thread_id = self.thread.pk

        # Delete child (has no children, only threads)
        self.admin.delete_model(request, self.child)

        # Verify child deleted
        self.assertFalse(
            Category.objects.filter(pk=self.child.pk).exists(),
            "Child category should be deleted"
        )

        # Verify thread CASCADE deleted
        self.assertFalse(
            Thread.objects.filter(pk=thread_id).exists(),
            "Thread should CASCADE delete with category"
        )

        # Verify warning message about threads
        messages = list(request._messages)
        # Should have both warning and success messages
        self.assertTrue(
            any('thread' in str(m).lower() for m in messages),
            "Admin should warn about thread deletion"
        )


class CategoryHierarchyIntegrationTestCase(TestCase):
    """
    Integration tests for complex category hierarchy scenarios.

    Tests multi-level hierarchies and edge cases.
    """

    def setUp(self):
        """Create multi-level category hierarchy."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create 3-level hierarchy
        # Plants (L0)
        #   ├─ Indoor (L1)
        #   │   ├─ Succulents (L2)
        #   │   └─ Ferns (L2)
        #   └─ Outdoor (L1)
        #       └─ Trees (L2)

        self.level_0 = Category.objects.create(
            name='Plants',
            slug='plants'
        )

        self.level_1_a = Category.objects.create(
            name='Indoor',
            slug='indoor',
            parent=self.level_0
        )

        self.level_1_b = Category.objects.create(
            name='Outdoor',
            slug='outdoor',
            parent=self.level_0
        )

        self.level_2_a = Category.objects.create(
            name='Succulents',
            slug='succulents',
            parent=self.level_1_a
        )

        self.level_2_b = Category.objects.create(
            name='Ferns',
            slug='ferns',
            parent=self.level_1_a
        )

        self.level_2_c = Category.objects.create(
            name='Trees',
            slug='trees',
            parent=self.level_1_b
        )

    def test_cannot_delete_level_0_with_nested_children(self):
        """
        Test PROTECT prevents deletion of top-level category with nested hierarchy.

        Expected: ProtectedError raised, entire hierarchy preserved.
        """
        with self.assertRaises(ProtectedError):
            self.level_0.delete()

        # Verify entire hierarchy still exists
        self.assertTrue(Category.objects.filter(pk=self.level_0.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_1_a.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_1_b.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_2_a.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_2_b.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_2_c.pk).exists())

    def test_cannot_delete_level_1_with_children(self):
        """
        Test PROTECT prevents deletion of mid-level category.

        Expected: ProtectedError raised, children preserved.
        """
        with self.assertRaises(ProtectedError):
            self.level_1_a.delete()

        # Verify level 1 and its children still exist
        self.assertTrue(Category.objects.filter(pk=self.level_1_a.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_2_a.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_2_b.pk).exists())

    def test_can_delete_leaf_categories(self):
        """
        Test leaf categories (no children) can be deleted.

        Expected: Only leaf deleted, hierarchy above preserved.
        """
        leaf_id = self.level_2_a.pk

        self.level_2_a.delete()

        # Verify leaf deleted
        self.assertFalse(Category.objects.filter(pk=leaf_id).exists())

        # Verify hierarchy above preserved
        self.assertTrue(Category.objects.filter(pk=self.level_0.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_1_a.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.level_2_b.pk).exists())

    def test_cascading_deletion_after_children_removed(self):
        """
        Test proper deletion order: leaves → branches → root.

        Expected: Categories can be deleted from bottom to top.
        """
        # Step 1: Delete all level 2 (leaf) categories
        self.level_2_a.delete()
        self.level_2_b.delete()
        self.level_2_c.delete()

        # Step 2: Now level 1 categories have no children, can be deleted
        self.level_1_a.delete()
        self.level_1_b.delete()

        # Step 3: Now level 0 has no children, can be deleted
        level_0_id = self.level_0.pk
        self.level_0.delete()

        # Verify entire hierarchy deleted
        self.assertFalse(Category.objects.filter(pk=level_0_id).exists())
        self.assertEqual(
            Category.objects.count(), 0,
            "All categories should be deleted"
        )
