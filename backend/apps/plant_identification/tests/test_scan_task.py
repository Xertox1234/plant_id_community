"""The background scan-job Celery tasks and their FCM push (Scan 2.0 B3).

``.delay`` runs as ``.apply`` (tests/conftest.py), so the whole chain
run_scan_job -> on_commit -> notify_scan_job_finished -> send_scan_push_to_device
runs in-process once the on_commit callbacks are executed.
"""

import io
from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest
from apps.core.models import PushDevice
from apps.plant_identification.scan_jobs import expire_stale_jobs
from apps.plant_identification.scan_models import ScanJob, ScanJobImage
from apps.plant_identification.scan_storage import normalize_scan_photo
from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
)
from apps.plant_identification.tasks import notify_scan_job_finished, run_scan_job
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image

TOKEN = "device-token-1"


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 120, 40)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def roots(tmp_path):
    media = tmp_path / "media"
    private = tmp_path / "private"
    media.mkdir()
    private.mkdir()
    with override_settings(MEDIA_ROOT=str(media), SCAN_PHOTO_LOCAL_ROOT=str(private)):
        yield


@pytest.fixture
def user(db):
    u = get_user_model().objects.create_user(
        username="scanner", email="scanner@example.com", password="x" * 16
    )
    PushDevice.objects.create(user=u, token=TOKEN, platform="ios")
    return u


def _job(user, mode="diagnose", roles=("problem", "leaf")):
    job = ScanJob.objects.create(user=user, mode=mode, local_date=date(2026, 11, 2))
    for role in roles:
        ScanJobImage.objects.create(
            job=job,
            role=role,
            image=normalize_scan_photo(ContentFile(_jpeg(), name="x.jpg")),
        )
    return job


def _results(status="ok", suggestions=True):
    return {
        "combined_suggestions": (
            [
                {
                    "plant_name": "Fiddle-leaf fig",
                    "scientific_name": "Ficus lyrata",
                    "probability": 0.9,
                    "description": "A fig.",
                    "source": "plant_id",
                }
            ]
            if suggestions
            else []
        ),
        "confidence_score": 0.9 if suggestions else 0,
        "disease_detection": None,
        "disease_detection_status": status,
    }


@pytest.fixture
def fcm():
    """FCM switched on, with send_fcm_message recorded instead of sent."""
    with (
        patch("apps.core.firebase_config.is_firebase_available", return_value=True),
        patch("apps.core.firebase_config.get_fcm_client", return_value=Mock()),
        patch("apps.plant_identification.tasks.send_fcm_message") as send,
    ):
        yield send


def _scan(**kwargs):
    """Patch the combined service: no real providers, scan() stubbed."""
    return patch.multiple(
        CombinedPlantIdentificationService,
        __init__=lambda self: None,
        scan=Mock(**kwargs),
    )


def _run(job, capture):
    with capture(execute=True):
        run_scan_job.delay(job.pk)
    job.refresh_from_db()
    return job


@pytest.mark.django_db
def test_done_diagnose_charges_and_notifies_once(
    user, fcm, django_capture_on_commit_callbacks
):
    job = _job(user)
    with _scan(return_value=_results("ok")):
        _run(job, django_capture_on_commit_callbacks)

    assert job.status == "done"
    assert job.charged_as == "diagnose"
    assert job.attempts == 1
    assert job.finished_at is not None
    assert job.notified_at is not None
    assert job.result["plant_name"] == "Fiddle-leaf fig"
    assert job.result["diagnosis"]["state"] == "healthy"
    assert fcm.call_count == 1
    _fcm, token, data, content, collapse_key = fcm.call_args.args
    assert token == TOKEN
    assert data == {
        "event": "scan_job_finished",
        "job_id": str(job.uuid),
        "status": "done",
    }
    assert content[0] == "Your plant check is ready"
    assert collapse_key == "scan-job-finished"
    assert user.onboarding_progress.first_identification_completed is True

    notify_scan_job_finished.delay(job.pk)
    assert fcm.call_count == 1


@pytest.mark.django_db
def test_scan_receives_photo_bytes_by_role(
    user, fcm, django_capture_on_commit_callbacks
):
    job = _job(user, roles=("problem", "whole"))
    with _scan(return_value=_results("ok")):
        _run(job, django_capture_on_commit_callbacks)
        shots, mode = CombinedPlantIdentificationService.scan.call_args.args
    assert mode == "diagnose"
    assert set(shots) == {"problem", "whole"}
    assert all(isinstance(b, bytes) and b[:2] == b"\xff\xd8" for b in shots.values())


@pytest.mark.django_db
def test_failed_retries_once_then_fails(user, fcm, django_capture_on_commit_callbacks):
    job = _job(user)
    with _scan(return_value=_results(suggestions=False)):
        _run(job, django_capture_on_commit_callbacks)
        assert CombinedPlantIdentificationService.scan.call_count == 2

    assert job.attempts == 2
    assert job.status == "failed"
    assert job.charged_as == ""
    assert job.failure_reason == "no_result"
    assert job.result is None
    assert fcm.call_count == 1
    _fcm, _token, data, content, _key = fcm.call_args.args
    assert data["status"] == "failed"
    assert content[0] == "We couldn't check your plant"


@pytest.mark.django_db
def test_degraded_charged_as_identify(user, fcm, django_capture_on_commit_callbacks):
    job = _job(user)
    with _scan(return_value=_results("unavailable")):
        _run(job, django_capture_on_commit_callbacks)

    assert job.status == "degraded"
    assert job.charged_as == "identify"
    assert job.result["diagnosis"]["state"] == "unavailable"
    assert fcm.call_args.args[3][0] == "Your plant check is ready"


