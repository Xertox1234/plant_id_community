"""
File upload validation utility for plant identification.

Implements three-layer defense-in-depth validation:
1. Content-Type header check (fast but spoofable)
2. File magic bytes verification (reliable, cannot be spoofed)
3. PIL image verification (ensures complete valid image)

Security: Prevents malicious file upload attacks (CWE-434)
"""

from PIL import Image
try:
    import magic
    _HAS_MAGIC = True
except ImportError:
    _HAS_MAGIC = False

from rest_framework.exceptions import ValidationError
from typing import BinaryIO
import logging

logger = logging.getLogger(__name__)


def validate_image_file(image_file: BinaryIO) -> bool:
    """
    Validate image file using three layers of security.

    Defense-in-depth approach:
    1. Content-Type header check (fast, first line of defense)
    2. File magic bytes verification (reliable, cannot be spoofed)
    3. PIL image open and verify (ensures complete valid image)

    Args:
        image_file: Django UploadedFile object

    Raises:
        ValidationError: If file is not a valid image

    Returns:
        True if all validation layers pass

    Examples:
        >>> validate_image_file(request.FILES['image'])
        True  # Valid JPEG image

        >>> validate_image_file(malicious_exe)
        ValidationError: File content does not match declared type

    Security:
        - Prevents Content-Type spoofing attacks
        - Detects renamed executables (.exe → .jpg)
        - Rejects corrupted or incomplete images
        - CWE-434: Unrestricted Upload of File with Dangerous Type
    """
    allowed_content_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    allowed_magic_types = ['image/jpeg', 'image/png', 'image/webp']

    # Layer 1: Check Content-Type header (fast but spoofable)
    if image_file.content_type not in allowed_content_types:
        raise ValidationError(
            f"Invalid Content-Type: {image_file.content_type}. "
            f"Allowed types: {', '.join(allowed_content_types)}"
        )

    # Layer 2: Verify file magic bytes (more reliable)
    if _HAS_MAGIC:
        image_file.seek(0)
        file_header = image_file.read(2048)  # Read first 2KB for magic detection
        image_file.seek(0)  # Reset file pointer for later processing

        mime = magic.from_buffer(file_header, mime=True)
        if mime not in allowed_magic_types:
            raise ValidationError(
                f"File content does not match declared type. "
                f"Detected: {mime}, Expected: {image_file.content_type}. "
                f"File may be renamed or have spoofed Content-Type header."
            )
    else:
        logger.warning(
            "[SECURITY] python-magic not available - skipping magic byte validation. "
            "Install with: pip install python-magic and brew install libmagic (macOS) "
            "or apt-get install libmagic1 (Ubuntu)"
        )

    # Layer 3: Try to open with PIL (ensures it's a complete, valid image)
    try:
        image_file.seek(0)
        img = Image.open(image_file)
        img.verify()  # Verify it's a complete image without loading entire file
        image_file.seek(0)  # Reset for later processing
    except Exception as e:
        raise ValidationError(
            f"Invalid or corrupted image file: {str(e)}. "
            f"File may be incomplete, corrupted, or not a valid image."
        )

    return True
