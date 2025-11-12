"""
Test CASCADE behavior for PlantDiseaseResult.identified_disease field.

This test verifies that deleting a disease from PlantDiseaseDatabase
does NOT cascade delete historical diagnosis results (Issue #002).
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.plant_identification.models import (
    PlantDiseaseDatabase,
    PlantDiseaseRequest,
    PlantDiseaseResult,
)

User = get_user_model()


class DiseaseCascadeBehaviorTest(TestCase):
    """Test that deleting diseases preserves historical diagnosis data."""

    def setUp(self):
        """Create test user, disease, and diagnosis result."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create a disease entry
        self.disease = PlantDiseaseDatabase.objects.create(
            disease_name='Powdery Mildew',
            scientific_name='Erysiphe cichoracearum',
            disease_type='fungal',
            confidence_score=0.85,
            api_source='plant_health',
            diagnosis_count=1
        )

        # Create a diagnosis request
        self.request = PlantDiseaseRequest.objects.create(
            user=self.user,
            status='diagnosed',
            symptoms_description='White powdery coating on leaves'
        )

        # Create a diagnosis result linked to the disease
        self.result = PlantDiseaseResult.objects.create(
            request=self.request,
            identified_disease=self.disease,
            suggested_disease_name='Powdery Mildew',
            suggested_disease_type='fungal',
            confidence_score=0.85,
            diagnosis_source='api_plant_health'
        )

    def test_deleting_disease_preserves_diagnosis_result(self):
        """
        Verify that deleting a disease from PlantDiseaseDatabase
        does NOT delete the diagnosis result (SET_NULL behavior).
        """
        result_id = self.result.id
        disease_name = self.disease.disease_name

        # Delete the disease
        self.disease.delete()

        # Verify the diagnosis result still exists
        result = PlantDiseaseResult.objects.get(id=result_id)
        self.assertIsNotNone(result, "Diagnosis result should still exist")

        # Verify the foreign key is now NULL
        self.assertIsNone(
            result.identified_disease,
            "identified_disease field should be NULL after disease deletion"
        )

        # Verify fallback fields still have data
        self.assertEqual(
            result.suggested_disease_name,
            disease_name,
            "suggested_disease_name should preserve original disease name"
        )
        self.assertEqual(
            result.suggested_disease_type,
            'fungal',
            "suggested_disease_type should preserve original disease type"
        )

        # Verify confidence score and other metadata is intact
        self.assertEqual(result.confidence_score, 0.85)
        self.assertEqual(result.diagnosis_source, 'api_plant_health')

    def test_disease_deletion_does_not_cascade_to_multiple_results(self):
        """
        Verify that deleting a disease with multiple diagnosis results
        preserves ALL historical results.
        """
        # Create additional diagnosis results for the same disease
        request2 = PlantDiseaseRequest.objects.create(
            user=self.user,
            status='diagnosed',
            symptoms_description='Second diagnosis'
        )
        result2 = PlantDiseaseResult.objects.create(
            request=request2,
            identified_disease=self.disease,
            suggested_disease_name='Powdery Mildew',
            suggested_disease_type='fungal',
            confidence_score=0.92,
            diagnosis_source='api_plant_health'
        )

        request3 = PlantDiseaseRequest.objects.create(
            user=self.user,
            status='diagnosed',
            symptoms_description='Third diagnosis'
        )
        result3 = PlantDiseaseResult.objects.create(
            request=request3,
            identified_disease=self.disease,
            suggested_disease_name='Powdery Mildew',
            suggested_disease_type='fungal',
            confidence_score=0.78,
            diagnosis_source='api_plant_health'
        )

        # Verify we have 3 results
        self.assertEqual(PlantDiseaseResult.objects.count(), 3)

        # Delete the disease
        self.disease.delete()

        # Verify all 3 diagnosis results still exist
        self.assertEqual(
            PlantDiseaseResult.objects.count(),
            3,
            "All 3 diagnosis results should still exist after disease deletion"
        )

        # Verify all identified_disease fields are now NULL
        for result in PlantDiseaseResult.objects.all():
            self.assertIsNone(
                result.identified_disease,
                f"Result {result.id} should have NULL identified_disease"
            )
            self.assertEqual(result.suggested_disease_name, 'Powdery Mildew')

    def test_deleting_request_still_cascades_to_results(self):
        """
        Verify that deleting a diagnosis request DOES cascade delete
        its results (diagnosis results are meaningless without the request).
        """
        result_id = self.result.id

        # Delete the request
        self.request.delete()

        # Verify the diagnosis result was deleted
        self.assertFalse(
            PlantDiseaseResult.objects.filter(id=result_id).exists(),
            "Diagnosis result should be deleted when request is deleted"
        )

        # Verify the disease was NOT deleted
        self.assertTrue(
            PlantDiseaseDatabase.objects.filter(id=self.disease.id).exists(),
            "Disease should NOT be deleted when request is deleted"
        )

    def test_display_name_fallback_after_disease_deletion(self):
        """
        Verify that display_name property works correctly after disease deletion.
        """
        # Before deletion - should use disease's display name
        original_display_name = self.result.display_name
        self.assertEqual(original_display_name, 'Powdery Mildew (Erysiphe cichoracearum)')

        # Delete the disease
        self.disease.delete()

        # Refresh the result from database
        self.result.refresh_from_db()

        # After deletion - should use suggested_disease_name
        fallback_display_name = self.result.display_name
        self.assertEqual(
            fallback_display_name,
            'Powdery Mildew',
            "display_name should fall back to suggested_disease_name"
        )
