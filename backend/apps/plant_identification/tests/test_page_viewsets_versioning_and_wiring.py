"""
Tests for PlantSpeciesPageViewSet and PlantCategoryIndexPageViewSet's
missing `versioning_class` (todo 325) and, for the latter, the same
serializer-wiring bug as todo 324.

`REST_FRAMEWORK["DEFAULT_VERSIONING_CLASS"] = "NamespaceVersioning"` is set
project-wide, so any custom viewset that doesn't opt out with
`versioning_class = None` 404s on every request with "Invalid version in
URL path" — live-confirmed on `/api/v2/plants/` before this fix. These
tests hit the real routes and assert 200, not 404.

`PlantCategoryIndexPageViewSet` additionally set `serializer_class`
(never read by Wagtail's own `get_serializer_class()`) instead of
overriding `get_serializer_class()` — see
`apps/plant_identification/api/endpoints.py`'s docstring for why a
`base_serializer_class` rename alone wouldn't have surfaced the custom
`categories`/`featured_plants` fields either.
"""

from django.test import TestCase
from wagtail.models import Site

from ..models import (
    PlantCategory,
    PlantCategoryIndexPage,
    PlantSpecies,
    PlantSpeciesPage,
)


def _site_root():
    """The default Wagtail `Site`'s actual root page, not the invisible
    tree root (`Page.objects.get(id=1)`) — a page added directly under the
    bare tree root isn't a descendant of any configured `Site`, so
    `get_url()`/`get_url_parts()` return `None` for it."""
    return Site.objects.get(is_default_site=True).root_page


class PlantSpeciesPageViewSetVersioningTestCase(TestCase):
    def setUp(self):
        species = PlantSpecies.objects.create(
            scientific_name="Versioning test species", family="Rosaceae"
        )
        self.plant_page = PlantSpeciesPage(
            title="Versioning Test Plant",
            slug="versioning-test-plant",
            plant_species=species,
            introduction="<p>Intro.</p>",
            content_blocks=[],
        )
        _site_root().add_child(instance=self.plant_page)

    def test_list_endpoint_returns_200_not_404(self):
        response = self.client.get("/api/v2/plants/")
        self.assertEqual(response.status_code, 200)

    def test_detail_endpoint_returns_200_not_404(self):
        response = self.client.get(f"/api/v2/plants/{self.plant_page.id}/")
        self.assertEqual(response.status_code, 200)


class PlantCategoryIndexPageViewSetTestCase(TestCase):
    def setUp(self):
        PlantCategory.objects.create(
            name="Featured Category", slug="featured-category", is_featured=True
        )
        self.index_page = PlantCategoryIndexPage(
            title="Plant Index Test", slug="plant-index-test"
        )
        _site_root().add_child(instance=self.index_page)

    def test_list_endpoint_returns_200_not_404(self):
        response = self.client.get("/api/v2/plant-index/")
        self.assertEqual(response.status_code, 200)

    def test_custom_fields_present_in_response(self):
        response = self.client.get(f"/api/v2/plant-index/{self.index_page.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for field in ("categories", "featured_plants"):
            self.assertIn(field, data)
        slugs = {row["slug"] for row in data["categories"]}
        self.assertIn("featured-category", slugs)

    def test_url_is_request_derived(self):
        response = self.client.get(f"/api/v2/plant-index/{self.index_page.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["url"].startswith("http://testserver/"))
