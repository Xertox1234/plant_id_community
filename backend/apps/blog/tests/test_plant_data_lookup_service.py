"""The external-API step of PlantDataLookupService (todo-less fix, 2026-10-19).

The step used to call `TrefleAPIService.search_species`, a method that class
never had; the AttributeError was swallowed by the step's own `except
Exception`, so Trefle never answered a lookup. mypy's `attr-defined` check
found it when apps/blog joined the gate. These tests pin the call that exists.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

MODULE = "apps.blog.services.plant_data_lookup_service"

TREFLE_HIT = {
    "id": 123,
    "scientific_name": "Monstera deliciosa",
    "common_name": "Swiss cheese plant",
    "family": "Araceae",
    "genus": "Monstera",
}


class ExternalApiLookupTests(SimpleTestCase):
    def _service(self, trefle):
        with patch(f"{MODULE}.TrefleAPIService", return_value=trefle), patch(
            f"{MODULE}.PlantNetAPIService", return_value=MagicMock()
        ):
            from apps.blog.services.plant_data_lookup_service import (
                PlantDataLookupService,
            )

            return PlantDataLookupService()

    def test_a_trefle_hit_is_found_via_search_plants(self):
        trefle = MagicMock()
        trefle.search_plants.return_value = [TREFLE_HIT]

        result = self._service(trefle)._search_external_apis("monstera")

        trefle.search_plants.assert_called_once_with("monstera", limit=1)
        self.assertTrue(result["found"])
        self.assertEqual(result["source"], "trefle_api")
        self.assertEqual(result["data"]["scientific_name"], "Monstera deliciosa")
        self.assertEqual(result["data"]["plant_name"], "Swiss cheese plant")
        self.assertEqual(result["data"]["trefle_id"], 123)
        self.assertEqual(result["data"]["api_source"], "trefle")

    def test_no_trefle_hits_is_not_found(self):
        trefle = MagicMock()
        trefle.search_plants.return_value = []

        result = self._service(trefle)._search_external_apis("no such plant")

        self.assertFalse(result["found"])
        self.assertIsNone(result["source"])

    def test_a_trefle_failure_is_not_found_not_raised(self):
        trefle = MagicMock()
        trefle.search_plants.side_effect = RuntimeError("trefle down")

        result = self._service(trefle)._search_external_apis("monstera")

        self.assertFalse(result["found"])

    def test_without_a_trefle_key_the_step_is_skipped(self):
        with patch(
            f"{MODULE}.TrefleAPIService", side_effect=ValueError("no key")
        ), patch(f"{MODULE}.PlantNetAPIService", return_value=MagicMock()):
            from apps.blog.services.plant_data_lookup_service import (
                PlantDataLookupService,
            )

            service = PlantDataLookupService()

        self.assertIsNone(service.trefle_service)
        self.assertFalse(service._search_external_apis("monstera")["found"])
