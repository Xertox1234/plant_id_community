"""Private storage for scan photos (Scan 2.0 B2).

Scan photos are user plant photos. They must NEVER go through the default
storage: in prod that serves public, permanent URLs. This storage has no
public URL at all; the app streams the bytes through an authenticated
endpoint (B4) and never calls ``.url()``.
"""

from __future__ import annotations

import io
import os
from functools import lru_cache

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from PIL import Image, ImageOps
from plant_community_backend.r2_config import R2_REGION_NAME

MAX_SCAN_PHOTO_SIDE = 1600
SCAN_PHOTO_JPEG_QUALITY = 85


class ScanPhotoFileSystemStorage(FileSystemStorage):
    """Local-disk scan storage whose root is read from settings on every use.

    ``ImageField(storage=callable)`` calls the callable once, at import, so a
    root baked in at construction could never follow ``override_settings``.
    The app never calls ``.url()``; there is no base URL on purpose.
    """

    @property
    def base_location(self) -> str:
        return str(settings.SCAN_PHOTO_LOCAL_ROOT)

    @property
    def location(self) -> str:
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


@lru_cache(maxsize=None)
def _build_storage(
    use_r2: bool,
    bucket: str,
    access_key: str,
    secret_key: str,
    endpoint_url: str,
) -> Storage:
    if use_r2:
        from storages.backends.s3 import S3Storage

        s3: Storage = S3Storage(
            bucket_name=bucket,
            access_key=access_key,
            secret_key=secret_key,
            endpoint_url=endpoint_url,
            region_name=R2_REGION_NAME,
            custom_domain=None,
            querystring_auth=True,
            file_overwrite=False,
            default_acl=None,
            object_parameters={"CacheControl": "private, no-store"},
        )
        return s3
    return ScanPhotoFileSystemStorage()


def scan_photo_storage() -> Storage:
    """The private storage for scan photos.

    Cached per effective R2 configuration (the cache key is the settings that
    shape the S3 storage), so a settings override takes effect without a manual
    cache clear. The local-disk storage reads its root from settings itself.
    """
    storage: Storage = _build_storage(
        bool(settings.USE_R2),
        settings.R2_SCANS_BUCKET_NAME,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
        settings.R2_ENDPOINT_URL,
    )
    return storage


def normalize_scan_photo(upload) -> ContentFile:
    """Re-encode ``upload`` as a JPEG of at most 1600 px on the longest side.

    Re-encoding drops EXIF (GPS included); the orientation is applied to the
    pixels first so the photo stays upright. Raises ``ValueError`` if the
    bytes do not decode as an image.
    """
    try:
        with Image.open(upload) as src:
            img = ImageOps.exif_transpose(src)
            img.load()
    except Exception as exc:
        raise ValueError("Not a decodable image") from exc
    img = img.convert("RGB")
    img.thumbnail((MAX_SCAN_PHOTO_SIDE, MAX_SCAN_PHOTO_SIDE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=SCAN_PHOTO_JPEG_QUALITY)
    return ContentFile(buf.getvalue(), name="photo.jpg")
