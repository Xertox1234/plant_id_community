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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

User = get_user_model()

UPDATE_URL = "/api/v1/auth/user/update/"
ORIGINAL_EMAIL = "ada@example.com"
OTHER_EMAIL = "attacker@example.com"


class ProfileUpdateEmailTests(TestCase):
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

    def setUp(self):
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
        self.assertTrue(self.user.avatar.name.startswith("avatars/"))
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