@pytest.mark.django_db
def test_unexpected_error_finalizes_failed(
    user, fcm, django_capture_on_commit_callbacks
):
    job = _job(user)
    with _scan(side_effect=RuntimeError("boom")):
        _run(job, django_capture_on_commit_callbacks)

    assert job.status == "failed"
    assert job.failure_reason == "error"
    assert job.charged_as == ""
    assert fcm.call_count == 1


@pytest.mark.django_db
def test_cancel_during_run_wins(user, fcm, django_capture_on_commit_callbacks):
    job = _job(user)

    def cancel_then_answer(shots, mode):
        ScanJob.objects.filter(pk=job.pk).update(status="cancelled")
        return _results("ok")

    with _scan(side_effect=cancel_then_answer):
        _run(job, django_capture_on_commit_callbacks)

    assert job.status == "cancelled"
    assert job.result is None
    assert job.charged_as == ""
    assert job.notified_at is None
    fcm.assert_not_called()


@pytest.mark.django_db
def test_finished_job_is_not_reclaimed(user, fcm, django_capture_on_commit_callbacks):
    job = _job(user)
    ScanJob.objects.filter(pk=job.pk).update(status="done", charged_as="diagnose")
    with _scan(return_value=_results("ok")):
        _run(job, django_capture_on_commit_callbacks)
        CombinedPlantIdentificationService.scan.assert_not_called()
    assert job.attempts == 0


@pytest.mark.django_db
def test_stale_processing_job_expires(user):
    job = _job(user)
    fresh = _job(user)
    ScanJob.objects.filter(pk=job.pk).update(
        status="processing", created_at=timezone.now() - timedelta(minutes=11)
    )

    assert expire_stale_jobs(user.pk) == 1

    job.refresh_from_db()
    fresh.refresh_from_db()
    assert job.status == "failed"
    assert job.failure_reason == "stale"
    assert job.finished_at is not None
    assert fresh.status == "pending"


@pytest.mark.django_db
def test_push_disabled_is_noop(user, django_capture_on_commit_callbacks):
    job = _job(user)
    with (
        patch("apps.core.firebase_config.is_firebase_available", return_value=False),
        patch("apps.plant_identification.tasks.send_fcm_message") as send,
        _scan(return_value=_results("ok")),
    ):
        _run(job, django_capture_on_commit_callbacks)

    assert job.status == "done"
    send.assert_not_called()


@pytest.mark.django_db
def test_dead_token_is_forgotten(user, fcm, django_capture_on_commit_callbacks):
    job = _job(user)
    with (
        patch(
            "apps.plant_identification.tasks.is_permanent_fcm_error",
            return_value=True,
        ),
        patch(
            "apps.plant_identification.tasks.is_dead_fcm_token_error",
            return_value=True,
        ),
        _scan(return_value=_results("ok")),
    ):
        fcm.side_effect = RuntimeError("unregistered")
        _run(job, django_capture_on_commit_callbacks)

    assert not PushDevice.objects.filter(token=TOKEN).exists()


@pytest.mark.django_db
def test_retry_countdown_is_five_seconds(user):
    """``.apply`` ignores countdown, so pin it on a mocked ``retry``."""
    from celery.exceptions import Retry

    job = _job(user)
    run_scan_job.push_request(retries=0)
    try:
        with (
            _scan(return_value=_results(suggestions=False)),
            patch.object(run_scan_job, "retry", side_effect=Retry()) as retry,
            pytest.raises(Retry),
        ):
            run_scan_job.run(job.pk)
    finally:
        run_scan_job.pop_request()
    assert retry.call_args.kwargs["countdown"] == 5
    job.refresh_from_db()
    assert job.status == "processing"  # left for the retry to re-claim


@pytest.mark.django_db
def test_job_out_of_attempts_is_not_reclaimed(
    user, fcm, django_capture_on_commit_callbacks
):
    """A job whose worker keeps dying (acks_late redelivery) is not re-run."""
    job = _job(user)
    ScanJob.objects.filter(pk=job.pk).update(status="processing", attempts=3)
    with _scan(return_value=_results("ok")):
        _run(job, django_capture_on_commit_callbacks)
        CombinedPlantIdentificationService.scan.assert_not_called()
    assert job.attempts == 3
    assert job.status == "processing"  # left for the stale expiry
    fcm.assert_not_called()


@pytest.mark.django_db
def test_error_loading_job_after_claim_finalizes_failed(
    user, fcm, django_capture_on_commit_callbacks
):
    """A failure between the claim and the scan must not leave it processing."""
    job = _job(user)
    with (
        _scan(return_value=_results("ok")),
        patch(
            "apps.plant_identification.tasks._read_shots",
            side_effect=OSError("storage down"),
        ),
    ):
        _run(job, django_capture_on_commit_callbacks)
        CombinedPlantIdentificationService.scan.assert_not_called()
    assert job.status == "failed"
    assert job.failure_reason == "error"
    assert fcm.call_count == 1


@pytest.mark.django_db
def test_error_fetching_job_row_after_claim_finalizes_failed(
    user, fcm, django_capture_on_commit_callbacks
):
    """The job load right after the claim fails once: finalized, not stuck."""
    from django.db.models.query import QuerySet

    job = _job(user)
    real_get = QuerySet.get
    armed = {"on": True}

    def flaky_get(self, *args, **kwargs):
        if self.model is ScanJob and armed["on"]:
            armed["on"] = False
            raise RuntimeError("db blip")
        return real_get(self, *args, **kwargs)

    with (
        _scan(return_value=_results("ok")),
        patch.object(QuerySet, "get", flaky_get),
    ):
        _run(job, django_capture_on_commit_callbacks)
        CombinedPlantIdentificationService.scan.assert_not_called()
    assert armed["on"] is False
    assert job.status == "failed"
    assert job.failure_reason == "error"
