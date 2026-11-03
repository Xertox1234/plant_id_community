"""CombinedPlantIdentificationService.scan() and the scan outcome functions (B3)."""

from unittest.mock import Mock, patch

import pytest
from apps.plant_identification.scan_jobs import classify_scan, summarize_scan_result
from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
    get_executor,
)
from django.test import override_settings

LEAF, WHOLE, FLOWER, PROBLEM = b"leaf-bytes", b"whole-bytes", b"flower", b"problem"


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


def provider(returns=None, raises=None):
    stub = Mock()
    stub.identify_plant = Mock(return_value=returns, side_effect=raises)
    return stub


def plantnet_result(score):
    return {
        "results": [
            {
                "score": score,
                "species": {
                    "scientificNameWithoutAuthor": "Monstera deliciosa",
                    "commonNames": ["Swiss cheese plant"],
                    "genus": {"scientificNameWithoutAuthor": "Monstera"},
                    "family": {"scientificNameWithoutAuthor": "Araceae"},
                },
            }
        ]
    }


_FICUS = {
    "plant_name": "Ficus lyrata",
    "scientific_name": "Ficus lyrata",
    "probability": 0.91,
    "description": "A fig.",
}
PLANT_ID_OK = {  # the shape of PlantIDAPIService._format_response
    "suggestions": [_FICUS],
    "health_assessment": None,
    "health_assessment_error": None,
    "top_suggestion": _FICUS,
    "confidence": 0.91,
}


def test_diagnose_sends_problem_to_health_and_others_to_identification():
    plant_id = provider(returns=PLANT_ID_OK)
    plantnet = provider(returns=plantnet_result(0.4))
    svc = build(plant_id=plant_id, plantnet=plantnet)

    out = svc.scan({"problem": PROBLEM, "whole": WHOLE, "leaf": LEAF}, "diagnose")

    kwargs = plant_id.identify_plant.call_args.kwargs
    assert kwargs["images"] == [LEAF, WHOLE]
    assert kwargs["health_images"] == [PROBLEM]
    assert kwargs["include_diseases"] is True
    pn_kwargs = plantnet.identify_plant.call_args.kwargs
    assert pn_kwargs["organs"] == ["leaf", "habit"]
    sent = [f.getvalue() for f in plantnet.identify_plant.call_args.args[0]]
    assert sent == [LEAF, WHOLE]
    assert out["disease_detection_status"] == "ok"


def test_diagnose_problem_only_goes_everywhere_as_leaf():
    plant_id = provider(returns=PLANT_ID_OK)
    plantnet = provider(returns=plantnet_result(0.4))
    svc = build(plant_id=plant_id, plantnet=plantnet)

    svc.scan({"problem": PROBLEM}, "diagnose")

    kwargs = plant_id.identify_plant.call_args.kwargs
    assert kwargs["images"] == [PROBLEM]
    assert kwargs["health_images"] == [PROBLEM]
    assert plantnet.identify_plant.call_args.kwargs["organs"] == ["leaf"]


@override_settings(SCAN_PLANTNET_CONFIDENCE_FLOOR=0.5)
def test_identify_confident_plantnet_skips_plant_id():
    plant_id = provider(returns=PLANT_ID_OK)
    svc = build(plant_id=plant_id, plantnet=provider(returns=plantnet_result(0.8)))

    out = svc.scan({"leaf": LEAF, "flower": FLOWER}, "identify")

    plant_id.identify_plant.assert_not_called()
    assert out["combined_suggestions"][0]["source"] == "plantnet"
    assert out["providers"]["plant_id"]["status"] == "not_configured"
    assert out["degraded"] is False


@override_settings(SCAN_PLANTNET_CONFIDENCE_FLOOR=0.5, PLANT_ID_DIAGNOSIS_RESERVE=2)
def test_identify_low_plantnet_falls_back_with_reserve():
    plant_id = provider(returns=PLANT_ID_OK)
    svc = build(plant_id=plant_id, plantnet=provider(returns=plantnet_result(0.3)))

    out = svc.scan({"leaf": LEAF, "whole": WHOLE}, "identify")

    plant_id.identify_plant.assert_called_once()
    kwargs = plant_id.identify_plant.call_args.kwargs
    assert kwargs["include_diseases"] is False
    assert kwargs["quota_reserve"] == 2
    assert kwargs["images"] == [LEAF, WHOLE]
    assert out["combined_suggestions"][0]["source"] == "plant_id"


