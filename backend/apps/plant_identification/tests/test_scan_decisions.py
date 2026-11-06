"""The scan decision fields and their serializer output (keep-or-dismiss, 1/11)."""

import io
from datetime import timedelta

import pytest
from apps.plant_identification.api.scan_serializers import ScanJobSerializer
from apps.plant_identification.constants import SCAN_DECISION_WINDOW_HOURS
from apps.plant_identification.scan_jobs import erase_scan
from apps.plant_identification.scan_models import ScanJob, ScanJobImage
from apps.plant_identification.scan_storage import normalize_scan_photo
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIRequestFactory


def _job(**fields):
    user = get_user_model().objects.create_user(
        username="decider", email="decider@example.com", password="x" * 16
    )
    defaults = {
        "user": user,
        "mode": "identify",
        "local_date": timezone.now().date(),
    }
    defaults.update(fields)
    return ScanJob.objects.create(**defaults)


def _data(job):
    request = APIRequestFactory().get("/")
    return ScanJobSerializer(job, context={"request": request}).data


def test_window_constant_is_24_hours():
    assert SCAN_DECISION_WINDOW_HOURS == 24


@pytest.mark.django_db
def test_new_job_defaults_to_kept():
    job = _job()
    assert job.decision == "kept"
    assert job.decided_at is None


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["done", "degraded"])
def test_decide_by_is_finished_plus_24h_for_undecided_done(status):
    finished = timezone.now()
    job = _job(status=status, decision="undecided", finished_at=finished)
    data = _data(job)
    assert data["decision"] == "undecided"
    expected = finished + timedelta(hours=24)
    assert data["decide_by"] == expected.isoformat().replace("+00:00", "Z")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,decision",
    [
        ("done", "kept"),
        ("done", "dismissed"),
        ("failed", "undecided"),
        ("cancelled", "undecided"),
        ("pending", "undecided"),
    ],
)
def test_decide_by_null_when_kept_or_failed(status, decision):
    job = _job(status=status, decision=decision, finished_at=timezone.now())
    assert _data(job)["decide_by"] is None


@pytest.mark.django_db
def test_decide_by_null_without_finished_at():
    job = _job(status="done", decision="undecided", finished_at=None)
    assert _data(job)["decide_by"] is None


def test_erased_decisions():
    assert ScanJob.ERASED_DECISIONS == ("dismissed", "expired", "removed")
    assert [c for c, _ in ScanJob.DECISION_CHOICES] == [
        "undecided",
        "kept",
        "dismissed",
        "expired",
        "removed",
    ]


@pytest.fixture
def roots(tmp_path):
    media = tmp_path / "media"
    private = tmp_path / "private"
    media.mkdir()
    private.mkdir()
    with override_settings(MEDIA_ROOT=str(media), SCAN_PHOTO_LOCAL_ROOT=str(private)):
        yield


def _photo_job(**fields):
    job = _job(**fields)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 120, 40)).save(buf, "JPEG")
    image = ScanJobImage.objects.create(
        job=job,
        role="leaf",
        image=normalize_scan_photo(ContentFile(buf.getvalue(), name="x.jpg")),
    )
    return job, image.image.name, image.image.storage


@pytest.mark.django_db
def test_erase_deletes_rows_files_and_result_keeps_charge(
    roots, django_capture_on_commit_callbacks
):
    job, name, storage = _photo_job(
        status="done",
        decision="undecided",
        charged_as="diagnose",
        result={"x": 1},
    )
    assert storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        assert erase_scan(job.pk, "dismissed", from_decisions=("undecided",)) is True
    job.refresh_from_db()
    assert ScanJobImage.objects.filter(job=job).count() == 0
    assert not storage.exists(name)
    assert job.result is None
    assert job.decision == "dismissed"
    assert job.decided_at is not None
    assert job.status == "done"
    assert job.charged_as == "diagnose"


@pytest.mark.django_db
def test_erase_refund_clears_charge(roots, django_capture_on_commit_callbacks):
    job, _, _ = _photo_job(status="done", decision="undecided", charged_as="diagnose")
    with django_capture_on_commit_callbacks(execute=True):
        assert (
            erase_scan(job.pk, "dismissed", from_decisions=("undecided",), refund=True)
            is True
        )
    job.refresh_from_db()
    assert job.charged_as == ""


@pytest.mark.django_db
def test_erase_from_wrong_decision_is_noop(roots, django_capture_on_commit_callbacks):
    job, name, storage = _photo_job(
        status="done", decision="kept", charged_as="diagnose", result={"x": 1}
    )
    with django_capture_on_commit_callbacks(execute=True):
        assert erase_scan(job.pk, "dismissed", from_decisions=("undecided",)) is False
    job.refresh_from_db()
    assert ScanJobImage.objects.filter(job=job).count() == 1
    assert storage.exists(name)
    assert job.decision == "kept"
    assert job.result == {"x": 1}
