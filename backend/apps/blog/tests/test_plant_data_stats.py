"""Query-count regression for the plant_data_stats admin endpoint (audit L13).

The four separate PlantSpecies `.count()` calls were collapsed into a single
conditional `aggregate()`; pin the query count so the per-count expansion cannot
silently return.
"""

from apps.plant_identification.models import PlantIdentificationRequest, PlantSpecies
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
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
        # Add more species; the data-query count must stay constant — one
        # PlantSpecies conditional aggregate (audit L13) + one
        # PlantIdentificationRequest count, no per-metric query. We pin only the
        # queries against these two tables, not the total, so auth/session/
        # savepoint overhead (a Django/middleware upgrade) can't break a test
        # that guards the aggregate. A regression to four separate `.count()`
        # calls would add 3 species queries and fail this assertion.
        for i in range(5):
            PlantSpecies.objects.create(scientific_name=f"Filler species {i}")

        data_tables = (
            PlantSpecies._meta.db_table,
            PlantIdentificationRequest._meta.db_table,
        )
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)

        # Match the quoted identifier Django emits (`FROM "..._plantspecies"`),
        # not a bare substring: `plant_identification_plantspecies` is a prefix
        # of the Wagtail `plant_identification_plantspeciespage` table, so an
        # unquoted match could miscount a future PlantSpeciesPage query as a data
        # query and mask a regression. Both Postgres (CI) and SQLite double-quote
        # identifiers, so the trailing quote stops the over-match.
        data_queries = [
            q["sql"]
            for q in ctx.captured_queries
            if any(f'"{table}"' in q["sql"] for table in data_tables)
        ]
        self.assertEqual(
            len(data_queries),
            2,
            "plant_data_stats must hit each data table exactly once; per-metric "
            "expansion would add queries. Captured:\n" + "\n".join(data_queries),
        )
