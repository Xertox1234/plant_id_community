"""
API tests for the UserPlant list endpoint (todo 243).

The web "My Plants" page reads GET /api/v1/plant-identification/plants/. These
tests pin the contract that page depends on:

  - the list requires authentication,
  - it returns only the requesting user's plants (paginated),
  - the query count does not grow with the number of plants — the serializer
    reads user (StringRelatedField), species (nested), collection.name, and
    from_identification_request.request_id per row, which the viewset folds
    into the main SELECT via select_related.

The query assertion is relative O(1) (small N == large N), per
docs/patterns/performance/query-optimization.md, so it is immune to unrelated
base-query plumbing changes. Object counts stay below the page size (20) so
every plant lands on page 1.
"""

from apps.users.models import UserPlantCollection
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from ..models import PlantSpecies, UserPlant

User = get_user_model()


class UserPlantListAPITests(TestCase):
    """GET /api/v1/plant-identification/plants/ — the My Plants read surface."""

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("v1:plant_identification:plants-list")

        cls.owner = User.objects.create_user(
            username="plant_owner", email="owner@example.com", password="x" * 20
        )
        cls.other = User.objects.create_user(
            username="other_user", email="other@example.com", password="x" * 20
        )

        cls.owner_collection = UserPlantCollection.objects.create(
            user=cls.owner, name="My Plants"
        )
        cls.other_collection = UserPlantCollection.objects.create(
            user=cls.other, name="My Plants"
        )

        cls.species = PlantSpecies.objects.create(
            scientific_name="Rosa damascena", family="Rosaceae"
        )

        for i in range(2):
            UserPlant.objects.create(
                user=cls.owner,
                collection=cls.owner_collection,
                species=cls.species,
                nickname=f"Owner plant {i}",
            )
        UserPlant.objects.create(
            user=cls.other,
            collection=cls.other_collection,
            species=cls.species,
            nickname="Other user's plant",
        )

    def setUp(self):
        self.client = APIClient()

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_list_returns_only_own_plants(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        nicknames = {plant["nickname"] for plant in response.data["results"]}
        self.assertEqual(nicknames, {"Owner plant 0", "Owner plant 1"})

        # Contract fields the web My Plants page renders — removing/renaming
        # any of these breaks the page while both suites stay green otherwise.
        plant = response.data["results"][0]
        for field in (
            "display_name",
            "image_thumbnail",
            "collection_name",
            "care_instructions_json",
            "notes",
            "created_at",
        ):
            self.assertIn(field, plant)
        self.assertEqual(plant["collection_name"], "My Plants")

    def test_list_query_count_constant_in_plant_count(self):
        """Per-row serializer relations must not add queries per plant."""
        self.client.force_authenticate(user=self.owner)

        with CaptureQueriesContext(connection) as small:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        for i in range(3):
            UserPlant.objects.create(
                user=self.owner,
                collection=self.owner_collection,
                species=self.species,
                nickname=f"Extra plant {i}",
            )

        with CaptureQueriesContext(connection) as large:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 5)

        self.assertEqual(
            len(small.captured_queries),
            len(large.captured_queries),
            "Query count grew with plant count — per-row relation reads are "
            "not folded into the list query (missing select_related).",
        )
