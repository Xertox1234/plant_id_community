"""
Security validators for the Plant Community application.

This module contains validation functions to ensure secure file uploads
and input handling across the application.
"""

import os
import mimetypes
from typing import List, Optional
from django.core.exceptions import ValidationError
from django.conf import settings
from PIL import Image
# import magic  # Commented out until python-magic is installed
import logging

logger = logging.getLogger(__name__)

# Allowed file types for different contexts
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_IMAGE_MIMETYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/gif'
}

# Maximum file sizes (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AVATAR_SIZE = 2 * 1024 * 1024   # 2MB

# Image dimension limits
MAX_IMAGE_DIMENSIONS = (4096, 4096)  # Max 4K resolution
MIN_IMAGE_DIMENSIONS = (50, 50)      # Minimum for visibility


class SecureFileValidator:
    """
    Comprehensive file validation for security and integrity.
    """
    
    @staticmethod
    def validate_image_file(file, max_size: int = MAX_IMAGE_SIZE) -> None:
        """
        Validate uploaded image files for security and format compliance.
        
        Args:
            file: Uploaded file object
            max_size: Maximum allowed file size in bytes
            
        Raises:
            ValidationError: If file fails validation
        """
        # Check file size
        if file.size > max_size:
            raise ValidationError(
                f'File size {file.size} bytes exceeds maximum allowed size of {max_size} bytes.'
            )
        
        # Check file extension
        name = file.name.lower() if file.name else ''
        extension = os.path.splitext(name)[1]
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(
                f'File extension "{extension}" is not allowed. '
                f'Allowed extensions: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'
            )
        
        # Check MIME type using python-magic for security (fallback to basic check)
        try:
            file.seek(0)
            file_header = file.read(1024)  # Read first 1KB
            file.seek(0)
            
            # Try to use python-magic if available, otherwise use basic extension check
            try:
                import magic
                detected_mime = magic.from_buffer(file_header, mime=True)
                if detected_mime not in ALLOWED_IMAGE_MIMETYPES:
                    raise ValidationError(
                        f'File type "{detected_mime}" is not allowed. '
                        f'This appears to be a {detected_mime} file, not an image.'
                    )
            except ImportError:
                # Fallback to basic validation using file extension and PIL
                logger.info("python-magic not available, using basic file validation")
                pass
        except Exception as e:
            logger.warning(f"Could not detect file type: {e}")
            # Fallback to Django's mime type detection
            guessed_type = mimetypes.guess_type(name)[0]
            if guessed_type not in ALLOWED_IMAGE_MIMETYPES:
                raise ValidationError('Could not verify file type as a valid image.')
        
        # Validate image integrity using PIL
        try:
            file.seek(0)
            with Image.open(file) as img:
                # Verify it's a valid image
                img.verify()
                
                # Reset file pointer and check dimensions
                file.seek(0)
                with Image.open(file) as img2:
                    width, height = img2.size
                    
                    # Check minimum dimensions
                    if width < MIN_IMAGE_DIMENSIONS[0] or height < MIN_IMAGE_DIMENSIONS[1]:
                        raise ValidationError(
                            f'Image dimensions {width}x{height} are too small. '
                            f'Minimum required: {MIN_IMAGE_DIMENSIONS[0]}x{MIN_IMAGE_DIMENSIONS[1]}'
                        )
                    
                    # Check maximum dimensions
                    if width > MAX_IMAGE_DIMENSIONS[0] or height > MAX_IMAGE_DIMENSIONS[1]:
                        raise ValidationError(
                            f'Image dimensions {width}x{height} are too large. '
                            f'Maximum allowed: {MAX_IMAGE_DIMENSIONS[0]}x{MAX_IMAGE_DIMENSIONS[1]}'
                        )
                    
                    # Check for suspicious aspect ratios (potential exploits)
                    aspect_ratio = max(width, height) / min(width, height)
                    if aspect_ratio > 10:  # Very thin/wide images can cause issues
                        raise ValidationError(
                            'Image aspect ratio is too extreme. Please use a more balanced image.'
                        )
        
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f'Invalid or corrupted image file: {str(e)}')
        
        finally:
            file.seek(0)  # Reset file pointer for subsequent use
    
    @staticmethod
    def validate_avatar_image(file) -> None:
        """Validate avatar images with stricter size limits."""
        SecureFileValidator.validate_image_file(file, max_size=MAX_AVATAR_SIZE)
    
    @staticmethod
    def validate_plant_identification_image(file) -> None:
        """Validate plant identification images."""
        SecureFileValidator.validate_image_file(file, max_size=MAX_IMAGE_SIZE)
        
        # Additional validation for plant ID images
        try:
            file.seek(0)
            with Image.open(file) as img:
                width, height = img.size
                
                # Minimum size for plant identification effectiveness
                if width < 200 or height < 200:
                    raise ValidationError(
                        'Plant identification images should be at least 200x200 pixels '
                        'for better identification accuracy.'
                    )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            # If PIL fails, the main validation already caught it
        finally:
            file.seek(0)


