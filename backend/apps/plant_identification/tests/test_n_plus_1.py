"""
N+1 query regression tests for the plant_identification API list endpoints
(todo 079).

Four plant_identification list endpoints serialize a count field on every row
(``results_count`` / ``affected_plant_count`` / ``plant_count``). The naive
implementation issued one ``SELECT COUNT(*)`` query per serialized object (an
N+1 pattern): the query count grew linearly with the number of objects on the
page. The fix annotates the counts on the queryset so the serializers read an
annotation (``hasattr(obj, "_results_count")`` etc.) instead of issuing a
COUNT:

  - ``serializers.py`` — ``get_results_count`` reads ``_results_count``;
    ``get_affected_plant_count`` reads ``_affected_plant_count``.
  - ``api/serializers.py`` — ``PlantCategorySerializer.get_plant_count`` reads
    ``_plant_count``.
  - ``views.py`` viewsets annotate ``_results_count`` /
    ``_affected_plant_count``; ``api/endpoints.py`` annotates ``_plant_count``.

These tests prove the fix holds by counting only the ``SELECT COUNT(...)``
queries issued while serving each endpoint, with a SMALL fixture set and then
again with a larger one. The per-row COUNT the naive code issued (one
``SELECT COUNT(*)`` per serialized row for the count field) is exactly that
shape; the annotated fix folds the count into the main SELECT and issues no
extra COUNT query. If the COUNT-query total is EQUAL across the small and
large fixtures, the count fields do not scale with object count — no N+1. A
regression (reintroducing the per-row COUNT) makes the larger fixture issue
more COUNT queries and fails the assertion.

Counting only COUNT-shaped queries (rather than every query) keeps the
assertion focused on what todo 079 fixed — the serializer count N+1 — and
immune to unrelated per-row query patterns elsewhere in the serializer chain
(e.g. the disease-request list serializer's nested ``diagnosis_results``,
which emits per-row SELECTs, not COUNTs, and is out of scope for this todo).

This is a relative O(1) assertion (small N == large N), which is intentionally
more robust than an absolute ``assertEqual(count, N)`` against variable
base-query plumbing — see docs/patterns/performance/query-optimization.md.

Object counts stay at/below 6 so every object lands on page 1 of pagination.
"""

import io

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from ..models import (
    PlantCategory,
    PlantDiseaseDatabase,
    PlantDiseaseRequest,
    PlantDiseaseResult,
    PlantSpecies,
)

User = get_user_model()


def _make_test_image(name):
    """Create a fresh in-memory JPEG that passes the image-upload validator.

    A new SimpleUploadedFile is required per model object — the file pointer is
    consumed when the first object is saved. Mirrors create_test_image() in
    apps/plant_identification/test_api.py.
    """
    image = Image.new("RGB", (300, 300), color="green")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(
        name=name, content=buffer.read(), content_type="image/jpeg"
    )


class PlantIdN1TestMixin:
    """Shared helper for counting COUNT-shaped queries serving a GET."""

    def _measure(self, client, url):
        """Return the number of ``SELECT COUNT(...)`` queries serving a GET.

        Only COUNT-shaped queries are counted: the naive serializer issued one
        per row for the count field, so a growing COUNT total is the exact
        N+1 signature todo 079 eliminated.
        """
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 from {url}, got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )
        return sum(1 for q in ctx.captured_queries if "COUNT(" in q["sql"])

    def _assert_no_n_plus_1(self, url, small_count, large_count):
        """Assert COUNT-query total did not grow as the fixture set grew."""
        self.assertGreater(
            small_count,
            0,
            f"Vacuous test on {url}: the small fixture issued zero COUNT "
            f"queries, so the measurement exercises nothing. The fixture must "
            f"hit the count code path.",
        )
        self.assertEqual(
            small_count,
            large_count,
            f"N+1 regression detected on {url}: COUNT-query total grew from "
            f"{small_count} (small fixture) to {large_count} (large fixture). "
            f"The count fields must be read from a queryset annotation folded "
            f"into the main SELECT, not from a per-row COUNT query. "
            f"See docs/patterns/performance/query-optimization.md.",
        )


