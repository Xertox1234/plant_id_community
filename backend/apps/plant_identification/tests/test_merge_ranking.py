"""How the combined identify answer picks its top plant (todo 661).

Plant.id's `probability` and PlantNet's `score` come from different models and
are not on one scale. The merge used to sort both providers' suggestions by
that one key, and the response's `confidence` was always Plant.id's -- so a
PlantNet plant could be shown with Plant.id's confidence for a different plant.

The interim rule these tests pin (revisit from the `[MERGE]` log lines):
  1. a species both providers name ranks above any species only one names;
  2. then Plant.id-only species, by Plant.id probability;
  3. then PlantNet-only species, by PlantNet score.
`confidence` is always the returned top suggestion's own number.
"""

from unittest.mock import Mock, patch

from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
    get_executor,
    normalize_scientific_name,
)
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient


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


def plantnet_result(*pairs):
    return {
        "results": [
            {"score": s, "species": {"scientificNameWithoutAuthor": name}}
            for name, s in pairs
        ]
    }


# --------------------------------------------------------------------------
# name normalisation
# --------------------------------------------------------------------------


def test_normalize_keeps_genus_and_epithet_only():
    assert normalize_scientific_name("Ficus lyrata Warb.") == "ficus lyrata"
    assert normalize_scientific_name("  Ficus   LYRATA ") == "ficus lyrata"
    assert normalize_scientific_name("Ficus") == "ficus"


def test_normalize_handles_missing_names():
    assert normalize_scientific_name(None) is None
    assert normalize_scientific_name("") is None
    assert normalize_scientific_name("   ") is None


# --------------------------------------------------------------------------
# agree / disagree / single provider
# --------------------------------------------------------------------------


def test_agreement_outranks_a_higher_single_provider_probability():
    """The fiddle-leaf shape: Plant.id leads with Adenium but also lists Ficus
    lyrata, which PlantNet names first. The species both name wins."""
    svc = build(
        plant_id=provider(
            plant_id_result(("Adenium obesum", 0.62), ("Ficus lyrata", 0.21))
        ),
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.55))),
    )

    out = svc.identify_plant(b"image-bytes")

    top = out["combined_suggestions"][0]
    assert top["scientific_name"] == "Ficus lyrata"
    assert top["plantnet_matched"] is True
    assert top["plantnet_score"] == 0.55
    assert out["top_source"] == "both"
    assert out["confidence_score"] == 0.21, "the top plant's own (Plant.id) number"
    assert [s["rank"] for s in out["combined_suggestions"]] == [1, 2]


def test_a_name_differing_only_by_author_suffix_counts_as_agreement():
    """Plant.id v3's `name` and PlantNet's `scientificNameWithoutAuthor` are
    normally both author-free, so this exercises a defensive path rather than
    reproducing the observed bug: a suffix or case difference must not split
    one species into two disagreeing entries."""
    svc = build(
        plant_id=provider(plant_id_result(("Ficus lyrata Warb.", 0.4))),
        plantnet=provider(plantnet_result(("ficus lyrata", 0.7))),
    )

    out = svc.identify_plant(b"image-bytes")

    assert len(out["combined_suggestions"]) == 1
    assert out["combined_suggestions"][0]["plantnet_matched"] is True
    assert out["top_source"] == "both"


def test_disagreement_ranks_plant_id_before_plantnet_whatever_the_raw_scores():
    """Raw scores are not comparable across providers, so a higher PlantNet
    score no longer jumps a Plant.id answer."""
    svc = build(
        plant_id=provider(
            plant_id_result(("Adenium obesum", 0.30), ("Pachypodium lamerei", 0.10))
        ),
        plantnet=provider(
            plantnet_result(("Ficus lyrata", 0.90), ("Ficus elastica", 0.05))
        ),
    )

    out = svc.identify_plant(b"image-bytes")

    names = [s["scientific_name"] for s in out["combined_suggestions"]]
    assert names == [
        "Adenium obesum",
        "Pachypodium lamerei",
        "Ficus lyrata",
        "Ficus elastica",
    ]
    assert out["top_source"] == "plant_id"
    assert out["confidence_score"] == 0.30


def test_plantnet_alone_ranks_first_with_its_own_confidence():
    """Plant.id answered nothing, so PlantNet's plant is returned -- and the
    confidence is PlantNet's score for that plant, not a Plant.id number."""
    svc = build(
        plant_id=None,
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.55), ("Ficus", 0.2))),
    )

    out = svc.identify_plant(b"image-bytes")

    top = out["combined_suggestions"][0]
    assert top["scientific_name"] == "Ficus lyrata"
    assert top["source"] == "plantnet"
    assert out["top_source"] == "plantnet"
    assert out["confidence_score"] == 0.55


def test_plant_id_alone_keeps_its_own_order():
    svc = build(
        plant_id=provider(
            plant_id_result(("Monstera deliciosa", 0.9), ("Monstera adansonii", 0.05))
        ),
        plantnet=None,
    )

    out = svc.identify_plant(b"image-bytes")

    names = [s["scientific_name"] for s in out["combined_suggestions"]]
    assert names == ["Monstera deliciosa", "Monstera adansonii"]
    assert out["top_source"] == "plant_id"
    assert out["confidence_score"] == 0.9


def test_no_answer_has_no_top_source():
    svc = build(plant_id=None, plantnet=None)

    out = svc.identify_plant(b"image-bytes")

    assert out["combined_suggestions"] == []
    assert out["top_source"] is None
    assert out["confidence_score"] == 0


def test_summary_and_confidence_name_the_same_number():
    svc = build(
        plant_id=None,
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.55))),
    )
    out = svc.identify_plant(b"image-bytes")

    assert "55.0%" in svc.get_identification_summary(out)


def test_the_merge_log_line_names_both_tops_and_nothing_private():
    """Asserted on the module logger: the project's JSON logging sets
    propagate=False, so caplog never sees `apps.*` records."""
    svc = build(
        plant_id=provider(plant_id_result(("Adenium obesum", 0.62))),
        plantnet=provider(plantnet_result(("Ficus lyrata", 0.55))),
    )

    with patch(
        "apps.plant_identification.services.combined_identification_service.logger"
    ) as log:
        svc.identify_plant(b"image-bytes")

    lines = [
        str(c.args[0]) for c in log.info.call_args_list if "[MERGE]" in str(c.args[0])
    ]
    assert len(lines) == 1
    line = lines[0]
    assert "Adenium obesum" in line and "0.62" in line
    assert "Ficus lyrata" in line and "0.55" in line
    assert "agree=False" in line
    assert "top_source=plant_id" in line
    assert "image-bytes" not in line


# --------------------------------------------------------------------------
# the endpoint
# --------------------------------------------------------------------------


class IdentifyResponseNamesItsTopAnswerTests(TestCase):
    URL = "/api/v1/plant-identification/identify/"

    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(
            username="fig", password="TestPass123!"  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=user)

    def test_confidence_belongs_to_the_returned_plant(self):
        svc = build(
            plant_id=None,
            plantnet=provider(plantnet_result(("Ficus lyrata", 0.55))),
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
        self.assertEqual(resp.data["scientific_name"], "Ficus lyrata")
        self.assertEqual(resp.data["confidence"], 0.55)
        self.assertEqual(resp.data["top_source"], "plantnet")
        self.assertIn("55.0%", resp.data["summary"])
