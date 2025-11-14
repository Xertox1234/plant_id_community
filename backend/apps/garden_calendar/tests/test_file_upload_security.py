"""
File Upload Security Tests for PlantImage

Tests all 4 security layers for plant image uploads:
1. File extension validation
2. MIME type validation
3. File size validation
4. PIL magic number + decompression bomb protection

Follows pattern from: docs/patterns/security/file-upload.md
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from PIL import Image
from unittest.mock import patch
import io

from ..models import GardenBed, Plant, PlantImage
from ..constants import (
    MAX_PLANT_IMAGE_SIZE_BYTES,
    MAX_IMAGES_PER_PLANT,
    MAX_IMAGE_WIDTH,
    MAX_IMAGE_HEIGHT,
)

User = get_user_model()


class FileUploadSecurityTestCase(TestCase):
    """
    Test 4-layer file upload security for PlantImage.

    URL Pattern: /api/v1/calendar/api/plants/{uuid}/upload_image/
    - /api/v1/ - API versioning prefix (project urls.py)
    - /calendar/ - Garden calendar app prefix (project urls.py:128)
    - /api/ - API router prefix (garden_calendar/urls.py:45)
    - /plants/ - PlantViewSet router registration (garden_calendar/urls.py:36)
    - /upload_image/ - @action decorator (views.py:877)
    """

    def setUp(self):
        """Set up test user, garden bed, and plant."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised',
            length_inches=96,
            width_inches=48
        )

        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date='2025-05-01'
        )

    def create_test_image(self, width=100, height=100, format='JPEG'):
        """Helper to create a valid test image."""
        img = Image.new('RGB', (width, height), color='red')
        img_io = io.BytesIO()
        img.save(img_io, format=format)
        img_io.seek(0)
        return img_io

    # =========================================================================
    # Layer 1: File Extension Validation Tests
    # =========================================================================

    def test_invalid_extension_php_rejected(self):
        """Layer 1: PHP file extension should be rejected."""
        file = SimpleUploadedFile(
            'malicious.php',
            b'<?php echo "hack"; ?>',
            content_type='application/x-php'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid file type', response.data['error'])

    def test_invalid_extension_exe_rejected(self):
        """Layer 1: EXE file extension should be rejected."""
        file = SimpleUploadedFile(
            'malware.exe',
            b'MZ\x90\x00',  # EXE magic number
            content_type='application/x-msdownload'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid file type', response.data['error'])

    def test_valid_extensions_accepted(self):
        """Layer 1: Valid extensions (jpg, jpeg, png, gif, webp) should be accepted."""
        for ext, format_name in [('jpg', 'JPEG'), ('jpeg', 'JPEG'), ('png', 'PNG'), ('gif', 'GIF')]:
            with self.subTest(extension=ext):
                img_io = self.create_test_image(format=format_name.upper())
                file = SimpleUploadedFile(
                    f'valid.{ext}',
                    img_io.read(),
                    content_type=f'image/{format_name.lower()}'
                )

                response = self.client.post(
                    f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
                    {'image': file},
                    format='multipart'
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

                # Clean up for next iteration
                PlantImage.objects.filter(plant=self.plant).delete()

    # =========================================================================
    # Layer 2: MIME Type Validation Tests
    # =========================================================================

    def test_invalid_mime_type_rejected(self):
        """Layer 2: Invalid MIME type should be rejected."""
        # PHP file renamed to .jpg but with wrong MIME type
        file = SimpleUploadedFile(
            'fake.jpg',
            b'<?php echo "hack"; ?>',
            content_type='application/x-php'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid file content type', response.data['error'])

    def test_mime_type_spoofing_rejected(self):
        """Layer 2: Content-type spoofing should be rejected (caught by Layer 4)."""
        # Executable with fake MIME type (will fail at Layer 4 magic number check)
        file = SimpleUploadedFile(
            'fake.jpg',
            b'MZ\x90\x00This is not an image',
            content_type='image/jpeg'  # Spoofed MIME type
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should be caught by Layer 4 (PIL magic number check)
        self.assertIn('Invalid image file', response.data['error'])

    # =========================================================================
    # Layer 3: File Size Validation Tests
    # =========================================================================

    def test_oversized_file_rejected(self):
        """Layer 3: Files exceeding size limit should be rejected."""
        # Create file larger than MAX_PLANT_IMAGE_SIZE_BYTES (10MB)
        large_data = b'x' * (MAX_PLANT_IMAGE_SIZE_BYTES + 1024)
        file = SimpleUploadedFile(
            'large.jpg',
            large_data,
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File too large', response.data['error'])

    def test_max_size_file_accepted(self):
        """Layer 3: Files at max size should be accepted (if valid image)."""
        # Create small valid image (well under limit)
        img_io = self.create_test_image()
        file = SimpleUploadedFile(
            'valid.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # =========================================================================
    # Layer 4: PIL Magic Number + Decompression Bomb Tests
    # =========================================================================

    def test_non_image_file_rejected(self):
        """Layer 4: Non-image files should be rejected by PIL."""
        # Text file with .jpg extension and image MIME type
        file = SimpleUploadedFile(
            'fake.jpg',
            b'This is not an image file',
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid image file', response.data['error'])

    def test_oversized_dimensions_rejected(self):
        """Layer 4: Images exceeding dimension limits should be rejected."""
        # Create image larger than MAX_IMAGE_WIDTH x MAX_IMAGE_HEIGHT
        img = Image.new('RGB', (MAX_IMAGE_WIDTH + 100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)

        file = SimpleUploadedFile(
            'huge.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Image dimensions too large', response.data['error'])

    def test_decompression_bomb_rejected(self):
        """Layer 4: Decompression bombs should be rejected."""
        # Mock PIL.Image.open to raise DecompressionBombError
        # This simulates an image that would exceed MAX_IMAGE_PIXELS when decompressed
        img_io = self.create_test_image()
        file = SimpleUploadedFile(
            'bomb.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        with patch('PIL.Image.open') as mock_open:
            # Simulate decompression bomb detection
            mock_open.side_effect = Image.DecompressionBombError(
                "Image size (150000000 pixels) exceeds limit of 100000000 pixels"
            )

            response = self.client.post(
                f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
                {'image': file},
                format='multipart'
            )

            # Verify decompression bomb rejection with explicit assertions
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('error', response.data, "Response should contain 'error' field")

            # Check error message indicates rejection (handles both 'error' and 'detail' fields)
            error_message = response.data['error'].lower()
            detail_message = response.data.get('detail', '').lower()
            combined_message = f"{error_message} {detail_message}"

            self.assertIn('rejected', combined_message,
                         f"Expected 'rejected' in error message, got: {response.data}")

    def test_valid_image_accepted(self):
        """Layer 4: Valid images should pass all checks."""
        # Create valid 100x100 JPEG
        img_io = self.create_test_image(100, 100, 'JPEG')
        file = SimpleUploadedFile(
            'valid.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('uuid', response.data)
        self.assertIn('image_url', response.data)

    # =========================================================================
    # Additional Security Tests
    # =========================================================================

    def test_image_count_limit_enforced(self):
        """Maximum image count per plant should be enforced."""
        # Upload MAX_IMAGES_PER_PLANT images
        for i in range(MAX_IMAGES_PER_PLANT):
            img_io = self.create_test_image()
            file = SimpleUploadedFile(
                f'image{i}.jpg',
                img_io.read(),
                content_type='image/jpeg'
            )

            response = self.client.post(
                f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
                {'image': file},
                format='multipart'
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Try to upload one more (should fail)
        img_io = self.create_test_image()
        file = SimpleUploadedFile(
            'extra.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(f'Maximum {MAX_IMAGES_PER_PLANT} images', response.data['error'])

    def test_primary_image_unsets_other_primary(self):
        """Setting is_primary should unset other primary images."""
        # Upload first image as primary
        img_io = self.create_test_image()
        file = SimpleUploadedFile(
            'image1.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file, 'is_primary': True},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        image1_uuid = response.data['uuid']

        # Upload second image as primary
        img_io = self.create_test_image()
        file = SimpleUploadedFile(
            'image2.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file, 'is_primary': True},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify first image is no longer primary
        image1 = PlantImage.objects.get(uuid=image1_uuid)
        self.assertFalse(image1.is_primary)

    def test_caption_saved_correctly(self):
        """Image caption should be saved correctly."""
        img_io = self.create_test_image()
        file = SimpleUploadedFile(
            'test.jpg',
            img_io.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/calendar/api/plants/{self.plant.uuid}/upload_image/',
            {'image': file, 'caption': 'First seedling leaves'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        image = PlantImage.objects.get(uuid=response.data['uuid'])
        self.assertEqual(image.caption, 'First seedling leaves')
