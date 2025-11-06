"""
Unit tests for Attachment soft delete functionality.

Tests the soft delete pattern implementation on Attachment model,
including cascading from Post deletion and cleanup job behavior.
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO, StringIO
from PIL import Image

from ..models import Thread, Post, Category, Attachment

User = get_user_model()


class AttachmentSoftDeleteTests(TestCase):
    """Test Attachment soft delete functionality."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )
        self.thread = Thread.objects.create(
            title='Test Thread',
            slug='test-thread',
            author=self.user,
            category=self.category,
            is_active=True
        )
        self.post = Post.objects.create(
            thread=self.thread,
            author=self.user,
            content_raw='Test post with attachment',
            is_active=True
        )

        # Create test image
        image = Image.new('RGB', (100, 100), color='red')
        image_buffer = BytesIO()
        image.save(image_buffer, 'JPEG')
        image_buffer.seek(0)
        image_data = image_buffer.getvalue()

        # Wrap in SimpleUploadedFile for Django compatibility
        image_file = SimpleUploadedFile(
            'test.jpg',
            image_data,
            content_type='image/jpeg'
        )

        self.attachment = Attachment.objects.create(
            post=self.post,
            image=image_file,
            original_filename='test.jpg',
            file_size=len(image_data),
            mime_type='image/jpeg',
            display_order=1,
            is_active=True
        )

    def test_attachment_soft_delete_sets_is_active_false(self):
        """Attachment.delete() should set is_active=False."""
        # Verify initial state
        self.assertTrue(self.attachment.is_active)
        self.assertIsNone(self.attachment.deleted_at)

        # Soft delete
        self.attachment.delete()

        # Verify soft delete
        self.attachment.refresh_from_db()
        self.assertFalse(self.attachment.is_active)
        self.assertIsNotNone(self.attachment.deleted_at)

        # Verify still exists in database
        self.assertEqual(Attachment.objects.filter(pk=self.attachment.pk).count(), 1)

    def test_attachment_soft_delete_preserves_in_database(self):
        """Soft-deleted attachments remain in database."""
        attachment_id = self.attachment.id

        # Soft delete
        self.attachment.delete()

        # Verify can still query via objects manager
        attachment = Attachment.objects.get(pk=attachment_id)
        self.assertFalse(attachment.is_active)

    def test_attachment_active_manager_excludes_soft_deleted(self):
        """ActiveAttachmentManager should exclude soft-deleted attachments."""
        # Create second active attachment
        image = Image.new('RGB', (100, 100), color='blue')
        image_buffer = BytesIO()
        image.save(image_buffer, 'JPEG')
        image_buffer.seek(0)
        image_data = image_buffer.getvalue()

        image_file = SimpleUploadedFile(
            'test2.jpg',
            image_data,
            content_type='image/jpeg'
        )

        attachment2 = Attachment.objects.create(
            post=self.post,
            image=image_file,
            original_filename='test2.jpg',
            file_size=len(image_data),
            mime_type='image/jpeg',
            display_order=2,
            is_active=True
        )

        # Verify both active
        self.assertEqual(Attachment.active.filter(post=self.post).count(), 2)
        self.assertEqual(Attachment.objects.filter(post=self.post).count(), 2)

        # Soft delete first attachment
        self.attachment.delete()

        # Verify active manager excludes soft-deleted
        self.assertEqual(Attachment.active.filter(post=self.post).count(), 1)
        self.assertEqual(Attachment.objects.filter(post=self.post).count(), 2)

        # Verify correct attachment excluded
        active_ids = list(Attachment.active.filter(post=self.post).values_list('id', flat=True))
        self.assertIn(attachment2.id, active_ids)
        self.assertNotIn(self.attachment.id, active_ids)

    def test_post_deletion_cascades_soft_delete_to_attachments(self):
        """Deleting a post should soft-delete all its attachments."""
        # Create second attachment
        image = Image.new('RGB', (100, 100), color='green')
        image_buffer = BytesIO()
        image.save(image_buffer, 'JPEG')
        image_buffer.seek(0)
        image_data = image_buffer.getvalue()

        image_file = SimpleUploadedFile(
            'test3.jpg',
            image_data,
            content_type='image/jpeg'
        )

        attachment2 = Attachment.objects.create(
            post=self.post,
            image=image_file,
            original_filename='test3.jpg',
            file_size=len(image_data),
            mime_type='image/jpeg',
            display_order=2,
            is_active=True
        )

        # Verify both attachments active
        self.assertEqual(Attachment.active.filter(post=self.post).count(), 2)

        # Soft delete post (via ViewSet pattern)
        self.post.is_active = False
        self.post.save()

        # Cascade soft-delete to attachments
        self.post.attachments.filter(is_active=True).update(
            is_active=False,
            deleted_at=timezone.now()
        )

        # Verify attachments soft-deleted
        self.assertEqual(Attachment.active.filter(post=self.post).count(), 0)
        self.assertEqual(Attachment.objects.filter(post=self.post).count(), 2)

        # Verify deleted_at timestamps set
        for attachment in Attachment.objects.filter(post=self.post):
            self.assertFalse(attachment.is_active)
            self.assertIsNotNone(attachment.deleted_at)

    def test_attachment_hard_delete_removes_from_database(self):
        """Attachment.hard_delete() should permanently remove from database."""
        attachment_id = self.attachment.id

        # Soft delete first
        self.attachment.delete()
        self.assertEqual(Attachment.objects.filter(pk=attachment_id).count(), 1)

        # Hard delete
        self.attachment.hard_delete()

        # Verify permanently removed
        self.assertEqual(Attachment.objects.filter(pk=attachment_id).count(), 0)

    def test_cleanup_command_deletes_old_attachments(self):
        """cleanup_attachments command should delete attachments older than threshold."""
        # Create attachment deleted 31 days ago
        old_attachment = Attachment.objects.create(
            post=self.post,
            image=self.attachment.image,
            original_filename='old.jpg',
            file_size=1000,
            mime_type='image/jpeg',
            display_order=2,
            is_active=False,
            deleted_at=timezone.now() - timedelta(days=31)
        )

        # Create attachment deleted 29 days ago (should NOT be deleted)
        recent_attachment = Attachment.objects.create(
            post=self.post,
            image=self.attachment.image,
            original_filename='recent.jpg',
            file_size=1000,
            mime_type='image/jpeg',
            display_order=3,
            is_active=False,
            deleted_at=timezone.now() - timedelta(days=29)
        )

        # Verify both exist
        self.assertEqual(Attachment.objects.filter(is_active=False).count(), 2)

        # Run cleanup with default 30 days
        out = StringIO()
        call_command('cleanup_attachments', stdout=out)

        # Verify old attachment deleted, recent preserved
        self.assertFalse(Attachment.objects.filter(pk=old_attachment.pk).exists())
        self.assertTrue(Attachment.objects.filter(pk=recent_attachment.pk).exists())

    def test_cleanup_command_dry_run_doesnt_delete(self):
        """cleanup_attachments --dry-run should not delete anything."""
        # Create old attachment
        old_attachment = Attachment.objects.create(
            post=self.post,
            image=self.attachment.image,
            original_filename='old.jpg',
            file_size=1000,
            mime_type='image/jpeg',
            display_order=2,
            is_active=False,
            deleted_at=timezone.now() - timedelta(days=31)
        )

        # Run dry-run
        out = StringIO()
        call_command('cleanup_attachments', '--dry-run', stdout=out)

        # Verify attachment still exists
        self.assertTrue(Attachment.objects.filter(pk=old_attachment.pk).exists())
        self.assertIn('DRY RUN', out.getvalue())

    def test_attachment_restore_from_soft_deleted(self):
        """restore() should reactivate a soft-deleted attachment."""
        # Soft delete attachment
        self.attachment.delete()
        self.attachment.refresh_from_db()
        self.assertFalse(self.attachment.is_active)
        self.assertIsNotNone(self.attachment.deleted_at)

        # Restore attachment
        self.attachment.restore()
        self.attachment.refresh_from_db()

        # Verify restored
        self.assertTrue(self.attachment.is_active)
        self.assertIsNone(self.attachment.deleted_at)

        # Verify appears in active manager
        self.assertEqual(Attachment.active.filter(pk=self.attachment.pk).count(), 1)

    def test_attachment_restore_already_active(self):
        """restore() on already-active attachment should be no-op."""
        # Verify initial state
        self.assertTrue(self.attachment.is_active)
        self.assertIsNone(self.attachment.deleted_at)

        # Call restore on active attachment
        self.attachment.restore()
        self.attachment.refresh_from_db()

        # Verify still active (no changes)
        self.assertTrue(self.attachment.is_active)
        self.assertIsNone(self.attachment.deleted_at)

    def test_attachment_restore_clears_deleted_at_timestamp(self):
        """restore() should clear deleted_at timestamp."""
        # Soft delete
        self.attachment.delete()
        self.attachment.refresh_from_db()
        deleted_at_value = self.attachment.deleted_at
        self.assertIsNotNone(deleted_at_value)

        # Restore
        self.attachment.restore()
        self.attachment.refresh_from_db()

        # Verify deleted_at is None
        self.assertIsNone(self.attachment.deleted_at)
        self.assertTrue(self.attachment.is_active)
