"""
Comprehensive tests for plant identification models.

This module tests the plant identification models including PlantSpecies,
PlantIdentificationRequest, PlantIdentificationResult, and related models.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from apps.plant_identification.models import (
    PlantSpecies, PlantIdentificationRequest, PlantIdentificationResult,
    PlantDiseaseRequest, PlantDiseaseResult, SavedCareInstructions
)
from apps.users.models import UserPlantCollection
import tempfile
from PIL import Image
import io

User = get_user_model()


@pytest.mark.django_db
class TestPlantSpeciesModel(TestCase):
    """Test cases for PlantSpecies model."""
    
    def setUp(self):
        """Set up test data."""
        self.plant_data = {
            'scientific_name': 'Rosa damascena',
            'common_names': 'Damask rose, Rose of Castile',
            'family': 'Rosaceae',
            'genus': 'Rosa',
            'description': 'A fragrant deciduous shrub',
        }
    
    @pytest.mark.unit
    def test_create_plant_species(self):
        """Test creating a new plant species."""
        plant = PlantSpecies.objects.create(**self.plant_data)
        
        self.assertEqual(plant.scientific_name, 'Rosa damascena')
        self.assertEqual(plant.family, 'Rosaceae')
        self.assertTrue(plant.uuid)  # UUID should be auto-generated
        self.assertEqual(str(plant), 'Rosa damascena')
    
    @pytest.mark.unit
    def test_scientific_name_uniqueness(self):
        """Test that scientific names must be unique."""
        PlantSpecies.objects.create(**self.plant_data)
        
        # Try to create another plant with the same scientific name
        with self.assertRaises(IntegrityError):
            PlantSpecies.objects.create(**self.plant_data)
    
    @pytest.mark.unit
    def test_common_names_parsing(self):
        """Test parsing of comma-separated common names."""
        plant = PlantSpecies.objects.create(**self.plant_data)
        
        # Assuming there's a method to get common names as list
        common_names = plant.common_names_list
        self.assertIn('Damask rose', common_names)
        self.assertIn('Rose of Castile', common_names)
    
    @pytest.mark.unit
    def test_plant_species_str_representation(self):
        """Test string representation of plant species."""
        plant = PlantSpecies.objects.create(**self.plant_data)
        self.assertEqual(str(plant), plant.scientific_name)


@pytest.mark.django_db
class TestPlantIdentificationRequest(TestCase):
    """Test cases for PlantIdentificationRequest model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test image
        self.test_image = self.create_test_image()
    
    def create_test_image(self):
        """Create a test image for upload."""
        image = Image.new('RGB', (100, 100), color='red')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='test_plant.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )
    
    @pytest.mark.unit
    def test_create_identification_request(self):
        """Test creating a plant identification request."""
        request = PlantIdentificationRequest.objects.create(
            user=self.user,
            image_1=self.test_image,
            location='Test Location',
            description='A beautiful flower in my garden'
        )
        
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.location, 'Test Location')
        self.assertEqual(request.status, 'pending')  # Default status
        self.assertTrue(request.request_id)
        self.assertTrue(request.created_at)
    
    @pytest.mark.unit
    def test_identification_request_status_choices(self):
        """Test that status field accepts valid choices."""
        request = PlantIdentificationRequest.objects.create(
            user=self.user,
            image_1=self.test_image,
            status='processing'
        )
        
        self.assertEqual(request.status, 'processing')
        
        # Test updating status
        request.status = 'identified'
        request.save()
        self.assertEqual(request.status, 'identified')


