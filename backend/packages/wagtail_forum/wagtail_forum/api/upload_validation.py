"""4-layer validation for forum image uploads (Spec 2 PR-3).

Mirrors the canonical pattern in `backend/docs/patterns/security/file-upload.md`
(extension, MIME, size, PIL decode + decompression-bomb + dimension caps). The
logic is copied in rather than imported because the package must not depend on
the host's `apps.*` namespace (`tests/test_reusability.py`).
"""

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from ..conf import get_setting

logger = logging.getLogger("wagtail_forum")


def validate_image_upload(image_file):
    """Raise ``ValidationError`` (-> 400) if *image_file* fails any of 4 layers."""
    from PIL import Image as PILImage

    extensions = get_setting("IMAGE_ALLOWED_EXTENSIONS")
    mime_types = get_setting("IMAGE_ALLOWED_MIME_TYPES")
    max_size = get_setting("IMAGE_MAX_SIZE_BYTES")
    max_pixels = get_setting("IMAGE_MAX_PIXELS")
    max_width = get_setting("IMAGE_MAX_WIDTH")
    max_height = get_setting("IMAGE_MAX_HEIGHT")

    # Layer 1: extension allowlist (blocks .php/.exe masquerading as an image).
    name = image_file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in extensions:
        raise ValidationError(
            _("Invalid file type. Allowed: %(allowed)s.")
            % {"allowed": ", ".join(extensions)}
        )

    # Layer 2: MIME allowlist (catches a declared content-type that isn't an image).
    if image_file.content_type not in mime_types:
        raise ValidationError(
            _('Invalid file content type "%(content_type)s".')
            % {"content_type": image_file.content_type}
        )

    # Layer 3: size cap (DoS guard).
    if image_file.size > max_size:
        raise ValidationError(
            _("File too large. Maximum %(max_mb)sMB.")
            % {"max_mb": max_size // (1024 * 1024)}
        )

    # Layer 4: PIL magic-number decode + decompression-bomb + dimension caps.
    try:
        PILImage.MAX_IMAGE_PIXELS = max_pixels
        image_file.seek(0)
        with PILImage.open(image_file) as img:
            img.verify()
            width, height = img.size
            if width > max_width or height > max_height:
                raise ValidationError(
                    _("Image dimensions too large. Maximum %(width)sx%(height)s.")
                    % {"width": max_width, "height": max_height}
                )
            if (img.format or "").lower() not in ("jpeg", "png", "gif", "webp"):
                raise ValidationError(
                    _('Invalid image format "%(format)s".') % {"format": img.format}
                )
        image_file.seek(0)  # reset the pointer for the subsequent save
    except ValidationError:
        raise  # a dimension/format rejection above — don't relabel it "invalid"
    except PILImage.DecompressionBombError:
        logger.warning(
            "[SECURITY] Forum image rejected (decompression bomb): name=%s size=%s",
            image_file.name,
            image_file.size,
        )
        raise ValidationError(_("Image file rejected as a decompression bomb."))
    except Exception as exc:  # not a decodable image
        logger.warning(
            "[SECURITY] Forum image rejected (invalid): name=%s error=%s",
            image_file.name,
            exc,
        )
        raise ValidationError(_("Invalid image file."))
