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


# --- Keep / dismiss / remove / undecided list endpoints (3/11) ---------------

from rest_framework.test import APIClient  # noqa: E402

BASE = "/api/v1/plant-identification/scans/"


def _api_job(user, **fields):
    defaults = {
        "user": user,
        "mode": "identify",
        "local_date": timezone.now().date(),
        "status": "done",
        "decision": "undecided",
        "charged_as": "identify",
        "finished_at": timezone.now(),
        "result": {"x": 1},
    }
    defaults.update(fields)
    job = ScanJob.objects.create(**defaults)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 120, 40)).save(buf, "JPEG")
    ScanJobImage.objects.create(
        job=job,
        role="whole",
        image=normalize_scan_photo(ContentFile(buf.getvalue(), name="x.jpg")),
    )
    return job


def _owner(name="decider"):
    return get_user_model().objects.create_user(
        username=name, email=f"{name}@example.com", password="x" * 16
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _url(job, action):
    return f"{BASE}{job.uuid}/{action}/"


@pytest.mark.django_db
def test_keep_sets_kept_and_decided_at(roots):
    user = _owner()
    job = _api_job(user)
    response = _client(user).post(_url(job, "keep"))
    assert response.status_code == 200
    assert response.data["decision"] == "kept"
    job.refresh_from_db()
    assert job.decision == "kept"
    assert job.decided_at is not None


@pytest.mark.django_db
def test_keep_twice_is_200(roots):
    user = _owner()
    job = _api_job(user)
    client = _client(user)
    assert client.post(_url(job, "keep")).status_code == 200
    again = client.post(_url(job, "keep"))
    assert again.status_code == 200
    assert again.data["decision"] == "kept"


@pytest.mark.django_db
def test_keep_after_dismiss_is_404(roots):
    user = _owner()
    job = _api_job(user)
    client = _client(user)
    assert client.post(_url(job, "dismiss")).status_code == 204
    response = client.post(_url(job, "keep"))
    assert response.status_code == 404
    assert response.data["code"] == "not_found"
    job.refresh_from_db()
    assert job.decision == "dismissed"


@pytest.mark.django_db
def test_keep_unfinished_is_409(roots):
    user = _owner()
    job = _api_job(user, status="processing", finished_at=None)
    response = _client(user).post(_url(job, "keep"))
    assert response.status_code == 409
    assert response.data["code"] == "not_undecided"


@pytest.mark.django_db
def test_dismiss_after_keep_is_409(roots):
    user = _owner()
    job = _api_job(user, decision="kept")
    response = _client(user).post(_url(job, "dismiss"))
    assert response.status_code == 409
    assert response.data["code"] == "already_kept"
    job.refresh_from_db()
    assert job.decision == "kept"
    assert job.images.count() == 1


@pytest.mark.django_db
def test_dismiss_twice_is_204(roots):
    user = _owner()
    job = _api_job(user)
    client = _client(user)
    assert client.post(_url(job, "dismiss")).status_code == 204
    assert client.post(_url(job, "dismiss")).status_code == 204


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["dismiss", "remove"])
def test_dismiss_and_remove_processing_job_is_409(roots, action):
    user = _owner()
    job = _api_job(user, status="processing", finished_at=None)
    response = _client(user).post(_url(job, action))
    assert response.status_code == 409
    assert response.data["code"] == "not_finished"
    job.refresh_from_db()
    assert job.decision == "undecided"
    assert job.images.count() == 1


@pytest.mark.django_db
def test_dismiss_degraded_without_retry_keeps_identify_charge(roots):
    user = _owner()
    job = _api_job(user, status="degraded", charged_as="identify", mode="diagnose")
    client = _client(user)
    before = client.get(BASE + "allowance/").data["identify"]["remaining"]
    assert client.post(_url(job, "dismiss")).status_code == 204
    after = client.get(BASE + "allowance/").data["identify"]["remaining"]
    assert after == before
    job.refresh_from_db()
    assert job.charged_as == "identify"


@pytest.mark.django_db
def test_dismiss_leaves_allowance_remaining_unchanged(roots):
    user = _owner()
    job = _api_job(user, mode="diagnose", charged_as="diagnose")
    client = _client(user)
    before = client.get(BASE + "allowance/").data
    assert client.post(_url(job, "dismiss")).status_code == 204
    after = client.get(BASE + "allowance/").data
    assert after["identify"]["remaining"] == before["identify"]["remaining"]
    assert after["diagnose"]["remaining"] == before["diagnose"]["remaining"]


@pytest.mark.django_db
def test_dismissed_job_retrieve_and_photo_404(roots):
    user = _owner()
    job = _api_job(user)
    client = _client(user)
    assert client.post(_url(job, "dismiss")).status_code == 204
    detail = client.get(f"{BASE}{job.uuid}/")
    assert detail.status_code == 404
    assert detail.data["code"] == "not_found"
    photo = client.get(f"{BASE}{job.uuid}/photos/whole/")
    assert photo.status_code == 404


@pytest.mark.django_db
def test_remove_kept_erases_photos(roots, django_capture_on_commit_callbacks):
    user = _owner()
    job = _api_job(user, decision="kept")
    image = job.images.get()
    name, storage = image.image.name, image.image.storage
    assert storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        response = _client(user).post(_url(job, "remove"))
    assert response.status_code == 204
    job.refresh_from_db()
    assert job.decision == "removed"
    assert job.result is None
    assert job.images.count() == 0
    assert not storage.exists(name)


