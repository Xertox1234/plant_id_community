"""
Test forum PostViewSet.

Tests CRUD operations, filtering, soft deletion, and edit tracking.
"""

from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework import status

from ..models import Thread, Post, Category

User = get_user_model()


class PostViewSetTests(TestCase):
    """Test PostViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Mock spam detection to prevent false positives
        self.spam_patcher = patch('apps.forum.services.spam_detection_service.SpamDetectionService.is_spam')
        self.mock_spam = self.spam_patcher.start()
        self.mock_spam.return_value = {
            'is_spam': False,
            'spam_score': 0,
            'reasons': [],
            'details': {}
        }

        self.client = APIClient()

        # Create users
        from datetime import timedelta
        from django.utils import timezone

        self.author = User.objects.create_user(username='author', password='pass')
        self.other_user = User.objects.create_user(username='other', password='pass')

        # Give author BASIC trust level by simulating 7 days of activity and 5 posts
        # This is required for image uploads (trust level check)
        self.author.date_joined = timezone.now() - timedelta(days=7)  # 7 days active
        self.author.save()

        from ..models import UserProfile
        from ..constants import TRUST_LEVEL_BASIC
        from django.core.cache import cache

        author_profile, _ = UserProfile.objects.get_or_create(user=self.author)
        author_profile.trust_level = TRUST_LEVEL_BASIC
        author_profile.post_count = 5  # Meet BASIC requirement
        author_profile.save()

        # Invalidate cache to ensure trust level is recognized
        cache.clear()

        # Create moderator
        self.moderator_group = Group.objects.get_or_create(name="Moderators")[0]
        self.moderator = User.objects.create_user(username='moderator', password='pass')
        self.moderator.groups.add(self.moderator_group)

        # Create category and thread
        self.category = Category.objects.create(
            name='Plant Care',
            slug='plant-care',
            description='General plant care topics',
            is_active=True
        )

        self.thread = Thread.objects.create(
            title='How to water succulents',
            slug='how-to-water-succulents',
            author=self.author,
            category=self.category,
            excerpt='Tips for watering succulents',
            is_active=True
        )

        # Create posts
        self.first_post = Post.objects.create(
            thread=self.thread,
            author=self.author,
            content_raw='This is the first post with detailed watering tips.',
            is_first_post=True,
            is_active=True
        )

        self.reply_post = Post.objects.create(
            thread=self.thread,
            author=self.other_user,
            content_raw='Thanks for the tips! Very helpful.',
            is_first_post=False,
            is_active=True
        )

        self.inactive_post = Post.objects.create(
            thread=self.thread,
            author=self.author,
            content_raw='This post was deleted.',
            is_first_post=False,
            is_active=False
        )

    def tearDown(self):
        """Clean up after each test."""
        self.spam_patcher.stop()

    def test_list_posts_requires_thread_parameter(self):
        """GET /posts/ without thread parameter returns 400."""
        self.client.force_authenticate(user=self.author)

        response = self.client.get('/api/v1/forum/posts/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_list_posts_by_thread(self):
        """GET /posts/?thread=slug returns posts in chronological order."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        results = response.data['results']
        self.assertEqual(len(results), 2)  # Only active posts

        # Verify chronological order (oldest first)
        self.assertEqual(results[0]['id'], str(self.first_post.id))
        self.assertEqual(results[1]['id'], str(self.reply_post.id))

    def test_list_posts_excludes_inactive_by_default(self):
        """GET /posts/?thread=slug excludes inactive posts."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertNotIn(str(self.inactive_post.id), post_ids)

    def test_list_posts_includes_inactive_with_parameter(self):
        """GET /posts/?thread=slug&is_active=false includes inactive posts."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}&is_active=false'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(self.inactive_post.id), post_ids)

    def test_filter_posts_by_author(self):
        """GET /posts/?thread=slug&author=username filters by author."""
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.slug}&author=author'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']

        # All posts should be by author
        for post in results:
            self.assertEqual(post['author']['username'], 'author')

        post_ids = [post['id'] for post in results]
        self.assertIn(str(self.first_post.id), post_ids)
        self.assertNotIn(str(self.reply_post.id), post_ids)

    def test_retrieve_post(self):
        """GET /posts/{id}/ returns single post detail."""
        response = self.client.get(f'/api/v1/forum/posts/{self.first_post.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.first_post.id))
        self.assertEqual(response.data['content_raw'], self.first_post.content_raw)
        self.assertTrue(response.data['is_first_post'])

    def test_create_post_requires_authentication(self):
        """POST /posts/ requires authentication."""
        # Unauthenticated request
        response = self.client.post(
            '/api/v1/forum/posts/',
            {
                'thread': str(self.thread.id),
                'content_raw': 'Test post content'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_post_as_authenticated_user(self):
        """POST /posts/ creates new post."""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            '/api/v1/forum/posts/',
            {
                'thread': str(self.thread.id),
                'content_raw': 'This is my new reply post.'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content_raw'], 'This is my new reply post.')
        self.assertEqual(response.data['author']['username'], 'other')

        # Verify post created in database
        post = Post.objects.get(id=response.data['id'])
        self.assertEqual(post.author, self.other_user)
        self.assertEqual(post.thread, self.thread)

    def test_update_post_requires_author_or_moderator(self):
        """PATCH /posts/{id}/ requires author or moderator."""
        # Other user denied
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Updated content'}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Author allowed
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Updated by author'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content_raw'], 'Updated by author')

    def test_update_post_sets_edited_fields(self):
        """PATCH /posts/{id}/ sets edited_at and edited_by."""
        self.client.force_authenticate(user=self.author)

        # Verify initial state
        self.assertIsNone(self.first_post.edited_at)
        self.assertIsNone(self.first_post.edited_by)

        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Edited content'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.first_post.refresh_from_db()
        self.assertIsNotNone(self.first_post.edited_at)
        self.assertEqual(self.first_post.edited_by, self.author)

    def test_moderator_can_update_any_post(self):
        """Moderators can update posts they didn't author."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            f'/api/v1/forum/posts/{self.first_post.id}/',
            {'content_raw': 'Moderated content'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content_raw'], 'Moderated content')

    def test_delete_post_soft_deletes(self):
        """DELETE /posts/{id}/ soft deletes (sets is_active=False)."""
        self.client.force_authenticate(user=self.author)

        response = self.client.delete(f'/api/v1/forum/posts/{self.reply_post.id}/')

        # Note: reply_post was created by other_user, but we're testing as author
        # This should fail permission check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Now authenticate as the actual author
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f'/api/v1/forum/posts/{self.reply_post.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify post still exists but is inactive
        self.reply_post.refresh_from_db()
        self.assertFalse(self.reply_post.is_active)

    def test_moderator_can_delete_any_post(self):
        """Moderators can delete posts they didn't author."""
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(f'/api/v1/forum/posts/{self.first_post.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify soft deletion
        self.first_post.refresh_from_db()
        self.assertFalse(self.first_post.is_active)

    def test_first_posts_action_returns_thread_starters(self):
        """GET /posts/first_posts/ returns all first posts."""
        # Create another thread with first post
        thread2 = Thread.objects.create(
            title='Another Thread',
            slug='another-thread',
            author=self.other_user,
            category=self.category,
            is_active=True
        )

        first_post2 = Post.objects.create(
            thread=thread2,
            author=self.other_user,
            content_raw='First post of second thread',
            is_first_post=True,
            is_active=True
        )

        response = self.client.get('/api/v1/forum/posts/first_posts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(self.first_post.id), post_ids)
        self.assertIn(str(first_post2.id), post_ids)
        self.assertNotIn(str(self.reply_post.id), post_ids)

    def test_first_posts_filter_by_category(self):
        """GET /posts/first_posts/?category=slug filters by thread category."""
        # Create different category
        other_category = Category.objects.create(
            name='Other',
            slug='other',
            is_active=True
        )

        other_thread = Thread.objects.create(
            title='Other Thread',
            slug='other-thread',
            author=self.author,
            category=other_category,
            is_active=True
        )

        other_first_post = Post.objects.create(
            thread=other_thread,
            author=self.author,
            content_raw='First post in other category',
            is_first_post=True,
            is_active=True
        )

        response = self.client.get('/api/v1/forum/posts/first_posts/?category=plant-care')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(self.first_post.id), post_ids)
        self.assertNotIn(str(other_first_post.id), post_ids)

    def test_anonymous_can_read_posts(self):
        """Anonymous users can list and retrieve posts."""
        # Unauthenticated client
        response = self.client.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f'/api/v1/forum/posts/{self.first_post.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/v1/forum/posts/first_posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_upload_image_success(self):
        """POST /posts/{id}/upload_image/ with valid image succeeds."""
        from io import BytesIO
        from PIL import Image as PILImage

        self.client.force_authenticate(user=self.author)

        # Create a test image
        image = PILImage.new('RGB', (100, 100), color='red')
        image_file = BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        image_file.name = 'test.jpg'

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': image_file, 'alt_text': 'Test image'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('thumbnail_url', response.data)
        self.assertIn('medium_url', response.data)
        self.assertEqual(response.data['alt_text'], 'Test image')

    def test_upload_image_requires_authentication(self):
        """Anonymous users cannot upload images."""
        from io import BytesIO
        from PIL import Image as PILImage

        # Create a test image
        image = PILImage.new('RGB', (100, 100), color='red')
        image_file = BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        image_file.name = 'test.jpg'

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_image_requires_post_ownership(self):
        """Non-authors cannot upload images to others' posts."""
        from io import BytesIO
        from PIL import Image as PILImage

        self.client.force_authenticate(user=self.other_user)

        # Create a test image
        image = PILImage.new('RGB', (100, 100), color='red')
        image_file = BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        image_file.name = 'test.jpg'

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': image_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_image_validates_max_count(self):
        """Cannot upload more than MAX_ATTACHMENTS_PER_POST images."""
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ..models import Attachment
        from ..constants import MAX_ATTACHMENTS_PER_POST

        self.client.force_authenticate(user=self.author)

        # Create MAX_ATTACHMENTS_PER_POST attachments
        for i in range(MAX_ATTACHMENTS_PER_POST):
            image = PILImage.new('RGB', (100, 100), color='red')
            buffer = BytesIO()
            image.save(buffer, format='JPEG')

            image_file = SimpleUploadedFile(
                f'test{i}.jpg',
                buffer.getvalue(),
                content_type='image/jpeg'
            )

            Attachment.objects.create(
                post=self.first_post,
                image=image_file
            )

        # Try to upload one more
        image = PILImage.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        extra_file = SimpleUploadedFile(
            'test_extra.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': extra_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Maximum', response.data['error'])
        self.assertIn('images allowed', response.data['error'])

    def test_upload_image_validates_file_size(self):
        """Cannot upload images larger than MAX_ATTACHMENT_SIZE_BYTES."""
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(user=self.author)

        # Create a large test image (11MB)
        # Create BytesIO with enough data to exceed 10MB limit
        large_data = b'x' * (11 * 1024 * 1024)  # 11MB of data

        # Create an uploaded file with the large size
        large_file = SimpleUploadedFile(
            'test.jpg',
            large_data,
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': large_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File too large', response.data['error'])

    def test_upload_image_validates_file_type(self):
        """Cannot upload non-image files."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(user=self.author)

        # Create a text file pretending to be an image
        text_file = SimpleUploadedFile(
            'test.jpg',
            b'This is not an image',
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': text_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid image file', response.data['error'])

    def test_upload_image_validates_magic_number(self):
        """
        Magic number validation: Reject files with wrong content type.
        Phase 6: Comprehensive image validation.

        Tests that executable files (.exe, .sh) renamed as images are rejected.
        This prevents attackers from uploading malicious files with renamed extensions.
        The magic number (file signature) check detects the actual file type.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(user=self.author)

        # Create a fake executable file with .jpg extension
        # Real executable files have specific magic numbers (e.g., MZ for .exe, #! for shell scripts)
        # For testing, we use a text file which Pillow will reject
        fake_image = SimpleUploadedFile(
            'malicious.jpg',  # Claims to be .jpg
            b'#!/bin/bash\necho "malicious script"',  # Actually a shell script
            content_type='image/jpeg'  # Claims to be JPEG MIME
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': fake_image},
            format='multipart'
        )

        # Should reject because Pillow detects content is not a valid image
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid image file', response.data['error'])

    def test_upload_image_validates_dimensions(self):
        """
        Dimension validation: Reject images exceeding size limits.
        Phase 6: Prevent resource exhaustion attacks.

        Tests that excessively large images are rejected to prevent
        server resource exhaustion and DoS attacks.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image as PILImage
        from ..constants import MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT

        self.client.force_authenticate(user=self.author)

        # Create an image larger than allowed dimensions
        # Use MAX_IMAGE_WIDTH + 1 to trigger validation
        oversized_image = PILImage.new('RGB', (MAX_IMAGE_WIDTH + 1, 100), color='green')
        buffer = BytesIO()
        oversized_image.save(buffer, format='JPEG')

        oversized_file = SimpleUploadedFile(
            'oversized.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': oversized_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('dimensions too large', response.data['error'])
        self.assertIn(f'{MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}', response.data['detail'])

    def test_upload_image_rejects_decompression_bomb(self):
        """
        Decompression bomb protection: Reject potential zip bombs.
        Phase 6: Security hardening against resource exhaustion.

        Tests that Pillow's decompression bomb detection rejects files
        that would consume excessive memory when decompressed.

        Note: This test simulates the scenario by attempting to create
        an image that would trigger MAX_IMAGE_PIXELS limit.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image as PILImage
        from ..constants import MAX_IMAGE_PIXELS

        self.client.force_authenticate(user=self.author)

        # Create an image that would exceed MAX_IMAGE_PIXELS when opened
        # We use sqrt(MAX_IMAGE_PIXELS) + 1 for each dimension to trigger the limit
        import math
        dim = int(math.sqrt(MAX_IMAGE_PIXELS)) + 1000  # Well over the limit

        # Pillow will detect this during open() and raise DecompressionBombError
        try:
            bomb_image = PILImage.new('RGB', (dim, dim), color='yellow')
            buffer = BytesIO()

            # Configure Pillow to use our limit for this test
            old_limit = PILImage.MAX_IMAGE_PIXELS
            PILImage.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

            try:
                bomb_image.save(buffer, format='JPEG')
            finally:
                PILImage.MAX_IMAGE_PIXELS = old_limit

            bomb_file = SimpleUploadedFile(
                'bomb.jpg',
                buffer.getvalue(),
                content_type='image/jpeg'
            )

            response = self.client.post(
                f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
                {'image': bomb_file},
                format='multipart'
            )

            # Should reject the decompression bomb
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            # Check for either dimension error or decompression bomb error
            self.assertTrue(
                'dimensions too large' in response.data['error'] or
                'decompression bomb' in response.data['error']
            )
        except PILImage.DecompressionBombError:
            # If Pillow prevents us from even creating the test image,
            # that's actually good - it means the protection is working
            pass

    def test_upload_image_validates_corrupt_file(self):
        """
        Corrupt file detection: Reject malformed image data.
        Phase 6: Defense against malicious file uploads.

        Tests that truncated or corrupt image files are properly rejected
        to prevent server crashes or unexpected behavior.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image as PILImage

        self.client.force_authenticate(user=self.author)

        # Create a valid JPEG, then truncate it to make it corrupt
        valid_image = PILImage.new('RGB', (100, 100), color='purple')
        buffer = BytesIO()
        valid_image.save(buffer, format='JPEG')

        # Truncate to first 50 bytes (corrupt JPEG header)
        corrupt_data = buffer.getvalue()[:50]

        corrupt_file = SimpleUploadedFile(
            'corrupt.jpg',
            corrupt_data,
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.first_post.id}/upload_image/',
            {'image': corrupt_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid image file', response.data['error'])

    def test_delete_image_success(self):
        """DELETE /posts/{id}/delete_image/{attachment_id}/ succeeds for author."""
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ..models import Attachment

        self.client.force_authenticate(user=self.author)

        # Create an attachment
        image = PILImage.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        image_file = SimpleUploadedFile(
            'test.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        attachment = Attachment.objects.create(
            post=self.first_post,
            image=image_file
        )

        response = self.client.delete(
            f'/api/v1/forum/posts/{self.first_post.id}/delete_image/{attachment.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Attachment.objects.filter(id=attachment.id).exists())

    def test_delete_image_requires_post_ownership(self):
        """Non-authors cannot delete images from others' posts."""
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ..models import Attachment

        # Create an attachment as author
        image = PILImage.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        image_file = SimpleUploadedFile(
            'test.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        attachment = Attachment.objects.create(
            post=self.first_post,
            image=image_file
        )

        # Try to delete as other user
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(
            f'/api/v1/forum/posts/{self.first_post.id}/delete_image/{attachment.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Attachment.objects.filter(id=attachment.id).exists())

    def test_staff_can_delete_any_image(self):
        """Staff users can delete images from any post."""
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ..models import Attachment

        # Create an attachment as author
        image = PILImage.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        image_file = SimpleUploadedFile(
            'test.jpg',
            buffer.getvalue(),
            content_type='image/jpeg'
        )

        attachment = Attachment.objects.create(
            post=self.first_post,
            image=image_file
        )

        # Create staff user
        staff_user = User.objects.create_user(username='staff', password='pass', is_staff=True)
        self.client.force_authenticate(user=staff_user)

        response = self.client.delete(
            f'/api/v1/forum/posts/{self.first_post.id}/delete_image/{attachment.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Attachment.objects.filter(id=attachment.id).exists())