@pytest.mark.django_db
class TestPlantIdentificationResult(TestCase):
    """Test cases for PlantIdentificationResult model."""
    
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
        
        self.identification_request = PlantIdentificationRequest.objects.create(
            user=self.user,
            image_1=self.create_test_image(),
            location='Test Garden'
        )
    
    def create_test_image(self):
        """Create a test image for upload."""
        image = Image.new('RGB', (100, 100), color='green')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='test_plant.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )
    
    @pytest.mark.unit
    def test_create_identification_result(self):
        """Test creating an identification result."""
        result = PlantIdentificationResult.objects.create(
            request=self.identification_request,
            identified_species=self.plant_species,
            confidence_score=0.95,
            identification_source='ai_plantnet'
        )
        
        self.assertEqual(result.identified_species, self.plant_species)
        self.assertEqual(result.confidence_score, 0.95)
        self.assertEqual(result.identification_source, 'ai_plantnet')
        self.assertFalse(result.is_accepted)
    
    @pytest.mark.unit
    def test_confidence_score_validation(self):
        """Model currently does not enforce 0..1 range on confidence_score via validators."""
        # Ensure full_clean does not raise for values > 1.0 (no validator present)
        result = PlantIdentificationResult(
            request=self.identification_request,
            identified_species=self.plant_species,
            confidence_score=1.5,  # Out of nominal range, but allowed by model
            identification_source='ai_plantnet'
        )
        # Should not raise ValidationError
        result.full_clean()


@pytest.mark.django_db 
class TestPlantDiseaseModels(TestCase):
    """Test cases for disease diagnosis models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.disease_request = PlantDiseaseRequest.objects.create(
            user=self.user,
            symptoms_description='Yellow leaves with black spots',
            image_1=self.create_test_image()
        )
    
    def create_test_image(self):
        """Create a test image for disease diagnosis."""
        image = Image.new('RGB', (100, 100), color='yellow')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='diseased_plant.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )
    
    @pytest.mark.unit
    def test_create_disease_request(self):
        """Test creating a disease diagnosis request."""
        self.assertEqual(self.disease_request.user, self.user)
        self.assertEqual(self.disease_request.symptoms_description, 'Yellow leaves with black spots')
        self.assertEqual(self.disease_request.status, 'pending')
    
    @pytest.mark.unit 
    def test_disease_result_creation(self):
        """Test creating a disease diagnosis result."""
        result = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Black Spot',
            confidence_score=0.88,
            severity_assessment='moderate',
            diagnosis_source='api_plant_health'
        )
        
        self.assertEqual(result.suggested_disease_name, 'Black Spot')
        self.assertEqual(result.confidence_score, 0.88)
        self.assertEqual(result.severity_assessment, 'moderate')


@pytest.mark.django_db
class TestSavedCareInstructions(TestCase):
    """Test cases for SavedCareInstructions model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @pytest.mark.unit
    def test_create_saved_care_instructions(self):
        """Test creating saved care instructions."""
        care_instructions = SavedCareInstructions.objects.create(
            user=self.user,
            plant_scientific_name='Rosa damascena',
            care_instructions_data={
                'watering': 'Water deeply once a week',
                'light': 'Full sun to partial shade',
                'temperature': '15-25°C',
                'humidity': '40-60%'
            },
            personal_notes='My rose in the front garden',
            custom_nickname='Front Garden Rose',
            current_status='thriving'
        )
        
        self.assertEqual(care_instructions.user, self.user)
        self.assertEqual(care_instructions.plant_scientific_name, 'Rosa damascena')
        self.assertEqual(care_instructions.custom_nickname, 'Front Garden Rose')
        self.assertEqual(care_instructions.current_status, 'thriving')
        self.assertFalse(care_instructions.is_favorite)  # Default should be False
    
    @pytest.mark.unit
    def test_favorite_functionality(self):
        """Test favorite marking functionality."""
        care_instructions = SavedCareInstructions.objects.create(
            user=self.user,
            plant_scientific_name='Rosa damascena',
            care_instructions_data={},
            is_favorite=True
        )
        
        self.assertTrue(care_instructions.is_favorite)