def validate_image_file(file):
    """Django validator function for image files."""
    SecureFileValidator.validate_image_file(file)


def validate_avatar_image(file):
    """Django validator function for avatar images."""
    SecureFileValidator.validate_avatar_image(file)


def validate_plant_identification_image(file):
    """Django validator function for plant identification images."""
    SecureFileValidator.validate_plant_identification_image(file)


class InputSanitizer:
    """
    Input sanitization utilities for text fields.
    """
    
    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 100) -> str:
        """
        Sanitize filename for safe storage.
        
        Args:
            filename: Original filename
            max_length: Maximum allowed length
            
        Returns:
            Sanitized filename
        """
        if not filename:
            return 'unnamed_file'
        
        # Remove directory traversal attempts
        filename = os.path.basename(filename)
        
        # Remove or replace dangerous characters
        dangerous_chars = '<>:"|?*'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # Limit length
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[:max_length-len(ext)] + ext
        
        # Ensure it's not empty
        if not filename or filename.isspace():
            filename = 'unnamed_file'
        
        return filename
    
    @staticmethod
    def sanitize_text_input(text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize text input for safe storage and display.
        
        Args:
            text: Input text
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
        """
        if not text:
            return ''
        
        # Remove null bytes (can cause issues in some systems)
        text = text.replace('\x00', '')
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Limit length if specified
        if max_length and len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    @staticmethod
    def validate_scientific_name(name: str) -> str:
        """
        Validate and sanitize scientific plant names.
        
        Args:
            name: Scientific name input
            
        Returns:
            Validated scientific name
            
        Raises:
            ValidationError: If name format is invalid
        """
        if not name:
            raise ValidationError('Scientific name cannot be empty.')
        
        # Basic sanitization
        name = InputSanitizer.sanitize_text_input(name, max_length=200)
        
        # Scientific names should contain only letters, spaces, dots, and hyphens
        import re
        if not re.match(r'^[A-Za-z\s.-]+$', name):
            raise ValidationError(
                'Scientific names should contain only letters, spaces, dots, and hyphens.'
            )
        
        # Should have at least genus and species (two words)
        words = name.split()
        if len(words) < 2:
            raise ValidationError(
                'Scientific names should contain at least genus and species (two words).'
            )
        
        return name.title()  # Proper capitalization


# Security event logging
class SecurityLogger:
    """
    Centralized security event logging.
    """
    
    @staticmethod
    def log_file_upload_attempt(user, filename: str, file_size: int, success: bool, error: str = None):
        """Log file upload attempts for security monitoring."""
        user_id = user.id if user and hasattr(user, 'id') else 'anonymous'
        
        if success:
            logger.info(
                f"File upload successful: user={user_id}, file={filename}, size={file_size}"
            )
        else:
            logger.warning(
                f"File upload failed: user={user_id}, file={filename}, size={file_size}, error={error}"
            )
    
    @staticmethod
    def log_suspicious_activity(user, activity: str, details: dict = None):
        """Log suspicious activities for security monitoring."""
        user_id = user.id if user and hasattr(user, 'id') else 'anonymous'
        logger.warning(
            f"Suspicious activity: user={user_id}, activity={activity}, details={details or {}}"
        )
    
    @staticmethod
    def log_validation_failure(user, field: str, value_type: str, error: str):
        """Log validation failures that might indicate attacks."""
        user_id = user.id if user and hasattr(user, 'id') else 'anonymous'
        logger.warning(
            f"Validation failure: user={user_id}, field={field}, type={value_type}, error={error}"
        )