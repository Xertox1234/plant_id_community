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
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

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


class DiagnosisMergeStaleInstanceTest(TestCase):
    """Confidence and symptoms must not be lost to a stale instance (todo 568).

    `diagnosis_count` was made atomic in todo 467, but the full-row save()
    still wrote back confidence_score and symptoms from the copy each request
    had read. The overlap is reproduced as above: both copies are loaded
    before either update runs.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="mergeuser", email="merge@example.com"
        )
        self.disease = PlantDiseaseDatabase.objects.create(
            disease_name="Leaf Spot",
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
            symptoms={"identified": ["brown spots"]},
        )
        self.service = DiseaseAutostorageService()

    def _result(self, confidence, symptoms):
        request = PlantDiseaseRequest.objects.create(
            user=self.user,
            status="diagnosed",
            symptoms_description="Spots on leaves",
        )
        return PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name="Leaf Spot",
            suggested_disease_type="fungal",
            confidence_score=confidence,
            symptoms_identified=symptoms,
            diagnosis_source="api_plant_health",
        )

    def test_overlapping_updates_keep_both_symptoms_and_higher_confidence(self):
        high = self._result(0.9, ["yellow halo"])
        low = self._result(0.7, ["leaf drop"])
        first = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)
        second = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)

        self.service._update_existing_disease(first, high)
        self.service._update_existing_disease(second, low)

        self.disease.refresh_from_db()
        # The stale-copy version gives 0.7 and drops "yellow halo".
        self.assertEqual(self.disease.confidence_score, 0.9)
        self.assertEqual(
            sorted(self.disease.symptoms["identified"]),
            ["brown spots", "leaf drop", "yellow halo"],
        )
        self.assertEqual(self.disease.diagnosis_count, 3)

    def test_update_writes_only_the_merged_fields(self):
        stale = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)
        PlantDiseaseDatabase.objects.filter(pk=self.disease.pk).update(
            description="Edited by a moderator"
        )

        self.service._update_existing_disease(stale, self._result(0.8, []))

        self.disease.refresh_from_db()
        self.assertEqual(self.disease.description, "Edited by a moderator")

    def test_store_disease_if_qualified_locks_the_existing_row(self):
        result = self._result(0.8, ["wilting"])

        with CaptureQueriesContext(connection) as ctx:
            stored = self.service.store_disease_if_qualified(result)

        self.assertEqual(stored.pk, self.disease.pk)
        lookups = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].lstrip().upper().startswith("SELECT")
            and PlantDiseaseDatabase._meta.db_table in q["sql"]
            and "FOR UPDATE" in q["sql"].upper()
        ]
        # The name lookup and the merge re-read both take the row lock.
        self.assertGreaterEqual(len(lookups), 2, ctx.captured_queries)
