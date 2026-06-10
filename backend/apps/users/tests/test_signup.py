"""Tests for centralized signup side-effects (todo 221 / finding M7).

`create_default_plant_collection` is the single hook that standard registration,
OAuth, and Firebase token-exchange all call, so the default "My Plants"
collection no longer drifts between account-creation paths (it was previously
created by registration and OAuth but MISSING from the Firebase path). The
Firebase path is covered in `test_firebase_auth.py`; this file covers the shared
hook directly and the registration endpoint end to end.
"""

from apps.users.models import UserPlantCollection
from apps.users.signup import create_default_plant_collection
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status

User = get_user_model()


class CreateDefaultPlantCollectionTest(TestCase):
    """Unit tests for the shared signup-side-effect hook."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="signupuser",
            email="signup@example.com",
            password="pw-signup-221",  # pragma: allowlist secret
        )

    def test_creates_default_collection(self):
        collection = create_default_plant_collection(self.user)
        self.assertEqual(collection.name, "My Plants")
        self.assertEqual(collection.description, "My personal plant collection")
        self.assertTrue(collection.is_public)
        self.assertEqual(UserPlantCollection.objects.filter(user=self.user).count(), 1)

    def test_is_idempotent(self):
        first = create_default_plant_collection(self.user)
        second = create_default_plant_collection(self.user)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(UserPlantCollection.objects.filter(user=self.user).count(), 1)


class RegistrationSignupSideEffectTest(TestCase):
    """The register endpoint applies the shared default-collection side-effect."""

    def test_registration_creates_default_collection(self):
        csrf_token = self.client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        response = self.client.post(
            "/api/v1/auth/register/",
            data={
                "username": "newsignup",
                "email": "newsignup@example.com",
                "password": "TestPassword123!",  # pragma: allowlist secret
                "confirmPassword": "TestPassword123!",  # pragma: allowlist secret
            },
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="newsignup")
        collections = UserPlantCollection.objects.filter(user=user)
        self.assertEqual(collections.count(), 1)
        self.assertEqual(collections.first().name, "My Plants")
