"""Serializer regression tests (todo 092).

`TreatmentAttemptSerializer.Meta.fields` previously listed ~12 fields that do not
exist on the `TreatmentAttempt` model (`uuid`, `user`, `start_date`, `completed`,
`effectiveness`, `notes`, ...). DRF's `ModelSerializer` builds its field set
lazily on first access to `.data`/`.fields`, and a field naming a non-existent
model attribute raises `ImproperlyConfigured` at that point. That aborted
OpenAPI schema generation (`/api/schema`, `/api/docs`) and 500'd the
treatment-attempts endpoint at runtime. This test pins the serializer to the
real model fields.

The serializer is exercised with in-memory model instances rather than a
persisted fixture: the `ImproperlyConfigured` failure occurs while *building*
the serializer fields, independent of whether the row exists, and the corrected
`source=` traversals (`saved_diagnosis.user.username`, `treatment.treatment_name`)
resolve against the directly-assigned related instances. These are real model
objects (not mocks); the full DB chain (User -> PlantDiseaseRequest ->
PlantDiseaseResult -> SavedDiagnosis, plus PlantDiseaseDatabase ->
DiseaseCareInstructions, including a FileField) is disproportionate for verifying
serializer field correctness and is exercised elsewhere in the app's suite.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import DiseaseCareInstructions, SavedDiagnosis, TreatmentAttempt
from ..serializers import TreatmentAttemptSerializer

User = get_user_model()


class TreatmentAttemptSerializerTest(TestCase):
    def test_treatment_attempt_serializer_data_builds_with_real_model_fields(self):
        """`.data` must build without raising and expose the corrected field set.

        Regression: before todo 092 this raised
        ``ImproperlyConfigured: Field name 'uuid' is not valid for model
        'TreatmentAttempt'`` while building the serializer fields.
        """
        user = User(username="treatmenttester")
        saved_diagnosis = SavedDiagnosis(user=user)
        treatment = DiseaseCareInstructions(treatment_name="Neem oil spray")
        attempt = TreatmentAttempt(
            saved_diagnosis=saved_diagnosis,
            treatment=treatment,
            started_date=date(2026, 5, 21),
            effectiveness_rating=4,
            success=True,
            user_notes="Worked well.",
            side_effects="Minor leaf burn.",
        )

        data = TreatmentAttemptSerializer(attempt).data

        self.assertIsInstance(data, dict)
        # Derived source-traversal fields resolve against the real relations.
        self.assertEqual(data["username"], "treatmenttester")
        self.assertEqual(data["treatment_name"], "Neem oil spray")
        # A representative concrete model field round-trips.
        self.assertEqual(data["effectiveness_rating"], 4)
        # None of the removed phantom fields leak into the output.
        for phantom in (
            "uuid",
            "user",
            "start_date",
            "completed",
            "effectiveness",
            "notes",
        ):
            self.assertNotIn(phantom, data)