@pytest.mark.django_db
def test_list_undecided_only_own_recent_finished_newest_first(roots):
    user = _owner()
    other = _owner("other")
    now = timezone.now()
    old = _api_job(user, finished_at=now - timedelta(hours=3))
    new = _api_job(user, status="degraded", finished_at=now - timedelta(hours=1))
    _api_job(user, finished_at=now - timedelta(hours=25))  # outside the window
    _api_job(user, decision="kept")
    _api_job(user, decision="dismissed")
    _api_job(user, status="processing", finished_at=None)
    _api_job(other)
    response = _client(user).get(BASE + "?decision=undecided")
    assert response.status_code == 200
    assert [r["id"] for r in response.data] == [str(new.uuid), str(old.uuid)]


@pytest.mark.django_db
@pytest.mark.parametrize("query", ["", "?decision=kept", "?decision="])
def test_list_requires_decision_param(roots, query):
    response = _client(_owner()).get(BASE + query)
    assert response.status_code == 400
    assert response.data["code"] == "invalid"


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["keep", "dismiss", "remove"])
def test_other_users_job_keep_dismiss_remove_404(roots, action):
    owner = _owner()
    job = _api_job(owner)
    response = _client(_owner("intruder")).post(_url(job, action))
    assert response.status_code == 404
    job.refresh_from_db()
    assert job.decision == "undecided"
    assert job.images.count() == 1


# --- Create: new-client header and retry_of (4/11) ---------------------------

from unittest.mock import patch  # noqa: E402

from apps.plant_identification.services.quota_manager import QuotaManager  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402


@pytest.fixture(autouse=False)
def create_env(roots):
    with (
        patch.object(QuotaManager, "can_call_plant_id", return_value=True),
        patch("apps.plant_identification.api.scan_views.validate_image_file"),
        patch("apps.plant_identification.api.scan_views._enqueue_scan_job"),
    ):
        yield


def _upload(name="leaf"):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 120, 40)).save(buf, "JPEG")
    return SimpleUploadedFile(f"{name}.jpg", buf.getvalue(), content_type="image/jpeg")


def _post_create(client, retry_of=None, header=True):
    data = {"mode": "identify", "leaf": _upload()}
    if retry_of is not None:
        data["retry_of"] = str(retry_of)
    extra = {"HTTP_X_SCAN_DECISIONS": "1"} if header else {}
    return client.post(BASE, data, format="multipart", **extra)


@pytest.mark.django_db
def test_create_with_header_starts_undecided(create_env):
    response = _post_create(_client(_owner()))
    assert response.status_code == 201
    assert ScanJob.objects.get(uuid=response.data["id"]).decision == "undecided"


@pytest.mark.django_db
def test_create_without_header_starts_kept(create_env):
    response = _post_create(_client(_owner()), header=False)
    assert response.status_code == 201
    assert ScanJob.objects.get(uuid=response.data["id"]).decision == "kept"


@pytest.mark.django_db
def test_retry_of_degraded_refunds_identify_and_erases(
    create_env, django_capture_on_commit_callbacks
):
    user = _owner()
    job = _api_job(user, status="degraded", charged_as="identify")
    client = _client(user)
    before = client.get(BASE + "allowance/").data["identify"]["remaining"]
    with django_capture_on_commit_callbacks(execute=True):
        response = _post_create(client, retry_of=job.uuid)
    assert response.status_code == 201
    job.refresh_from_db()
    assert job.decision == "dismissed"
    assert job.charged_as == ""
    assert ScanJobImage.objects.filter(job=job).count() == 0
    # The new scan holds one slot, the degraded one was refunded: net zero,
    # where a create without retry_of would have lowered it by one.
    after = client.get(BASE + "allowance/").data["identify"]["remaining"]
    assert after == before


@pytest.mark.django_db
def test_create_without_retry_lowers_remaining(create_env):
    user = _owner()
    _api_job(user, status="degraded", charged_as="identify")
    client = _client(user)
    before = client.get(BASE + "allowance/").data["identify"]["remaining"]
    assert _post_create(client).status_code == 201
    after = client.get(BASE + "allowance/").data["identify"]["remaining"]
    assert after == before - 1


@pytest.mark.django_db
def test_retry_of_done_job_ignored(create_env):
    user = _owner()
    job = _api_job(user, status="done")
    response = _post_create(_client(user), retry_of=job.uuid)
    assert response.status_code == 201
    job.refresh_from_db()
    assert job.decision == "undecided"
    assert job.charged_as == "identify"
    assert ScanJobImage.objects.filter(job=job).count() == 1


@pytest.mark.django_db
def test_retry_of_already_decided_degraded_ignored(create_env):
    user = _owner()
    job = _api_job(user, status="degraded", decision="kept")
    assert _post_create(_client(user), retry_of=job.uuid).status_code == 201
    job.refresh_from_db()
    assert job.decision == "kept"
    assert job.charged_as == "identify"


@pytest.mark.django_db
def test_retry_of_other_users_job_ignored(create_env):
    other = _owner("other")
    job = _api_job(other, status="degraded", charged_as="identify")
    response = _post_create(_client(_owner()), retry_of=job.uuid)
    assert response.status_code == 201
    job.refresh_from_db()
    assert job.decision == "undecided"
    assert job.charged_as == "identify"
    assert ScanJobImage.objects.filter(job=job).count() == 1


@pytest.mark.django_db
def test_retry_of_garbage_ignored_201(create_env):
    response = _post_create(_client(_owner()), retry_of="not-a-uuid")
    assert response.status_code == 201