class PlantDiseaseRequestListN1Test(PlantIdN1TestMixin, TestCase):
    """disease-requests-list — get_results_count() on the WithResults serializer.

    PlantDiseaseRequestViewSet.get_queryset() filters to the authenticated user
    and annotates ``_results_count``. The list action uses
    PlantDiseaseRequestWithResultsSerializer; its nested diagnosis_results emit
    per-row SELECTs (not COUNTs) so they do not affect this COUNT-only count.
    Each request is given one diagnosis result so the count path is non-trivial.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="diseaserequser",
            email="diseaserequser@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:plant_identification:disease-requests-list")
        self._seq = 0

    def _make_request_with_result(self):
        """Create one disease request (owned by user) plus one diagnosis result."""
        self._seq += 1
        i = self._seq
        request = PlantDiseaseRequest.objects.create(
            user=self.user,
            image_1=_make_test_image(f"disease-{i}.jpg"),
            symptoms_description=f"Symptoms {i}",
        )
        PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name=f"Disease {i}",
            confidence_score=0.85,
            diagnosis_source="api_plant_health",
        )
        return request

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 disease requests.
        self._make_request_with_result()
        self._make_request_with_result()
        small = self._measure(self.client, self.url)

        # Large fixture: 6 disease requests total (still page 1).
        for _ in range(4):
            self._make_request_with_result()
        large = self._measure(self.client, self.url)

        self._assert_no_n_plus_1(self.url, small, large)


class PlantDiseaseDatabaseListN1Test(PlantIdN1TestMixin, TestCase):
    """disease-database-list — PlantDiseaseDatabaseSerializer.get_affected_plant_count().

    PlantDiseaseDatabaseViewSet.get_queryset() filters to rows with
    ``diagnosis_count >= 1`` and annotates ``_affected_plant_count``. Each row
    is given one affected plant (M2M) so the count code path is non-trivial.
    The endpoint allows anonymous access (IsAuthenticatedOrReadOnly).
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("v1:plant_identification:disease-database-list")
        self._seq = 0

    def _make_disease_with_affected_plant(self):
        """Create one disease (diagnosis_count >= 1) with one affected plant."""
        self._seq += 1
        i = self._seq
        species = PlantSpecies.objects.create(
            scientific_name=f"Affected species {i}",
        )
        disease = PlantDiseaseDatabase.objects.create(
            disease_name=f"Disease DB {i}",
            disease_type="fungal",
            confidence_score=0.8,
            diagnosis_count=1,
        )
        disease.affected_plants.add(species)
        return disease

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 disease-database rows.
        self._make_disease_with_affected_plant()
        self._make_disease_with_affected_plant()
        small = self._measure(self.client, self.url)

        # Large fixture: 6 disease-database rows total (still page 1).
        for _ in range(4):
            self._make_disease_with_affected_plant()
        large = self._measure(self.client, self.url)

        self._assert_no_n_plus_1(self.url, small, large)


class PlantCategoryListN1Test(PlantIdN1TestMixin, TestCase):
    """Wagtail plant-categories API — PlantCategorySerializer.get_plant_count().

    PlantCategoryAPIViewSet.get_queryset() annotates ``_plant_count``. The
    endpoint is the Wagtail API router path /api/v2/plant-categories/ (registered
    in plant_community_backend/urls.py); Wagtail API URLs are not reversible
    from a Django namespace, so the path is hard-coded. Each category is given
    one plant species so the count code path is non-trivial per row.
    """

    URL = "/api/v2/plant-categories/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self._seq = 0

    def _make_category_with_species(self):
        """Create one PlantCategory with one plant species attached."""
        self._seq += 1
        i = self._seq
        species = PlantSpecies.objects.create(
            scientific_name=f"Category species {i}",
        )
        category = PlantCategory.objects.create(
            name=f"Plant Category {i}",
            slug=f"plant-category-{i}",
        )
        # plant_species is a ParentalManyToManyField; .add() commits directly
        # to the through table on a saved instance.
        category.plant_species.add(species)
        return category

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 categories.
        self._make_category_with_species()
        self._make_category_with_species()
        small = self._measure(self.client, self.URL)

        # Large fixture: 6 categories total (still page 1).
        for _ in range(4):
            self._make_category_with_species()
        large = self._measure(self.client, self.URL)

        self._assert_no_n_plus_1(self.URL, small, large)