@override_settings(SCAN_PLANTNET_CONFIDENCE_FLOOR=0.5)
def test_identify_fallback_failure_returns_plantnet():
    svc = build(
        plant_id=provider(raises=RuntimeError("boom")),
        plantnet=provider(returns=plantnet_result(0.3)),
    )

    out = svc.scan({"leaf": LEAF}, "identify")

    assert out["combined_suggestions"][0]["source"] == "plantnet"
    assert out["providers"]["plant_id"]["status"] == "failed"


# --------------------------------------------------------------------------
# classify_scan
# --------------------------------------------------------------------------


def test_classify_scan_no_suggestions_fails():
    assert classify_scan("diagnose", {"combined_suggestions": []}) == ("failed", "")
    assert classify_scan("identify", {}) == ("failed", "")


def test_classify_scan_identify_done():
    results = {"combined_suggestions": [{"plant_name": "x"}]}
    assert classify_scan("identify", results) == ("done", "identify")


def test_classify_scan_diagnose_ok_done():
    results = {
        "combined_suggestions": [{"plant_name": "x"}],
        "disease_detection_status": "ok",
    }
    assert classify_scan("diagnose", results) == ("done", "diagnose")


def test_classify_scan_diagnose_unavailable_degraded():
    results = {
        "combined_suggestions": [{"plant_name": "x"}],
        "disease_detection_status": "unavailable",
    }
    assert classify_scan("diagnose", results) == ("degraded", "identify")


# --------------------------------------------------------------------------
# summarize_scan_result
# --------------------------------------------------------------------------


def _results(status="ok", disease=None):
    return {
        "combined_suggestions": [
            {
                "plant_name": f"Plant {i}",
                "scientific_name": f"Genus species{i}",
                "probability": 0.9 - i / 10,
                "description": "First." if i == 0 else None,
                "source": "plant_id",
            }
            for i in range(7)
        ],
        "confidence_score": 0.9,
        "disease_detection_status": status,
        "disease_detection": disease,
    }


def test_summarize_diagnosis_states():
    found = summarize_scan_result(
        "diagnose",
        _results(
            disease={
                "is_healthy": False,
                "disease_name": "Root rot",
                "probability": 0.7,
                "description": "Too wet.",
            }
        ),
    )
    assert found["diagnosis"] == {
        "state": "found",
        "name": "Root rot",
        "probability": 0.7,
        "description": "Too wet.",
    }
    assert found["plant_name"] == "Plant 0"
    assert found["scientific_name"] == "Genus species0"
    assert found["confidence"] == 0.9
    assert found["description"] == "First."
    assert len(found["suggestions"]) == 5
    assert set(found["suggestions"][0]) == {
        "plant_name",
        "scientific_name",
        "probability",
    }

    healthy_none = summarize_scan_result("diagnose", _results(disease=None))
    assert healthy_none["diagnosis"]["state"] == "healthy"
    healthy_flag = summarize_scan_result(
        "diagnose",
        _results(disease={"is_healthy": True, "disease_name": "x", "probability": 0.1}),
    )
    assert healthy_flag["diagnosis"]["state"] == "healthy"

    unavailable = summarize_scan_result("diagnose", _results(status="unavailable"))
    assert unavailable["diagnosis"]["state"] == "unavailable"

    assert summarize_scan_result("identify", _results())["diagnosis"] is None


def test_summarize_empty_result_is_none():
    assert summarize_scan_result("diagnose", {"combined_suggestions": []}) is None


@pytest.mark.parametrize("mode", ["diagnose", "identify"])
def test_scan_returns_same_keys_as_identify_plant(mode):
    svc = build(
        plant_id=provider(returns=PLANT_ID_OK),
        plantnet=provider(returns=plantnet_result(0.3)),
    )
    shots = {"problem": PROBLEM} if mode == "diagnose" else {"leaf": LEAF}
    assert set(svc.scan(shots, mode)) == set(svc.identify_plant(b"image"))


def test_gather_reraises_celery_soft_time_limit():
    """Inside the scan task, the soft limit must reach the task's handler."""
    from celery.exceptions import SoftTimeLimitExceeded

    service = CombinedPlantIdentificationService.__new__(
        CombinedPlantIdentificationService
    )
    future = Mock()
    future.result.side_effect = SoftTimeLimitExceeded()
    with pytest.raises(SoftTimeLimitExceeded):
        service._gather(future, "PlantNet", 5)


def test_gather_still_names_other_thread_errors():
    from apps.plant_identification.provider_failures import classify_provider_failure

    service = CombinedPlantIdentificationService.__new__(
        CombinedPlantIdentificationService
    )
    future = Mock()
    future.result.side_effect = RuntimeError("boom")
    outcome = service._gather(future, "PlantNet", 5)
    assert outcome.result is None
    assert outcome.reason == classify_provider_failure(RuntimeError("boom"))
