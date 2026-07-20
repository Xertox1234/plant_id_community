r"""SQL LIKE wildcard regression tests for plant_identification search endpoints
(todo 269).

``escape_search_query()`` was removed from every search call site because it
double-escaped SQL LIKE wildcards on top of Django ORM's own
``PatternLookup.process_rhs()`` auto-escaping. The double escape silently
dropped real matches: a search for ``Rosa_`` stopped matching the row
``Rosa_damascena`` (``escape_search_query("Rosa_")`` -> ``Rosa\_``, which the
ORM escaped again, so the LIKE pattern only matched a literal backslash that
was never stored).

Each test below follows the discriminating design pinned by
``packages/wagtail_forum/.../test_user_search.py::test_search_escapes_sql_wildcards``:

1. The query string contains a literal ``_``.
2. A REAL target row whose searched field contains that literal substring is
   created and asserted to be RETURNED. Under the old double-escape bug this
   assertion FAILS -- that is the regression these tests pin. (Verified: with
   the old ``escape_search_query`` applied, ``...__icontains`` returned 0 rows
   for every field exercised here.)
3. A DECOY row that would match ONLY if ``_`` were treated as a SQL wildcard
   (``X`` where the target has ``_``) is created and asserted NOT returned.
   This proves ``_`` is treated as a literal, not a wildcard.
"""

from apps.plant_identification.api.endpoints import (
    PlantSpeciesAPIViewSet,
    PlantSpeciesPageViewSet,
)
from apps.plant_identification.models import (
    PlantDiseaseDatabase,
    PlantSpecies,
    PlantSpeciesPage,
)
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIRequestFactory, APITestCase
from wagtail.models import Page


def _unwrap(response_data):
    """Return the row list whether or not the response is paginated."""
    if isinstance(response_data, dict) and "results" in response_data:
        return response_data["results"]
    return response_data


class PlantSpeciesViewSetSearchWildcardTests(APITestCase):
    """GET /api/v1/plant-identification/species/ ?search= and ?family=."""

    def setUp(self):
        cache.clear()
        self.url = reverse("v1:plant_identification:species-list")
        # Target: literal "Rosa_" appears in scientific_name AND family.
        self.target = PlantSpecies.objects.create(
            scientific_name="Rosa_damascena",
            common_names="Damask rose",
            family="Rosa_family",
        )
        # Decoy: only matches if "_" acts as a single-char SQL wildcard.
        self.decoy = PlantSpecies.objects.create(
            scientific_name="RosaXdamascena",
            common_names="Imposter rose",
            family="RosaXfamily",
        )

    def test_search_treats_underscore_as_literal(self):
        response = self.client.get(self.url, {"search": "Rosa_"})
        self.assertEqual(response.status_code, 200)
        names = {row["scientific_name"] for row in _unwrap(response.data)}
        # Target returned (fails under the old double-escape bug).
        self.assertIn("Rosa_damascena", names)
        # Decoy excluded (proves "_" is literal, not a wildcard).
        self.assertNotIn("RosaXdamascena", names)

    def test_family_filter_treats_underscore_as_literal(self):
        response = self.client.get(self.url, {"family": "Rosa_"})
        self.assertEqual(response.status_code, 200)
        names = {row["scientific_name"] for row in _unwrap(response.data)}
        self.assertIn("Rosa_damascena", names)
        self.assertNotIn("RosaXdamascena", names)


class DiseaseDatabaseViewSetSearchWildcardTests(APITestCase):
    """GET /api/v1/plant-identification/disease-database/ ?search=."""

    def setUp(self):
        cache.clear()
        self.url = reverse("v1:plant_identification:disease-database-list")
        # Base queryset filters diagnosis_count__gte=1; default is 1.
        self.target = PlantDiseaseDatabase.objects.create(
            disease_name="Rosa_rot",
            disease_type="fungal",
            confidence_score=0.8,
            diagnosis_count=1,
        )
        self.decoy = PlantDiseaseDatabase.objects.create(
            disease_name="RosaXrot",
            disease_type="fungal",
            confidence_score=0.8,
            diagnosis_count=1,
        )

    def test_search_treats_underscore_as_literal(self):
        response = self.client.get(self.url, {"search": "Rosa_"})
        self.assertEqual(response.status_code, 200)
        names = {row["disease_name"] for row in _unwrap(response.data)}
        self.assertIn("Rosa_rot", names)
        self.assertNotIn("RosaXrot", names)


class SearchLocalPlantsWildcardTests(APITestCase):
    """GET /api/v1/plant-identification/search/plants/ ?q= (rate-limited)."""

    def setUp(self):
        cache.clear()
        self.url = reverse("v1:plant_identification:search_local_plants")
        self.target = PlantSpecies.objects.create(
            scientific_name="Fern_ales",
            common_names="Underscore fern",
        )
        self.decoy = PlantSpecies.objects.create(
            scientific_name="FernXales",
            common_names="Wildcard fern",
        )

    def test_search_treats_underscore_as_literal(self):
        # Endpoint is rate-limited -- issue exactly one request.
        response = self.client.get(self.url, {"q": "Fern_"})
        self.assertEqual(response.status_code, 200)
        names = {row["scientific_name"] for row in response.data["results"]}
        self.assertIn("Fern_ales", names)
        self.assertNotIn("FernXales", names)


