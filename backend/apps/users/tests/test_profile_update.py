"""Tests for PATCH /api/v1/auth/user/update/ (``update_profile``).

Todo 404: ``email`` was writable on ``UserProfileSerializer``, so any session
could repoint an account's email with no re-auth and no verification. Email is
the lookup key for web OAuth, password login and the Firebase legacy fallback,
and it is not DB-unique, so a writable email let one account take another's
address. It is now read-only: DRF drops the key silently (200, email unchanged),
which is fine because no client sends it.
"""

import io
import tempfile
from unittest.mock import PropertyMock, patch

from apps.users.serializers import UserProfileSerializer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

User = get_user_model()


def _avatar_name(user) -> str:
    """The stored avatar's name; the field types it Optional until a file is saved."""
    name: str | None = user.avatar.name
    assert name is not None, "no avatar stored"
    return name


UPDATE_URL = "/api/v1/auth/user/update/"
ORIGINAL_EMAIL = "ada@example.com"
OTHER_EMAIL = "attacker@example.com"


class ProfileUpdateEmailTests(TestCase):
    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="ada",
            email=ORIGINAL_EMAIL,
            password="TestPass123!",  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.user)

    def test_patch_with_email_leaves_stored_email_unchanged(self):
        resp = self.client.patch(UPDATE_URL, {"email": OTHER_EMAIL}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, ORIGINAL_EMAIL)
        self.assertEqual(resp.data["user"]["email"], ORIGINAL_EMAIL)

    def test_email_alongside_profile_fields_updates_only_the_profile(self):
        # The shape a real client sends: profile fields, plus a stray email.
        resp = self.client.patch(
            UPDATE_URL, {"bio": "Fern person", "email": OTHER_EMAIL}, format="json"
        )

        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Fern person")
        self.assertEqual(self.user.email, ORIGINAL_EMAIL)

    def test_email_is_still_returned(self):
        # Mobile and web both read `email` from the response; read-only must
        # not remove it.
        resp = self.client.patch(UPDATE_URL, {"bio": "x"}, format="json")

        self.assertEqual(resp.data["user"]["email"], ORIGINAL_EMAIL)

    def test_email_field_is_read_only(self):
        self.assertTrue(UserProfileSerializer().fields["email"].read_only)


def _png(name="me.png", size=(64, 64)):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 120, 60)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class ProfileBioAndAvatarTests(TestCase):
    """What the mobile edit-profile screen sends (todo 455): a JSON bio, and
    the avatar as a multipart PATCH to the same endpoint."""

    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        cache.clear()  # the per-user profile throttle counts in the cache
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="bo", password="TestPass123!"  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.user)
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_a_bio_is_saved(self):
        resp = self.client.patch(UPDATE_URL, {"bio": "Grows ferns."}, format="json")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Grows ferns.")
        self.assertEqual(resp.data["user"]["bio"], "Grows ferns.")

    def test_a_multipart_avatar_is_saved_and_returned_as_absolute_urls(self):
        resp = self.client.patch(UPDATE_URL, {"avatar": _png()}, format="multipart")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertTrue(_avatar_name(self.user).startswith("avatars/"))
        # Absolute, so the app can load it; and the thumbnail is filled.
        self.assertTrue(resp.data["user"]["avatar"].startswith("http"))
        self.assertTrue(resp.data["user"]["avatar_thumbnail"].startswith("http"))

        fetched = self.client.get("/api/v1/auth/user/")
        self.assertTrue(fetched.data["avatar"].startswith("http"))

    def test_a_non_image_avatar_is_refused(self):
        bogus = SimpleUploadedFile("me.png", b"not an image", content_type="image/png")

        resp = self.client.patch(UPDATE_URL, {"avatar": bogus}, format="multipart")

        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_a_thumbnail_that_cannot_be_generated_does_not_500_the_profile(self):
        # The thumbnail is generated on first access; its source can be gone
        # (a wiped volume, a deleted object) or unreadable.
        self.client.patch(UPDATE_URL, {"avatar": _png()}, format="multipart")

        with patch(
            "imagekit.cachefiles.ImageCacheFile.url",
            new_callable=PropertyMock,
            side_effect=FileNotFoundError("gone"),
        ):
            resp = self.client.get("/api/v1/auth/user/")

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["avatar_thumbnail"])
        self.assertTrue(resp.data["avatar"].startswith("http"))


def _jpeg_with_metadata(size=(80, 60)):
    """A JPEG carrying EXIF a phone writes: a camera make, GPS, and an
    orientation that says "rotate 90 degrees" (6)."""
    exif = Image.Exif()
    exif[0x010F] = "SpyCamMaker"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90 CW to display
    exif[0x8825] = {1: "N", 2: (51.0, 30.0, 26.0)}  # GPSInfo
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


