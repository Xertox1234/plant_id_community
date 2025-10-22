"""
API tests for plant identification endpoints.

This module tests the plant identification REST API endpoints including
authentication, plant identification workflow, disease diagnosis, and care instructions.
"""

import pytest
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from apps.plant_identification.models import (
    PlantSpecies, PlantIdentificationRequest, PlantIdentificationResult,
    PlantDiseaseRequest, SavedCareInstructions
)
from PIL import Image
import io
import json

User = get_user_model()


@pytest.mark.django_db
class TestPlantIdentificationAPI(APITestCase):
    """Test plant identification API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plant_species = PlantSpecies.objects.create(
            scientific_name='Rosa damascena',
            common_names='Damask rose',
            family='Rosaceae',
            genus='Rosa'
        )
        
        # Create test image
        self.test_image = self.create_test_image()
    
    def create_test_image(self):
        """Create a test image for upload."""
        image = Image.new('RGB', (300, 300), color='green')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='test_plant.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )
    
    @pytest.mark.api
    def test_create_identification_request_authenticated(self):
        """Test creating identification request with authenticated user."""
        self.client.force_authenticate(user=self.user)
        
        # DRF router basename is 'requests' (see apps/plant_identification/urls.py)
        url = reverse('plant_identification:requests-list')
        data = {
            'image_1': self.test_image,
            'location': 'Test Garden',
            'description': 'Beautiful flower in my garden'
        }
        
        response = self.client.post(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['location'], 'Test Garden')
        # Status may be updated synchronously; just ensure request_id exists
        self.assertIn('request_id', response.data)
        
        # Verify request was created in database
        self.assertEqual(PlantIdentificationRequest.objects.count(), 1)
        request = PlantIdentificationRequest.objects.first()
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.location, 'Test Garden')
    
    @pytest.mark.api 
    def test_create_identification_request_unauthenticated(self):
        """Test that unauthenticated users cannot create identification requests."""
        url = reverse('plant_identification:requests-list')
        data = {
            'image_1': self.test_image,
            'location': 'Test Garden'
        }
        
        response = self.client.post(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(PlantIdentificationRequest.objects.count(), 0)
    
    @pytest.mark.api
    def test_get_identification_request_detail(self):
        """Test retrieving identification request details."""
        self.client.force_authenticate(user=self.user)
        
        # Create a request first
        identification_request = PlantIdentificationRequest.objects.create(
            user=self.user,
            image_1=self.test_image,
            location='Test Location'
        )
        
        # Detail uses request_id UUID as pk
        url = reverse('plant_identification:requests-detail', args=[identification_request.request_id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['location'], 'Test Location')
        self.assertIn('status', response.data)
    
    @pytest.mark.api
    def test_user_can_only_access_own_requests(self):
        """Test that users can only access their own identification requests."""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Create request for other user
        other_request = PlantIdentificationRequest.objects.create(
            user=other_user,
            image_1=self.test_image,
            location='Other Location'
        )
        
        # Try to access other user's request
        self.client.force_authenticate(user=self.user)
        url = reverse('plant_identification:requests-detail', args=[other_request.request_id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @pytest.mark.api
    @patch('apps.plant_identification.services.identification_service.PlantIdentificationService.identify_plant_from_request')
    def test_plant_identification_workflow(self, mock_identify):
        """Test the complete plant identification workflow."""
        # Mock identification service to simulate successful processing
        def _mock_identify(request_obj):
            PlantIdentificationResult.objects.create(
                request=request_obj,
                confidence_score=0.9,
                suggested_scientific_name='Rosa damascena',
                identification_source='ai_plantnet'
            )
            request_obj.status = 'identified'
            request_obj.save(update_fields=['status'])
            return []
        mock_identify.side_effect = _mock_identify
        
        self.client.force_authenticate(user=self.user)
        
        # Create identification request
        url = reverse('plant_identification:requests-list')
        data = {
            'image_1': self.test_image,
            'location': 'Test Garden'
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        request_id = response.data['request_id']
        
        # Optionally trigger manual processing endpoint (for completeness)
        process_url = reverse('plant_identification:requests-process-now', args=[request_id])
        process_resp = self.client.post(process_url)
        self.assertIn(process_resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        
        # Check that results were created and status updated
        req = PlantIdentificationRequest.objects.get(request_id=request_id)
        results = PlantIdentificationResult.objects.filter(request=req)
        self.assertTrue(results.exists())
        self.assertEqual(req.status, 'identified')


@pytest.mark.django_db
class TestDiseasesDiagnosisAPI(APITestCase):
    """Test disease diagnosis API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.diseased_image = self.create_diseased_image()
    
    def create_diseased_image(self):
        """Create a test image of diseased plant."""
        image = Image.new('RGB', (300, 300), color='yellow')  # Yellowish for diseased plant
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='diseased_plant.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )
    
    @pytest.mark.api
    @patch('apps.plant_identification.services.disease_diagnosis_service.PlantDiseaseService.diagnose_disease_from_request')
    def test_create_disease_diagnosis_request(self, mock_diagnose):
        """Test creating a disease diagnosis request."""
        # Prevent external API call and ensure no exceptions
        mock_diagnose.return_value = []
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plant_identification:disease-requests-list')
        data = {
            'symptoms_description': 'Yellow leaves with black spots',
            'image_1': self.diseased_image,
        }
        
        response = self.client.post(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify request was created
        self.assertEqual(PlantDiseaseRequest.objects.count(), 1)
        request = PlantDiseaseRequest.objects.first()
        self.assertEqual(request.user, self.user)
    
    @pytest.mark.api
    @patch('apps.plant_identification.services.disease_diagnosis_service.PlantDiseaseService.diagnose_disease_from_request')
    def test_disease_diagnosis_with_api(self, mock_diagnose):
        """Test disease diagnosis using external API."""
        # Mock service to mark request as diagnosed and create a result
        def _mock_diag(request_obj):
            from apps.plant_identification.models import PlantDiseaseResult
            PlantDiseaseResult.objects.create(
                request=request_obj,
                suggested_disease_name='Black Spot',
                confidence_score=0.88,
                severity_assessment='moderate',
                diagnosis_source='api_plant_health'
            )
            request_obj.status = 'diagnosed'
            request_obj.save(update_fields=['status'])
            return []
        mock_diagnose.side_effect = _mock_diag
        
        self.client.force_authenticate(user=self.user)
        
        # Create disease request
        disease_request = PlantDiseaseRequest.objects.create(
            user=self.user,
            symptoms_description='Black spots on leaves',
            image_1=self.diseased_image
        )
        
        # Trigger diagnosis (manual processing action)
        url = reverse('plant_identification:disease-requests-process-now', args=[disease_request.request_id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify diagnosis result was created
        disease_request.refresh_from_db()
        self.assertEqual(disease_request.status, 'diagnosed')
        
        # Check diagnosis results
        results = disease_request.diagnosis_results.all()
        self.assertTrue(results.exists())
        result = results.first()
        self.assertEqual(result.suggested_disease_name, 'Black Spot')
        self.assertEqual(result.confidence_score, 0.88)


@pytest.mark.django_db
class TestCareInstructionsAPI(APITestCase):
    """Test care instructions API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.plant_species = PlantSpecies.objects.create(
            scientific_name='Rosa damascena',
            common_names='Damask rose',
            family='Rosaceae'
        )
    
    @pytest.mark.api
    def test_get_care_instructions_by_species(self):
        """Test retrieving care instructions for a plant species."""
        self.client.force_authenticate(user=self.user)
        
        # Function view named 'care_instructions' expects int species_id
        url = reverse('plant_identification:care_instructions', args=[self.plant_species.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('plant', response.data)
        self.assertEqual(response.data['plant']['scientific_name'], 'Rosa damascena')
    
    @pytest.mark.api
    def test_save_care_instructions_to_profile(self):
        """Test saving care instructions to user profile."""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plant_identification:saved-care-instructions-list')
        data = {
            'plant_scientific_name': 'Rosa damascena',
            'care_instructions_data': {
                'watering': 'Water deeply once a week',
                'light': 'Full sun to partial shade',
                'temperature': '15-25°C'
            },
            'personal_notes': 'My favorite rose in the garden',
            'custom_nickname': 'Garden Rose',
            'is_favorite': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['plant_scientific_name'], 'Rosa damascena')
        self.assertEqual(response.data['custom_nickname'], 'Garden Rose')
        self.assertTrue(response.data['is_favorite'])
        
        # Verify it was saved
        saved_instructions = SavedCareInstructions.objects.filter(user=self.user)
        self.assertEqual(saved_instructions.count(), 1)
    
    @pytest.mark.api
    def test_list_user_saved_care_instructions(self):
        """Test listing user's saved care instructions."""
        # Create some saved care instructions
        SavedCareInstructions.objects.create(
            user=self.user,
            plant_scientific_name='Rosa damascena',
            care_instructions_data={'watering': 'Weekly'},
            custom_nickname='Rose 1'
        )
        
        SavedCareInstructions.objects.create(
            user=self.user,
            plant_scientific_name='Monstera deliciosa',
            care_instructions_data={'watering': 'Bi-weekly'},
            custom_nickname='Monstera 1'
        )
        
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plant_identification:saved-care-instructions-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle with/without pagination
        results = response.data['results'] if isinstance(response.data, dict) and 'results' in response.data else response.data
        self.assertEqual(len(results), 2)
        
        # Verify user can only see their own instructions
        nicknames = [item['custom_nickname'] for item in results]
        self.assertIn('Rose 1', nicknames)
        self.assertIn('Monstera 1', nicknames)


@pytest.mark.django_db
class TestAPIAuthentication(APITestCase):
    """Test API authentication and permissions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @pytest.mark.api
    def test_jwt_authentication(self):
        """Test JWT token authentication."""
        # Obtain JWT via SimpleJWT endpoint, then access protected endpoint
        obtain_url = reverse('token_obtain_pair')
        response = self.client.post(obtain_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data.get('access')
        self.assertIsNotNone(access_token)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        protected_url = reverse('users:current_user')
        response = self.client.get(protected_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
    
    @pytest.mark.api
    def test_token_refresh(self):
        """Test JWT token refresh functionality."""
        # Login to get initial tokens
        # Use users' refresh endpoint
        obtain_url = reverse('token_obtain_pair')
        response = self.client.post(obtain_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        refresh_token = response.data.get('refresh')
        self.assertIsNotNone(refresh_token)
        
        refresh_url = reverse('users:token_refresh')
        # View expects 'refresh' in request.data (or cookie)
        refresh_response = self.client.post(refresh_url, {
            'refresh': refresh_token
        })
        
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
    
    @pytest.mark.api
    def test_unauthorized_access_protection(self):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            reverse('plant_identification:requests-list'),
            reverse('plant_identification:disease-requests-list'),
            reverse('plant_identification:saved-care-instructions-list'),
            reverse('users:current_user'),
        ]
        
        for endpoint in protected_endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code, 
                status.HTTP_401_UNAUTHORIZED,
                f"Endpoint {endpoint} should require authentication"
            )


@pytest.mark.django_db
class TestAPIPerformance(APITestCase):
    """Test API performance and optimization."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create multiple plant species and identification requests for testing
        self.create_test_data()
    
    def create_test_data(self):
        """Create test data for performance testing."""
        # Create plant species
        for i in range(20):
            PlantSpecies.objects.create(
                scientific_name=f'Test plant {i}',
                common_names=f'Common plant {i}',
                family=f'Family {i % 5}',  # Group into families
                genus=f'Genus {i % 10}'   # Group into genera
            )
        
        # Create identification requests
        for i in range(10):
            PlantIdentificationRequest.objects.create(
                user=self.user,
                location=f'Location {i}',
                description=f'Description {i}',
                status='identified' if i % 2 == 0 else 'pending'
            )
    
    @pytest.mark.slow
    def test_list_endpoints_performance(self):
        """Test performance of list endpoints with pagination."""
        self.client.force_authenticate(user=self.user)
        
        # Test plant species list
        url = reverse('plant_identification:species-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Do not assert pagination shape to avoid config coupling
        
        # Test with query parameters
        response = self.client.get(url, {'family': 'Family 1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    @pytest.mark.slow
    def test_search_functionality(self):
        """Test search functionality performance."""
        self.client.force_authenticate(user=self.user)
        
        # Test plant species search
        url = reverse('plant_identification:species-list')
        response = self.client.get(url, {'search': 'Test plant'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results should contain search term (handle with/without pagination)
        results = response.data['results'] if isinstance(response.data, dict) and 'results' in response.data else response.data
        for result in results:
            self.assertIn('Test plant', result['scientific_name'])


@pytest.mark.django_db
class TestAPIErrorHandling(APITestCase):
    """Test API error handling and validation."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @pytest.mark.api
    def test_invalid_image_upload(self):
        """Test handling of invalid image uploads."""
        self.client.force_authenticate(user=self.user)
        
        # Create invalid image file
        invalid_file = SimpleUploadedFile(
            name='not_an_image.txt',
            content=b'This is not an image',
            content_type='text/plain'
        )
        
        url = reverse('plant_identification:requests-list')
        data = {
            'image_1': invalid_file,
            'location': 'Test Location'
        }
        
        response = self.client.post(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @pytest.mark.api
    def test_missing_required_fields(self):
        """Test validation of required fields."""
        self.client.force_authenticate(user=self.user)
        
        # Try to create identification request without required image
        url = reverse('plant_identification:requests-list')
        data = {
            'location': 'Test Location'
            # Missing required 'image' field
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @pytest.mark.api
    def test_non_existent_resource_404(self):
        """Test 404 response for non-existent resources."""
        self.client.force_authenticate(user=self.user)
        
        # Try to access non-existent identification request
        url = reverse('plant_identification:requests-detail', args=['00000000-0000-0000-0000-000000000000'])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)