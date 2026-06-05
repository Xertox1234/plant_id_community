"""Query-count regression for the plant_data_stats admin endpoint (audit L13).

The four separate PlantSpecies `.count()` calls were collapsed into a single
conditional `aggregate()`; pin the query count so the per-count expansion cannot
silently return.
"""

from apps.plant_identification.models import PlantSpecies
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PlantDataStatsQueryTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="stats_staff",
            email="s@test.com",
            password="testpass123",  # pragma: allowlist secret
            is_staff=True,
        )
        self.client.force_login(self.staff)
        # Mixed rows so the conditional aggregate has something to count: one
        # verified species with care data + image, two bare species.
        PlantSpecies.objects.create(
            scientific_name="Rosa damascena",
            is_verified=True,
            light_requirements="full_sun",
            water_requirements="moderate",
            primary_image="species/rose.jpg",
        )
        PlantSpecies.objects.create(scientific_name="Mentha spicata")
        PlantSpecies.objects.create(scientific_name="Ocimum basilicum")
        self.url = reverse("blog_api:plant_stats")

    def test_returns_200_with_correct_counts(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        stats = response.json()["stats"]
        self.assertEqual(stats["local_species_count"], 3)
        self.assertEqual(stats["verified_species_count"], 1)
        self.assertEqual(stats["species_with_care_data"], 1)
        self.assertEqual(stats["species_with_images"], 1)

    def test_query_count_does_not_scale_with_species(self):
        # Add more species; the count must stay constant — one PlantSpecies
        # aggregate + one PlantIdentificationRequest count, no per-metric query.
        for i in range(5):
            PlantSpecies.objects.create(scientific_name=f"Filler species {i}")
        with self.assertNumQueries(7):
            self.client.get(self.url)
