"""Avatar storage hygiene (todo 565, owner decisions 2026-10-11).

* A replaced or removed avatar is deleted, with its imagekit thumbnail.
  ``ImageField`` never deletes a file it stops pointing at, so every "Change
  photo" used to leave the old photo stored, and public at its old URL on R2.
* An uploaded avatar is re-encoded from its pixels, which drops EXIF (GPS
  included), XMP and every other metadata chunk before it is stored. A phone
  photo's location would otherwise be served to anyone who sees the avatar.
"""

from __future__ import annotations

import io
import logging
import os
from typing import TYPE_CHECKING, List

from apps.core.validators import MAX_AVATAR_SIZE
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from .models import User

logger = logging.getLogger(__name__)

# What each stored format is re-encoded as. GIF becomes PNG: an avatar is one
# frame anyway (the mobile picker flattens it too), and PNG keeps alpha. MPO is
# how Pillow reports a phone JPEG that carries extra frames (an HDR gain map, a
# depth map): it is a JPEG, and re-encoded as PNG it grew past the size cap.
_REENCODE = {"JPEG": "JPEG", "MPO": "JPEG", "PNG": "PNG", "WEBP": "WEBP", "GIF": "PNG"}
_EXTENSION = {"JPEG": None, "PNG": ".png", "WEBP": ".webp"}


class AvatarReencodeError(ValueError):
    """The upload passed the header checks but cannot be stored. The
    serializer answers each subclass with its own fixed message, so no
    exception text reaches the client."""


class AvatarUnreadableError(AvatarReencodeError):
    """Its pixels do not decode, or its format is not one we store."""


class AvatarTooLargeError(AvatarReencodeError):
    """Larger than ``MAX_AVATAR_SIZE`` once re-encoded."""


_SAVE_OPTIONS = {"JPEG": {"quality": 90}, "WEBP": {"quality": 90}, "PNG": {}}


def avatar_file_names(user: "User") -> List[str]:
    """The stored names of ``user``'s avatar and its thumbnail, if any.

    The thumbnail's name is computed from the source name; reading it does
    not generate the file. Call this BEFORE the avatar changes.
    """
    if not user.avatar:
        return []
    return [user.avatar.name, user.avatar_thumbnail.name]


def delete_avatar_files_on_commit(user: "User", names: List[str]) -> None:
    """Delete ``names`` from the avatar's storage once the change commits.

    After the commit, so a rolled-back change never loses the file it still
    points at. Never raises: a storage failure leaves an orphan behind, which
    is logged, rather than failing a profile update that already succeeded.
    """
    if not names:
        return
    storage = user.avatar.storage

    def delete() -> None:
        for name in names:
            try:
                storage.delete(name)
            except Exception:
                logger.exception("[PROFILE] Could not delete a replaced avatar file")

    transaction.on_commit(delete)


def strip_image_metadata(upload: "UploadedFile") -> ContentFile:
    """``upload`` re-encoded from its pixels alone, with no metadata.

    Orientation is applied first (``exif_transpose``), or a portrait phone
    photo would be stored sideways once its EXIF orientation is gone. Same
    approach as the forum's link-preview images
    (``apps.forum_host.link_preview``).

    ``upload`` has already passed ``validate_avatar_image`` (type, size,
    dimensions), but that check reads only the header. A file whose pixels
    fail to decode, a format outside ``_REENCODE``, or a re-encoded photo larger
    than ``MAX_AVATAR_SIZE`` raises ``AvatarReencodeError``, which the
    serializer turns into a 400.
    """
    upload.seek(0)
    try:
        with Image.open(upload) as source:
            source_format = source.format
            source.load()
            image = ImageOps.exif_transpose(source)
        target = _REENCODE[source_format]
        has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
        mode = "RGBA" if has_alpha and target != "JPEG" else "RGB"
        image = image.convert(mode)
        # Rebuilt from pixels alone, so nothing still in ``image.info`` (EXIF,
        # XMP, ICC, comments) can reach the encoder.
        clean = Image.frombytes(mode, image.size, image.tobytes())
        output = io.BytesIO()
        clean.save(output, target, **_SAVE_OPTIONS[target])
    except (OSError, ValueError, KeyError, Image.DecompressionBombError) as exc:
        raise AvatarUnreadableError() from exc
    if output.tell() > MAX_AVATAR_SIZE:
        raise AvatarTooLargeError()

    name = os.path.basename(upload.name or "avatar")
    extension = _EXTENSION[target]
    if extension and not name.lower().endswith(extension):
        name = f"{os.path.splitext(name)[0]}{extension}"
    return ContentFile(output.getvalue(), name=name)
