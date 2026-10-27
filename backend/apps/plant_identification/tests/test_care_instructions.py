"""Identify's `care_instructions` carries no placeholder and no taxonomy (todo 662).

It used to be one fixed set of care strings ("Moderate watering recommended",
"Bright indirect light", ...) for every plant, with PlantNet's scientific name,
family and genus merged in -- and it came from PlantNet's top result even when
the returned plant was Plant.id's. Owner decision 2026-10-27: no care source for
now. `care_instructions` is null until Scan 2.0 part 4 brings real care guides,
and the clients hide their care section on null.
"""

from unittest.mock import Mock, patch

from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
    get_executor,
)
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

PLACEHOLDER_CARE = {
    "Moderate watering recommended",
    "Bright indirect light",
    "Average humidity",
    "Monthly during growing season",
    "Prune as needed",
}


def build(plant_id=None, plantnet=None):
    """A service with both providers stubbed; None means 'not configured'."""
    with patch.object(
        CombinedPlantIdentificationService, "__init__", lambda self: None
    ):
        svc = CombinedPlantIdentificationService()
    svc.plant_id = plant_id
    svc.plantnet = plantnet
    svc.executor = get_executor()
    return svc


def provider(returns):
    stub = Mock()
    stub.identify_plant = Mock(return_value=returns)
    return stub


def plant_id_result(*pairs):
    suggestions = [
        {"plant_name": name, "scientific_name": name, "probability": p}
        for name, p in pairs
    ]
    return {
        "suggestions": suggestions,
        "top_suggestion": suggestions[0],
        "confidence": suggestions[0]["probability"],
        "health_assessment": None,
        "health_assessment_error": None,
    }


def plantnet_result(*rows):
    """PlantNet rows with the family/genus that used to leak into care."""
    return {
        "results": [
            {
                "score": score,
                "species": {
                    "scientificNameWithoutAuthor": name,
                    "family": {"scientificName": family},
                    "genus": {"scientificName": name.split()[0]},
                },
            }
            for name, score, family in rows
        ]
    }


def test_plantnet_taxonomy_never_lands_in_care_instructions():
    """The rows the sim showed under Care Instructions: Scientific name,
    Family, Genus. PlantNet alone answers, with full taxonomy."""
    svc = build(
        plant_id=None,
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.8, "Moraceae"))),
    )

    out = svc.identify_plant(b"image-bytes")

    care = out["care_instructions"]
    assert care is None
    # The taxonomy is still in the response, on the suggestion it describes.
    top = out["combined_suggestions"][0]
    assert top["scientific_name"] == "Ficus lyrata"
    assert top["family"] == "Moraceae"


def test_no_placeholder_care_when_both_providers_agree():
    svc = build(
        plant_id=provider(plant_id_result(("Ficus lyrata", 0.9))),
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.8, "Moraceae"))),
    )

    out = svc.identify_plant(b"image-bytes")

    assert out["care_instructions"] is None
    assert out["top_source"] == "both"


def test_disagreeing_providers_get_no_care_from_the_other_plant():
    """The fiddle-leaf case: Plant.id's top plant is Adenium obesum, PlantNet's
    is Ficus lyrata, and they share nothing. The returned plant is Plant.id's,
    and the care dict used to be built from PlantNet's Ficus -- care for a
    different plant. No care source belongs to the returned species, so it is
    null rather than another plant's."""
    svc = build(
        plant_id=provider(plant_id_result(("Adenium obesum", 0.62))),
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.55, "Moraceae"))),
    )

    out = svc.identify_plant(b"image-bytes")

    assert out["combined_suggestions"][0]["scientific_name"] == "Adenium obesum"
    assert out["care_instructions"] is None


def test_the_placeholder_care_text_is_gone_from_the_service():
    """A regression guard on the source: the fixed strings cannot come back
    by a code path these stubs do not drive."""
    import inspect

    from apps.plant_identification.services import combined_identification_service

    source = inspect.getsource(combined_identification_service)
    assert not [text for text in PLACEHOLDER_CARE if text in source]
    assert not hasattr(CombinedPlantIdentificationService, "_extract_care_info")


class IdentifyResponseCareIsNullTests(TestCase):
    """The API answer, end to end through the view, with providers disagreeing."""

    URL = "/api/v1/plant-identification/identify/"

    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(
            username="carefree", password="TestPass123!"  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=user)

    def test_response_care_instructions_is_null(self):
        svc = build(
            plant_id=provider(plant_id_result(("Adenium obesum", 0.62))),
            plantnet=provider(plantnet_result(("Ficus lyrata", 0.55, "Moraceae"))),
        )
        image = SimpleUploadedFile(
            "leaf.jpg", b"\xff\xd8\xff\xe0fake", content_type="image/jpeg"
        )
        with patch("apps.plant_identification.utils.validate_image_file"), patch(
            "apps.plant_identification.api.simple_views.CombinedPlantIdentificationService",
            return_value=svc,
        ):
            resp = self.client.post(self.URL, {"image": image}, format="multipart")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["plant_name"], "Adenium obesum")
        self.assertIn("care_instructions", resp.data)
        self.assertIsNone(resp.data["care_instructions"])