@pytest.mark.django_db 
class TestModelRelationships(TestCase):
    """Test relationships between models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com', 
            password='testpass123'
        )
        
        self.plant_species = PlantSpecies.objects.create(
            scientific_name='Rosa damascena',
            family='Rosaceae'
        )
    
    @pytest.mark.integration
    def test_user_plant_collections(self):
        """Test user's plant collections relationship."""
        # Create user plant collection
        user_plant_collection = UserPlantCollection.objects.create(
            user=self.user,
            name='My Plant Collection',
            description='Beautiful fragrant rose collection'
        )
        
        # Test relationships
        self.assertEqual(user_plant_collection.user, self.user)
        self.assertEqual(user_plant_collection.name, 'My Plant Collection')
        
        # Test reverse relationships
        user_collections = self.user.plant_collections.all()
        self.assertEqual(user_collections.count(), 1)
        self.assertEqual(user_collections.first(), user_plant_collection)


@pytest.mark.django_db
class TestModelValidation(TestCase):
    """Test model validation and constraints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @pytest.mark.unit
    def test_required_fields_validation(self):
        """Test that required fields are properly validated."""
        # Test PlantSpecies without required scientific_name via model validation
        plant = PlantSpecies(
            family='Rosaceae'
            # Missing scientific_name
        )
        with self.assertRaises(ValidationError):
            plant.full_clean()
    
    @pytest.mark.unit 
    def test_choice_field_validation(self):
        """Test validation of choice fields."""
        # Assuming status has specific choices
        request = PlantIdentificationRequest(
            user=self.user,
            image_1=self.create_test_image(),
            status='invalid_status'  # Invalid choice
        )
        
        with self.assertRaises(ValidationError):
            request.full_clean()
    
    def create_test_image(self):
        """Create a test image."""
        image = Image.new('RGB', (100, 100), color='blue')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        
        return SimpleUploadedFile(
            name='test.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )


# Performance tests
@pytest.mark.django_db
class TestModelPerformance(TestCase):
    """Test model performance and database queries."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create multiple plant species for testing
        self.plant_species = []
        for i in range(10):
            plant = PlantSpecies.objects.create(
                scientific_name=f'Test plant {i}',
                family='Test Family',
                genus='Test'
            )
            self.plant_species.append(plant)
    
    @pytest.mark.slow
    def create_test_image(self, color='purple'):
        """Create a small JPEG test image."""
        image = Image.new('RGB', (50, 50), color=color)
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)
        return SimpleUploadedFile(
            name='perf_test.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )

    @pytest.mark.slow
    def test_bulk_operations(self):
        """Test creating multiple identification requests (avoid bulk_create with file fields)."""
        # Create multiple requests using regular create() to ensure files are processed
        for i in range(5):
            PlantIdentificationRequest.objects.create(
                user=self.user,
                image_1=self.create_test_image(),
                location=f'Location {i}',
                description=f'Description {i}'
            )

        total_requests = PlantIdentificationRequest.objects.filter(user=self.user).count()
        self.assertEqual(total_requests, 5)


@pytest.mark.django_db
class TestCascadeBehavior(TestCase):
    """
    Test cascade behavior for foreign keys according to CASCADE policy.

    CASCADE POLICY OVERVIEW:
    - User deletion: CASCADE (GDPR right to be forgotten)
    - PlantSpecies deletion: SET_NULL (preserve research/historical data)
    - Request deletion: CASCADE (results meaningless without request)
    - Collection deletion: CASCADE (plants belong to collection)
    """

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

        self.identification_request = PlantIdentificationRequest.objects.create(
            user=self.user,
            image_1=self.create_test_image(),
            location='Test Garden'
        )

    def create_test_image(self):
        """Create a test image for upload."""
        image = Image.new('RGB', (100, 100), color='green')
        image_file = io.BytesIO()
        image.save(image_file, format='JPEG')
        image_file.seek(0)

        return SimpleUploadedFile(
            name='test_plant.jpg',
            content=image_file.read(),
            content_type='image/jpeg'
        )

    @pytest.mark.unit
    def test_user_deletion_cascades_to_identification_requests(self):
        """Test that deleting a user cascades to their identification requests (GDPR)."""
        request_id = self.identification_request.id

        # Verify request exists
        self.assertTrue(PlantIdentificationRequest.objects.filter(id=request_id).exists())

        # Delete user
        self.user.delete()

        # Verify request was deleted (CASCADE)
        self.assertFalse(PlantIdentificationRequest.objects.filter(id=request_id).exists())

    @pytest.mark.unit
    def test_species_deletion_preserves_identification_results(self):
        """Test that deleting a species preserves identification results (SET_NULL for research data)."""
        # Create identification result linked to species
        result = PlantIdentificationResult.objects.create(
            request=self.identification_request,
            identified_species=self.plant_species,
            confidence_score=0.95,
            identification_source='ai_plantnet',
            suggested_scientific_name='Rosa damascena',
            suggested_common_name='Damask rose'
        )

        result_id = result.id

        # Delete the plant species
        self.plant_species.delete()

        # Reload result from database
        result.refresh_from_db()

        # Verify result still exists but species is NULL
        self.assertTrue(PlantIdentificationResult.objects.filter(id=result_id).exists())
        self.assertIsNone(result.identified_species)

        # Verify fallback data is preserved
        self.assertEqual(result.suggested_scientific_name, 'Rosa damascena')
        self.assertEqual(result.suggested_common_name, 'Damask rose')

    @pytest.mark.unit
    def test_species_deletion_preserves_user_plants(self):
        """Test that deleting a species preserves user's plant records (SET_NULL)."""
        from apps.plant_identification.models import UserPlant
        from apps.users.models import UserPlantCollection

        # Create collection and user plant
        collection = UserPlantCollection.objects.create(
            user=self.user,
            name='My Garden',
            description='Test collection'
        )

        user_plant = UserPlant.objects.create(
            user=self.user,
            collection=collection,
            species=self.plant_species,
            nickname='My Beautiful Rose',
            location_in_home='Front Garden'
        )

        plant_id = user_plant.id

        # Delete the plant species
        self.plant_species.delete()

        # Reload user plant from database
        user_plant.refresh_from_db()

        # Verify plant record still exists but species is NULL
        self.assertTrue(UserPlant.objects.filter(id=plant_id).exists())
        self.assertIsNone(user_plant.species)

        # Verify user's metadata is preserved
        self.assertEqual(user_plant.nickname, 'My Beautiful Rose')
        self.assertEqual(user_plant.location_in_home, 'Front Garden')

    @pytest.mark.unit
    def test_species_deletion_preserves_saved_care_instructions(self):
        """Test that deleting a species preserves saved care instructions (SET_NULL)."""
        care_card = SavedCareInstructions.objects.create(
            user=self.user,
            plant_species=self.plant_species,
            plant_scientific_name='Rosa damascena',
            plant_common_name='Damask rose',
            plant_family='Rosaceae',
            care_instructions_data={
                'watering': 'Water deeply once a week',
                'light': 'Full sun to partial shade'
            },
            personal_notes='My favorite rose care instructions'
        )

        card_id = care_card.id

        # Delete the plant species
        self.plant_species.delete()

        # Reload care card from database
        care_card.refresh_from_db()

        # Verify care card still exists but species is NULL
        self.assertTrue(SavedCareInstructions.objects.filter(id=card_id).exists())
        self.assertIsNone(care_card.plant_species)

        # Verify fallback data is preserved
        self.assertEqual(care_card.plant_scientific_name, 'Rosa damascena')
        self.assertEqual(care_card.plant_common_name, 'Damask rose')
        self.assertEqual(care_card.plant_family, 'Rosaceae')
        self.assertEqual(care_card.personal_notes, 'My favorite rose care instructions')

    @pytest.mark.unit
    def test_request_deletion_cascades_to_results(self):
        """Test that deleting a request cascades to its results (results meaningless without request)."""
        result = PlantIdentificationResult.objects.create(
            request=self.identification_request,
            identified_species=self.plant_species,
            confidence_score=0.95,
            identification_source='ai_plantnet'
        )

        result_id = result.id

        # Verify result exists
        self.assertTrue(PlantIdentificationResult.objects.filter(id=result_id).exists())

        # Delete request
        self.identification_request.delete()

        # Verify result was deleted (CASCADE)
        self.assertFalse(PlantIdentificationResult.objects.filter(id=result_id).exists())

    @pytest.mark.unit
    def test_user_deletion_cascades_to_care_instructions(self):
        """Test that deleting a user cascades to their saved care instructions (GDPR)."""
        care_card = SavedCareInstructions.objects.create(
            user=self.user,
            plant_scientific_name='Rosa damascena',
            care_instructions_data={}
        )

        card_id = care_card.id

        # Verify care card exists
        self.assertTrue(SavedCareInstructions.objects.filter(id=card_id).exists())

        # Delete user
        self.user.delete()

        # Verify care card was deleted (CASCADE)
        self.assertFalse(SavedCareInstructions.objects.filter(id=card_id).exists())

    @pytest.mark.unit
    def test_collection_deletion_cascades_to_user_plants(self):
        """Test that deleting a collection cascades to plants in that collection."""
        from apps.plant_identification.models import UserPlant
        from apps.users.models import UserPlantCollection

        collection = UserPlantCollection.objects.create(
            user=self.user,
            name='My Garden',
            description='Test collection'
        )

        user_plant = UserPlant.objects.create(
            user=self.user,
            collection=collection,
            species=self.plant_species,
            nickname='My Rose'
        )

        plant_id = user_plant.id

        # Verify plant exists
        self.assertTrue(UserPlant.objects.filter(id=plant_id).exists())

        # Delete collection
        collection.delete()

        # Verify plant was deleted (CASCADE - plants belong to collection)
        self.assertFalse(UserPlant.objects.filter(id=plant_id).exists())

    @pytest.mark.integration
    def test_multiple_results_species_deletion(self):
        """Test that deleting a species preserves ALL identification results that reference it."""
        # Create multiple requests and results for the same species
        results = []
        for i in range(3):
            request = PlantIdentificationRequest.objects.create(
                user=self.user,
                image_1=self.create_test_image(),
                location=f'Location {i}'
            )

            result = PlantIdentificationResult.objects.create(
                request=request,
                identified_species=self.plant_species,
                confidence_score=0.90 + (i * 0.01),
                identification_source='ai_plantnet',
                suggested_scientific_name='Rosa damascena'
            )
            results.append(result)

        # Delete the species
        self.plant_species.delete()

        # Verify all results still exist with NULL species
        for result in results:
            result.refresh_from_db()
            self.assertIsNone(result.identified_species)
            self.assertEqual(result.suggested_scientific_name, 'Rosa damascena')

    @pytest.mark.integration
    def test_cascade_policy_gdpr_compliance(self):
        """Test that user deletion removes all user data (GDPR right to be forgotten)."""
        from apps.plant_identification.models import UserPlant
        from apps.users.models import UserPlantCollection

        # Create various user data
        collection = UserPlantCollection.objects.create(
            user=self.user,
            name='My Garden'
        )

        user_plant = UserPlant.objects.create(
            user=self.user,
            collection=collection,
            species=self.plant_species
        )

        result = PlantIdentificationResult.objects.create(
            request=self.identification_request,
            identified_species=self.plant_species,
            confidence_score=0.95,
            identification_source='ai_plantnet'
        )

        care_card = SavedCareInstructions.objects.create(
            user=self.user,
            plant_scientific_name='Rosa damascena',
            care_instructions_data={}
        )

        # Store IDs
        request_id = self.identification_request.id
        result_id = result.id
        plant_id = user_plant.id
        collection_id = collection.id
        card_id = care_card.id

        # Delete user
        self.user.delete()

        # Verify all user data is deleted (GDPR compliance)
        self.assertFalse(PlantIdentificationRequest.objects.filter(id=request_id).exists())
        self.assertFalse(PlantIdentificationResult.objects.filter(id=result_id).exists())
        self.assertFalse(UserPlant.objects.filter(id=plant_id).exists())
        self.assertFalse(UserPlantCollection.objects.filter(id=collection_id).exists())
        self.assertFalse(SavedCareInstructions.objects.filter(id=card_id).exists())

        # But species should still exist (research data preservation)
        self.assertTrue(PlantSpecies.objects.filter(id=self.plant_species.id).exists())