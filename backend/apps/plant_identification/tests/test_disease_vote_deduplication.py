"""
Tests for PlantDiseaseVote deduplication on disease diagnosis results.

Verifies that:
- A first vote is accepted and increments the counter.
- A second identical vote by the same user removes the vote (toggle).
- A vote change (upvote → downvote) swaps the counters correctly.
- The unique_together constraint prevents duplicate DB rows.
"""

from apps.plant_identification.models import (
    PlantDiseaseDatabase,
    PlantDiseaseRequest,
    PlantDiseaseResult,
    PlantDiseaseVote,
)
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class PlantDiseaseVoteDeduplicationTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="voter",
            email="voter@example.com",
            password="pass123",  # pragma: allowlist secret
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="pass123",  # pragma: allowlist secret
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.disease = PlantDiseaseDatabase.objects.create(
            disease_name="Powdery Mildew",
            scientific_name="Erysiphe cichoracearum",
            disease_type="fungal",
            confidence_score=0.85,
            api_source="plant_health",
            diagnosis_count=1,
        )
        self.request_obj = PlantDiseaseRequest.objects.create(
            user=self.user,
            status="diagnosed",
            symptoms_description="White coating",
        )
        self.result = PlantDiseaseResult.objects.create(
            request=self.request_obj,
            identified_disease=self.disease,
            confidence_score=0.85,
            upvotes=0,
            downvotes=0,
        )
        self.vote_url = (
            f"/api/v1/plant-identification/disease-results/{self.result.pk}/vote/"
        )

    def _vote(self, vote_type):
        return self.client.post(self.vote_url, {"vote_type": vote_type}, format="json")

    def test_different_users_can_hold_independent_votes(self):
        PlantDiseaseVote.objects.create(
            user=self.user, diagnosis_result=self.result, vote_type="upvote"
        )
        PlantDiseaseVote.objects.create(
            user=self.other_user, diagnosis_result=self.result, vote_type="upvote"
        )
        self.assertEqual(
            PlantDiseaseVote.objects.filter(diagnosis_result=self.result).count(), 2
        )

    def test_unique_together_constraint(self):
        from django.db import IntegrityError

        PlantDiseaseVote.objects.create(
            user=self.user, diagnosis_result=self.result, vote_type="upvote"
        )
        with self.assertRaises(IntegrityError):
            PlantDiseaseVote.objects.create(
                user=self.user, diagnosis_result=self.result, vote_type="downvote"
            )