class SearchLocalDiseasesWildcardTests(APITestCase):
    """GET /api/v1/plant-identification/search/diseases/ ?q= (rate-limited)."""

    def setUp(self):
        cache.clear()
        self.url = reverse("v1:plant_identification:search_local_diseases")
        # No diagnosis_count gate on this endpoint.
        self.target = PlantDiseaseDatabase.objects.create(
            disease_name="Mildew_spot",
            disease_type="fungal",
            confidence_score=0.7,
        )
        self.decoy = PlantDiseaseDatabase.objects.create(
            disease_name="MildewXspot",
            disease_type="fungal",
            confidence_score=0.7,
        )

    def test_search_treats_underscore_as_literal(self):
        # Endpoint is rate-limited -- issue exactly one request.
        response = self.client.get(self.url, {"q": "Mildew_"})
        self.assertEqual(response.status_code, 200)
        names = {row["disease_name"] for row in response.data["results"]}
        self.assertIn("Mildew_spot", names)
        self.assertNotIn("MildewXspot", names)


class PlantSpeciesAPIViewSetWildcardTests(APITestCase):
    """Wagtail v2 API PlantSpeciesAPIViewSet -- family__icontains.

    Exercised via a direct ``get_queryset()`` call rather than an HTTP request:
    over HTTP, Wagtail's ``FieldsFilter`` applies an EXACT ``family=`` match
    (``family`` is an available db field), which intersects with and shadows
    the viewset's own ``family__icontains`` -- so ``?family=Rosa_`` returns 0
    rows even after the fix and could not honestly assert the target is
    returned. Calling ``get_queryset()`` runs the exact production line the
    fix touched (``family__icontains``) with no filter-backend interference.
    """

    def setUp(self):
        cache.clear()
        self.target = PlantSpecies.objects.create(
            scientific_name="Snippet target species",
            family="Rosa_snippet",
        )
        self.decoy = PlantSpecies.objects.create(
            scientific_name="Snippet decoy species",
            family="RosaXsnippet",
        )

    def test_family_filter_treats_underscore_as_literal(self):
        view = PlantSpeciesAPIViewSet()
        view.request = APIRequestFactory().get("/?family=Rosa_")
        view.args = ()
        view.kwargs = {}
        ids = set(view.get_queryset().values_list("id", flat=True))
        # Target returned (fails under the old double-escape bug).
        self.assertIn(self.target.id, ids)
        # Decoy excluded (proves "_" is literal, not a wildcard).
        self.assertNotIn(self.decoy.id, ids)


class PlantSpeciesPageViewSetWildcardTests(APITestCase):
    """Wagtail v2 API PlantSpeciesPageViewSet -- plant_species__family__icontains.

    Exercised via a direct ``get_queryset()`` call rather than an HTTP request:
    ``/api/v2/plants/`` 404s under the project's DRF ``NamespaceVersioning``
    because this ``PagesAPIViewSet`` subclass does not set
    ``versioning_class = None`` (unlike the snippet viewsets). Calling
    ``get_queryset()`` runs the exact production line the fix touched
    (``plant_species__family__icontains`` traversal) over the
    ``.live().public().specific()`` base queryset.
    """

    def setUp(self):
        cache.clear()
        root = Page.objects.get(id=1)

        self.target_species = PlantSpecies.objects.create(
            scientific_name="Page target species",
            family="Rosa_page",
        )
        self.decoy_species = PlantSpecies.objects.create(
            scientific_name="Page decoy species",
            family="RosaXpage",
        )

        self.target_page = PlantSpeciesPage(
            title="Rosa underscore page",
            slug="rosa-underscore-page",
            plant_species=self.target_species,
            introduction="<p>Target intro.</p>",
            content_blocks=[],
        )
        root.add_child(instance=self.target_page)
        self.target_page.save_revision().publish()

        self.decoy_page = PlantSpeciesPage(
            title="Rosa wildcard page",
            slug="rosa-wildcard-page",
            plant_species=self.decoy_species,
            introduction="<p>Decoy intro.</p>",
            content_blocks=[],
        )
        root.add_child(instance=self.decoy_page)
        self.decoy_page.save_revision().publish()

    def test_family_filter_treats_underscore_as_literal(self):
        view = PlantSpeciesPageViewSet()
        view.request = APIRequestFactory().get("/?family=Rosa_")
        view.args = ()
        view.kwargs = {}
        ids = set(view.get_queryset().values_list("id", flat=True))
        self.assertIn(self.target_page.id, ids)
        self.assertNotIn(self.decoy_page.id, ids)


class PlantSpeciesSearchPercentWildcardTests(APITestCase):
    """Parity coverage for the OTHER SQL LIKE wildcard, ``%`` (todo 269 review).

    The removed ``escape_search_query`` escaped BOTH ``%`` and ``_``, so ``%``
    had the identical silent-drop bug. ``_`` is covered per-endpoint above; this
    pins the ``%`` case for the shared ``__icontains`` mechanism via one
    representative endpoint. (``\\`` is intentionally not tested separately: the
    removed util only ever escaped ``%`` and ``_``, never backslash, so ``\\``
    was never a double-escape vector for this fix.)
    """

    def setUp(self):
        cache.clear()
        self.url = reverse("v1:plant_identification:species-list")
        # Target contains a literal "%"; the decoy would match only if "%"
        # acted as a "zero-or-more-chars" SQL wildcard.
        self.target = PlantSpecies.objects.create(scientific_name="Rosa%alba")
        self.decoy = PlantSpecies.objects.create(scientific_name="RosaZZalba")

    def test_search_treats_percent_as_literal(self):
        response = self.client.get(self.url, {"search": "Rosa%"})
        self.assertEqual(response.status_code, 200)
        names = {row["scientific_name"] for row in _unwrap(response.data)}
        # Target returned (fails under the old double-escape bug).
        self.assertIn("Rosa%alba", names)
        # Decoy excluded (proves "%" is literal, not a wildcard).
        self.assertNotIn("RosaZZalba", names)
