"""Tests for PATCH /api/v1/auth/user/update/ (``update_profile``).

Todo 404: ``email`` was writable on ``UserProfileSerializer``, so any session
could repoint an account's email with no re-auth and no verification. Email is
the lookup key for web OAuth, password login and the Firebase legacy fallback,
and it is not DB-unique, so a writable email let one account take another's
address. It is now read-only: DRF drops the key silently (200, email unchanged),
which is fine because no client sends it.
"""

from apps.users.serializers import UserProfileSerializer
from django.contrib.auth import get_user_model
from django.test import TestCase
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
