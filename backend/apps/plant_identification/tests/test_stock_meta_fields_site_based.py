"""
Documents/pins the mechanism behind todo 327: Wagtail's own stock
`meta.detail_url` field (built by `DetailUrlField` ->
`get_object_detail_url()` -> `wagtail.api.v2.utils.get_full_url()`) is NOT
request-derived, unlike every URL this project's own serializer code
builds (todo 308's `_absolute_page_url()`/`request.build_absolute_uri()`
fix). It always resolves via the Wagtail `Site` model, so it emits
`http://localhost/...` regardless of the actual request host whenever a
Site row for the real domain isn't configured.

Live-probing this in production isn't possible today (todo 327's AC #1):
every endpoint that would expose it either returns zero items (no seed
data at the snippet endpoints) or -- for this project's own hand-written
Page serializers -- never lists "detail_url"/"html_url" in `Meta.fields`
at all, so `meta` stays empty for those (confirmed empirically: neither
`BlogCategorySerializer` nor any of the todo-324/325 Page serializers
include them, sidestepping this specific bug incidentally). This test
verifies the mechanism directly instead, on a viewset that DOES expose
it: `PlantSpeciesAPIViewSet` (a snippet viewset using Wagtail's own
dynamic serializer construction, unmodified).

Per todo 327's own recommendation, this is left deferred/documented
(Option 2) rather than fixed -- nothing in web/mobile reads
`meta.detail_url`/`meta.html_url` today (confirmed by grep in the todo).
This test exists so a future accidental "fix" or regression here is
visible, and to give whoever revisits todo 327 a ready reproducer.
"""

from django.test import TestCase, override_settings

from ..models import PlantSpecies


class StockDetailUrlFieldIsSiteBasedNotRequestDerivedTestCase(TestCase):
    @override_settings(ALLOWED_HOSTS=["api.example.com", "testserver"])
    def test_detail_url_ignores_actual_request_host(self):
        species = PlantSpecies.objects.create(
            scientific_name="Todo 327 species", family="Rosaceae"
        )
        response = self.client.get(
            f"/api/v2/plant-species/{species.id}/", SERVER_NAME="api.example.com"
        )
        self.assertEqual(response.status_code, 200)
        detail_url = response.json()["meta"]["detail_url"]
        # This is the bug, pinned: a request-derived URL would start with
        # "http://api.example.com/". It doesn't -- it's Site-based.
        self.assertTrue(detail_url.startswith("http://localhost/"), detail_url)
