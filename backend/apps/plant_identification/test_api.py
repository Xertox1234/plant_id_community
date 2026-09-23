"""
API tests for plant identification endpoints.

This module tests the plant identification REST API endpoints including
authentication, plant identification workflow, disease diagnosis, and care instructions.
"""

import io
from unittest.mock import patch

import pytest
from apps.plant_identification.models import PlantDiseaseRequest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.mark.django_db
class TestDiseasesDiagnosisAPI(APITestCase):
    """Test disease diagnosis API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.diseased_image = self.create_diseased_image()

    def create_diseased_image(self):
        """Create a test image of diseased plant."""
        image = Image.new(
            "RGB", (300, 300), color="yellow"
        )  # Yellowish for diseased plant
        image_file = io.BytesIO()
        image.save(image_file, format="JPEG")
        image_file.seek(0)

        return SimpleUploadedFile(
            name="diseased_plant.jpg",
            content=image_file.read(),
            content_type="image/jpeg",
        )

    @pytest.mark.api
    @patch(
        "apps.plant_identification.services.disease_diagnosis_service.PlantDiseaseService.diagnose_disease_from_request"
    )
    def test_create_disease_diagnosis_request(self, mock_diagnose):
        """Test creating a disease diagnosis request."""
        # Prevent external API call and ensure no exceptions
        mock_diagnose.return_value = []
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:plant_identification:disease-requests-list")
        data = {
            "symptoms_description": "Yellow leaves with black spots",
            "image_1": self.diseased_image,
        }

        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify request was created
        self.assertEqual(PlantDiseaseRequest.objects.count(), 1)
        request = PlantDiseaseRequest.objects.first()
        self.assertEqual(request.user, self.user)

    @pytest.mark.api
    @patch(
        "apps.plant_identification.services.disease_diagnosis_service.PlantDiseaseService.diagnose_disease_from_request"
    )
    def test_create_response_returns_request_id_and_status(self, mock_diagnose):
        """POST create must return request_id + status so the client can fetch results."""
        mock_diagnose.return_value = []
        self.client.force_authenticate(user=self.user)
        url = reverse("v1:plant_identification:disease-requests-list")
        data = {
            "symptoms_description": "Yellow leaves with black spots",
            "image_1": self.create_diseased_image(),
        }

        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", response.data)
        self.assertTrue(response.data["request_id"])  # non-empty UUID
        self.assertIn("status", response.data)
        self.assertIn(
            response.data["status"],
            ["pending", "processing", "diagnosed", "needs_help", "failed"],
        )


@pytest.mark.django_db
class TestAPIAuthentication(APITestCase):
    """Test API authentication and permissions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @pytest.mark.api
    def test_jwt_authentication(self):
        """A bearer access token still authenticates (JWTAuthentication fallback)."""
        access_token = str(RefreshToken.for_user(self.user).access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        protected_url = reverse("v1:users:current_user")
        response = self.client.get(protected_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")

    @pytest.mark.api
    def test_token_refresh(self):
        """The users refresh endpoint exchanges a refresh token."""
        refresh_token = str(RefreshToken.for_user(self.user))

        refresh_url = reverse("v1:users:token_refresh")
        # View expects 'refresh' in request.data (or cookie)
        refresh_response = self.client.post(refresh_url, {"refresh": refresh_token})

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)

    @pytest.mark.api
    def test_simplejwt_password_grant_routes_are_gone(self):
        """Todo 405 slice 2: /api/auth/token/ was an unthrottled password grant
        that bypassed the login view's rate limit and account lockout. Nothing
        called it; it must stay removed."""
        for path in ("/api/auth/token/", "/api/auth/token/verify/"):
            response = self.client.post(
                path, {"username": "testuser", "password": "testpass123"}
            )
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, path)

    @pytest.mark.api
    def test_unauthorized_access_protection(self):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            reverse("v1:plant_identification:disease-requests-list"),
            reverse("v1:users:current_user"),
        ]

        for endpoint in protected_endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Endpoint {endpoint} should require authentication",
            )
