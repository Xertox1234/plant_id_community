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
from apps.plant_identification.models import PlantSpecies, PlantSpeciesPage
from django.core.cache import cache
from rest_framework.test import APIRequestFactory, APITestCase
from wagtail.models import Page


def _unwrap(response_data):
    """Return the row list whether or not the response is paginated."""
    if isinstance(response_data, dict) and "results" in response_data:
        return response_data["results"]
    return response_data


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

    Exercised via a direct ``get_queryset()`` call rather than an HTTP
    request: ``/api/v2/plants/`` used to 404 under the project's DRF
    ``NamespaceVersioning`` because this ``PagesAPIViewSet`` subclass
    didn't set ``versioning_class = None`` -- fixed by todo 325, see
    ``apps/plant_identification/tests/test_page_viewsets_versioning_and_wiring.py``
    for the HTTP-level coverage. Kept as a direct ``get_queryset()`` call
    here since that's what this test is actually about: the exact
    production line the fix touched
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
