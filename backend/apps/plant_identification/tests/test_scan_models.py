"""ScanJob models and the private scan photo storage (Scan 2.0 B2)."""

import io
import uuid
from datetime import date
from pathlib import Path

import pytest
from apps.plant_identification.scan_models import ScanJob, ScanJobImage
from apps.plant_identification.scan_storage import (
    normalize_scan_photo,
    scan_photo_storage,
)
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import override_settings
from PIL import Image

GPS_IFD = 0x8825
MAKE = 0x010F


def _jpeg_with_exif(size=(2400, 1200)) -> bytes:
    exif = Image.Exif()
    exif[MAKE] = "PhoneMaker"
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (37.0, 46.0, 30.0)
    buf = io.BytesIO()
    Image.new("RGB", size, (40, 120, 40)).save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


@pytest.fixture
def roots(tmp_path):
    media = tmp_path / "media"
    private = tmp_path / "private"
    media.mkdir()
    private.mkdir()
    with override_settings(MEDIA_ROOT=str(media), SCAN_PHOTO_LOCAL_ROOT=str(private)):
        yield media, private


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="scanner", email="scanner@example.com", password="x" * 16
    )


@pytest.fixture
def job(user):
    return ScanJob.objects.create(
        user=user, mode="diagnose", local_date=date(2026, 11, 2)
    )


def _add_photo(job, role="leaf"):
    return ScanJobImage.objects.create(
        job=job,
        role=role,
        image=normalize_scan_photo(ContentFile(_jpeg_with_exif(), name="x.jpg")),
    )


@pytest.mark.django_db
def test_photo_saved_to_private_storage_not_default(roots, job):
    media, private = roots
    row = _add_photo(job)
    expected = f"scans/{job.user_id}/{job.uuid}/leaf.jpg"
    assert row.image.name == expected
    assert (private / expected).is_file()
    assert not any(p.is_file() for p in Path(media).rglob("*"))
    assert default_storage.exists(expected) is False


@pytest.mark.django_db
def test_photo_is_reencoded_without_exif(roots, job):
    row = _add_photo(job)
    with row.image.open("rb") as fh, Image.open(fh) as im:
        exif = im.getexif()
        assert dict(exif) == {}
        assert dict(exif.get_ifd(GPS_IFD)) == {}
        assert im.format == "JPEG"
        assert max(im.size) <= 1600


@pytest.mark.django_db
def test_user_delete_removes_photo_files(
    roots, job, user, django_capture_on_commit_callbacks
):
    _, private = roots
    row = _add_photo(job)
    path = private / row.image.name
    assert path.is_file()
    with django_capture_on_commit_callbacks(execute=True):
        user.delete()
    assert not path.exists()


@pytest.mark.django_db
def test_role_is_unique_per_job(roots, job):
    from django.db import IntegrityError, transaction

    _add_photo(job, "leaf")
    with pytest.raises(IntegrityError), transaction.atomic():
        _add_photo(job, "leaf")


@pytest.mark.django_db
def test_job_defaults(job):
    assert isinstance(job.uuid, uuid.UUID)
    assert job.status == "pending"
    assert job.charged_as == ""
    assert job.attempts == 0
    assert ScanJob.ACTIVE_STATUSES == ("pending", "processing")


def test_r2_requires_scans_bucket():
    from plant_community_backend.r2_config import R2_REQUIRED_VARS

    assert "R2_SCANS_BUCKET_NAME" in R2_REQUIRED_VARS


def test_r2_scan_storage_is_private():
    with override_settings(
        USE_R2=True,
        R2_SCANS_BUCKET_NAME="scans-bucket",
        R2_BUCKET_NAME="media-bucket",
        R2_ACCESS_KEY_ID="k",
        R2_SECRET_ACCESS_KEY="s",  # pragma: allowlist secret
        R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
        R2_CUSTOM_DOMAIN="media.example.com",
    ):
        storage = scan_photo_storage()
    assert storage.querystring_auth is True
    assert not storage.custom_domain
    assert storage.bucket_name == "scans-bucket"
    assert storage.file_overwrite is False
    assert storage.object_parameters["CacheControl"] == "private, no-store"