class AvatarStorageHygieneTests(TestCase):
    """Todo 565, owner decisions 2026-10-11: findings 1, 2, 4, 6 and 9."""

    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="cy", password="TestPass123!"  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.user)
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)

    def _upload(self, upload=None):
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(
                UPDATE_URL, {"avatar": upload or _png()}, format="multipart"
            )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        return resp

    def _stored_files(self):
        # The original and its thumbnail, generated as a GET would.
        self.client.get("/api/v1/auth/user/")
        self.user.refresh_from_db()
        names = [self.user.avatar.name, self.user.avatar_thumbnail.name]
        for name in names:
            self.assertTrue(default_storage.exists(name), name)
        return names

    def test_a_refused_avatar_is_the_error_envelope_with_a_message(self):
        # Finding 1: mobile reads only message/detail/error.
        bogus = SimpleUploadedFile("me.png", b"not an image", content_type="image/png")

        resp = self.client.patch(UPDATE_URL, {"avatar": bogus}, format="multipart")

        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp.data["message"].startswith("avatar: "), resp.data)
        self.assertIn("avatar", resp.data["errors"])

    def test_replacing_the_avatar_deletes_the_old_photo_and_thumbnail(self):
        # Finding 2: ImageField never deletes a file it stops pointing at.
        self._upload()
        old = self._stored_files()

        self._upload(_png(name="new.png"))

        for name in old:
            self.assertFalse(default_storage.exists(name), name)
        self.assertTrue(default_storage.exists(_avatar_name(self.user)))

    def test_a_bio_only_update_keeps_the_avatar(self):
        self._upload()
        old = self._stored_files()

        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(UPDATE_URL, {"bio": "Ferns."}, format="json")

        for name in old:
            self.assertTrue(default_storage.exists(name), name)

    def test_the_stored_avatar_has_no_metadata_and_keeps_its_orientation(self):
        # Finding 6: EXIF, GPS included, is dropped; the orientation it
        # carried is applied first, so the photo is not stored sideways.
        original = _jpeg_with_metadata()
        self.assertIn(b"SpyCamMaker", original)

        self._upload(SimpleUploadedFile("me.jpg", original, content_type="image/jpeg"))

        with default_storage.open(_avatar_name(self.user), "rb") as stored:
            data = stored.read()
        self.assertNotIn(b"SpyCamMaker", data)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(dict(image.getexif()), {})
            self.assertEqual(image.size, (60, 80))  # rotated upright

    def test_a_multi_picture_phone_jpeg_is_stored_as_a_jpeg(self):
        # PR #1028 review: Pillow reports a JPEG with extra frames as MPO; it
        # fell through to PNG and grew past the 2 MB cap.
        buf = io.BytesIO()
        frames = [Image.new("RGB", (80, 60), c) for c in ((10, 120, 40), (90, 0, 0))]
        frames[0].save(buf, format="MPO", save_all=True, append_images=frames[1:])
        with Image.open(io.BytesIO(buf.getvalue())) as probe:
            self.assertEqual(probe.format, "MPO")

        self._upload(
            SimpleUploadedFile("me.jpg", buf.getvalue(), content_type="image/jpeg")
        )

        self.assertTrue(
            _avatar_name(self.user).endswith(".jpg"), _avatar_name(self.user)
        )
        with default_storage.open(_avatar_name(self.user), "rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.format, "JPEG")

    def test_a_photo_too_large_once_re_encoded_is_refused(self):
        # The size cap is re-checked on what is stored, not only on the upload.
        with patch("apps.users.avatars.MAX_AVATAR_SIZE", 64):
            resp = self.client.patch(UPDATE_URL, {"avatar": _png()}, format="multipart")

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("once its metadata is removed", resp.data["message"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_pixels_that_do_not_decode_are_a_400_not_a_500(self):
        # The upload validators read the header only; a truncated body used to
        # raise OSError out of the re-encode.
        from apps.users.avatars import AvatarUnreadableError, strip_image_metadata

        whole = _jpeg_with_metadata(size=(400, 300))
        truncated = SimpleUploadedFile(
            "me.jpg", whole[: len(whole) // 2], content_type="image/jpeg"
        )
        with self.assertRaises(AvatarUnreadableError):
            strip_image_metadata(truncated)

        resp = self.client.patch(UPDATE_URL, {"avatar": truncated}, format="multipart")

        self.assertEqual(resp.status_code, 400, resp.data)

    def test_profile_updates_are_throttled_per_user(self):
        from apps.plant_identification.constants import RATE_LIMITS

        limit = int(RATE_LIMITS["user_features"]["profile_updates"].split("/")[0])
        for _ in range(limit):
            self.assertEqual(
                self.client.patch(UPDATE_URL, {"bio": "x"}, format="json").status_code,
                200,
            )

        resp = self.client.patch(UPDATE_URL, {"bio": "x"}, format="json")

        self.assertEqual(resp.status_code, 429)
        self.assertIn("Retry-After", resp)

    def test_a_thumbnail_failure_is_logged_with_its_traceback(self):
        # Finding 4: the null-thumbnail fallback stays, but a storage or
        # config fault is no longer reduced to a bare exception type.
        self._upload()

        with patch(
            "imagekit.cachefiles.ImageCacheFile.url",
            new_callable=PropertyMock,
            side_effect=PermissionError("storage refused"),
        ), self.assertLogs("apps.users.serializers", level="ERROR") as logs:
            resp = self.client.get("/api/v1/auth/user/")

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["avatar_thumbnail"])
        exc_info = logs.records[0].exc_info
        assert exc_info is not None  # narrows the Optional for mypy
        self.assertIs(exc_info[0], PermissionError)

    def test_removing_the_avatar_deletes_its_files(self):
        # Finding 9: a route to remove the photo, not only replace it.
        self._upload()
        old = self._stored_files()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.delete("/api/v1/auth/user/avatar/")

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["user"]["avatar"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        for name in old:
            self.assertFalse(default_storage.exists(name), name)

    def test_removing_with_no_avatar_is_a_no_op(self):
        resp = self.client.delete("/api/v1/auth/user/avatar/")

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["user"]["avatar"])

    def test_removing_needs_a_signed_in_user(self):
        resp = APIClient().delete("/api/v1/auth/user/avatar/")

        self.assertEqual(resp.status_code, 401)
