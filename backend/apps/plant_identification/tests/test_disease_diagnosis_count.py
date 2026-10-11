"""
`PlantDiseaseDatabase.diagnosis_count` must not lose increments (todo 467).

Two diagnoses of the same disease that overlap each read the row, then each
write back what they read plus one. With `count += 1` in Python the second
write overwrites the first and one diagnosis is never counted. The increment
has to happen in the database (`F("diagnosis_count") + 1`).

The overlap is reproduced deterministically: two instances of the same row are
loaded before either update runs, which is exactly the state two concurrent
requests are in.
"""

from apps.plant_identification.models import (
    PlantDiseaseDatabase,
    PlantDiseaseRequest,
    PlantDiseaseResult,
)
from apps.plant_identification.services.disease_diagnosis_service import (
    DiseaseAutostorageService,
)
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class DiagnosisCountIncrementTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="countuser", email="count@example.com")
        self.disease = PlantDiseaseDatabase.objects.create(
            disease_name="Powdery Mildew",
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
        )
        request = PlantDiseaseRequest.objects.create(
            user=user,
            status="diagnosed",
            symptoms_description="White powdery coating on leaves",
        )
        self.result = PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name="Powdery Mildew",
            suggested_disease_type="fungal",
            confidence_score=0.7,
            diagnosis_source="api_plant_health",
        )
        self.service = DiseaseAutostorageService()

    def test_overlapping_updates_both_count(self):
        # Both "requests" read the row before either writes.
        first = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)
        second = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)

        self.service._update_existing_disease(first, self.result)
        self.service._update_existing_disease(second, self.result)

        self.disease.refresh_from_db()
        # 1 initial + 2 diagnoses. The read-modify-write version gives 2.
        self.assertEqual(self.disease.diagnosis_count, 3)

    def test_returned_instance_holds_the_stored_integer(self):
        updated = self.service._update_existing_disease(
            PlantDiseaseDatabase.objects.get(pk=self.disease.pk), self.result
        )
        # Not an unevaluated F() expression: callers log and serialize it.
        self.assertIsInstance(updated.diagnosis_count, int)
        self.assertEqual(updated.diagnosis_count, 2)

    def test_store_disease_if_qualified_increments_existing(self):
        stored = self.service.store_disease_if_qualified(self.result)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.pk, self.disease.pk)
        self.disease.refresh_from_db()
        self.assertEqual(self.disease.diagnosis_count, 2)
