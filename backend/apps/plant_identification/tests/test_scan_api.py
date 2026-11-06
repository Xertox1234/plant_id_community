"""The Scan 2.0 job API: allowance, create, status, cancel, photos (B4).

``run_scan_job.delay`` runs inline (tests/conftest.py), but only from an
on_commit callback, which never fires inside a ``django_db`` test transaction.
So in these tests a created job stays ``pending`` (active) until a test
finalizes it by hand, except in the TransactionTestCase-style test below.
"""

import io
import threading
from datetime import date, datetime
from datetime import timezone as dt_timezone
from unittest.mock import Mock, patch

import pytest
from apps.plant_identification.scan_jobs import local_date_for
from apps.plant_identification.scan_models import ScanJob, ScanJobImage
from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
)
from apps.plant_identification.services.quota_manager import QuotaManager
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from freezegun import freeze_time
from PIL import Image
from rest_framework.test import APIClient

BASE = "/api/v1/plant-identification/scans/"


def _jpeg(color=(40, 120, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, "JPEG")
    return buf.getvalue()


def _file(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(f"{name}.jpg", _jpeg(), content_type="image/jpeg")


@pytest.fixture(autouse=True)
def roots(tmp_path):
    media = tmp_path / "media"
    private = tmp_path / "private"
    media.mkdir()
    private.mkdir()
    with override_settings(MEDIA_ROOT=str(media), SCAN_PHOTO_LOCAL_ROOT=str(private)):
        yield


@pytest.fixture(autouse=True)
def no_real_checks():
    """No shared-Redis quota reads, no magic-byte checks: deterministic."""
    with (
        patch.object(QuotaManager, "can_call_plant_id", return_value=True),
        patch("apps.plant_identification.api.scan_views.validate_image_file"),
    ):
        yield


def _user(name="scanner", premium=False):
    return get_user_model().objects.create_user(
        username=name,
        email=f"{name}@example.com",
        password="x" * 16,
        is_premium=premium,
    )


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _create(client, mode="diagnose", roles=None, offset=None):
    roles = roles or (("problem", "leaf") if mode == "diagnose" else ("leaf",))
    data = {"mode": mode, **{role: _file(role) for role in roles}}
    if offset is not None:
        data["utc_offset_minutes"] = str(offset)
    return client.post(BASE, data, format="multipart")


def _finish(response, status="done", charged_as=None):
    """Finalize the job a create returned, as the worker would."""
    job = ScanJob.objects.get(uuid=response.data["id"])
    if charged_as is None:
        charged_as = job.mode if status == "done" else ""
    ScanJob.objects.filter(pk=job.pk).update(status=status, charged_as=charged_as)
    return job


@pytest.mark.django_db
def test_create_diagnose_requires_problem_photo():
    response = _create(_client(_user()), "diagnose", roles=("leaf", "whole"))
    assert response.status_code == 400
    assert response.data["code"] == "invalid"
    assert not ScanJob.objects.exists()


@pytest.mark.django_db
def test_create_identify_requires_leaf_photo():
    response = _create(_client(_user()), "identify", roles=("whole",))
    assert response.status_code == 400
    assert response.data["code"] == "invalid"


@pytest.mark.django_db
def test_create_rejects_role_not_in_mode():
    response = _create(_client(_user()), "identify", roles=("leaf", "problem"))
    assert response.status_code == 400
    assert response.data["code"] == "invalid"
    assert not ScanJob.objects.exists()


@pytest.mark.django_db
def test_create_rejects_oversized_photo():
    big = SimpleUploadedFile(
        "leaf.jpg", b"\xff\xd8" + b"0" * (10 * 1024 * 1024), content_type="image/jpeg"
    )
    response = _client(_user()).post(
        BASE, {"mode": "identify", "leaf": big}, format="multipart"
    )
    assert response.status_code == 400
    assert response.data["code"] == "invalid"


@pytest.mark.django_db
def test_create_returns_job_and_stores_reencoded_photos():
    user = _user()
    response = _create(_client(user), "diagnose", roles=("problem", "whole"))
    assert response.status_code == 201
    body = response.data
    assert body["mode"] == "diagnose"
    assert body["status"] == "pending"
    assert body["result"] is None
    assert set(body["photos"]) == {"problem", "whole"}
    assert body["photos"]["whole"].startswith("http://testserver" + BASE)
    assert body["cover_photo"] == body["photos"]["whole"]
    job = ScanJob.objects.get(uuid=body["id"])
    assert job.user == user
    assert {i.role for i in job.images.all()} == {"problem", "whole"}


@pytest.mark.django_db
def test_free_user_second_diagnosis_same_day_429():
    client = _client(_user())
    first = _create(client)
    assert first.status_code == 201
    _finish(first, "done", "diagnose")

    second = _create(client)
    assert second.status_code == 429
    assert second.data["code"] == "allowance_exhausted"
    assert second.data["kind"] == "diagnose"
    assert second.data["limit"] == 1
    assert second.data["resets_at"].endswith("Z")


@pytest.mark.django_db
def test_identify_allowance_separate_from_diagnose():
    client = _client(_user())
    _finish(_create(client), "done", "diagnose")
    response = _create(client, "identify")
    assert response.status_code == 201


@pytest.mark.django_db
def test_premium_gets_three():
    client = _client(_user(premium=True))
    for _ in range(3):
        response = _create(client)
        assert response.status_code == 201
        _finish(response, "done", "diagnose")
    fourth = _create(client)
    assert fourth.status_code == 429
    assert fourth.data["code"] == "allowance_exhausted"
    assert fourth.data["limit"] == 3


@pytest.mark.django_db
def test_failed_and_cancelled_do_not_count():
    client = _client(_user())
    _finish(_create(client), "failed")
    _finish(_create(client), "cancelled")
    allowance = client.get(BASE + "allowance/").data
    assert allowance["diagnose"]["used"] == 0
    assert _create(client).status_code == 201


@pytest.mark.django_db
def test_degraded_counts_as_identify():
    client = _client(_user())
    _finish(_create(client), "degraded", "identify")
    allowance = client.get(BASE + "allowance/").data
    assert allowance["diagnose"]["used"] == 0
    assert allowance["identify"]["used"] == 1


@pytest.mark.django_db
def test_active_job_reserves_its_slot():
    client = _client(_user())
    _create(client)
    allowance = client.get(BASE + "allowance/").data
    assert allowance["diagnose"] == {"limit": 1, "used": 1, "remaining": 0}


@pytest.mark.django_db
def test_offset_is_recorded_but_cannot_reach_a_second_day():
    """M1: flipping utc_offset_minutes used to land on another local date
    with a fresh slot; the rolling window is the same at every offset."""
    client = _client(_user())
    with freeze_time("2026-11-02T23:30:00Z"):
        response = _create(client, offset=60)
        assert response.status_code == 201
        job = _finish(response, "done", "diagnose")
        job.refresh_from_db()
        assert job.local_date == date(2026, 11, 3)
        assert job.utc_offset_minutes == 60
        for offset in (-840, 0, 840):
            allowance = client.get(
                BASE + f"allowance/?utc_offset_minutes={offset}"
            ).data
            assert allowance["diagnose"]["used"] == 1
            assert _create(client, offset=offset).status_code == 429


@pytest.mark.django_db
def test_slot_comes_back_24_hours_after_the_scan():
    client = _client(_user())
    with freeze_time("2026-11-02T10:00:00Z"):
        _finish(_create(client), "done", "diagnose")
    with freeze_time("2026-11-03T09:59:00Z"):
        refused = _create(client)
        assert refused.status_code == 429
        assert refused.data["resets_at"] == "2026-11-03T10:00:00Z"
        assert client.get(BASE + "allowance/").data["resets_at"] == (
            "2026-11-03T10:00:00Z"
        )
    with freeze_time("2026-11-03T10:00:01Z"):
        assert _create(client).status_code == 201


@pytest.mark.django_db
def test_exhausted_identify_429_carries_identify_reset():
    client = _client(_user())
    with freeze_time("2026-11-02T08:00:00Z"):
        for _ in range(5):
            _finish(_create(client, "identify"), "done", "identify")
    with freeze_time("2026-11-02T12:00:00Z"):
        refused = _create(client, "identify")
    assert refused.status_code == 429
    assert refused.data["kind"] == "identify"
    assert refused.data["resets_at"] == "2026-11-03T08:00:00Z"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("60", date(2026, 11, 3)),
        ("-840", date(2026, 11, 2)),
        ("5000", date(2026, 11, 3)),  # clamped to +840
        ("abc", date(2026, 11, 2)),  # invalid means UTC
        (None, date(2026, 11, 2)),
    ],
)
def test_local_date_for_clamps_and_defaults(raw, expected):
    with freeze_time("2026-11-02T23:30:00Z"):
        assert local_date_for(raw) == expected


@pytest.mark.django_db
def test_one_active_job_409_with_job_id():
    client = _client(_user())
    first = _create(client)
    second = _create(client, "identify")
    assert second.status_code == 409
    assert second.data["code"] == "scan_in_progress"
    assert second.data["job_id"] == str(first.data["id"])


@pytest.mark.django_db
def test_stale_active_job_is_expired_on_create():
    client = _client(_user())
    first = _create(client)
    with freeze_time(datetime.now(dt_timezone.utc).replace(microsecond=0)) as frozen:
        frozen.tick(60 * 11)
        second = _create(client, "identify")
    assert second.status_code == 201
    assert ScanJob.objects.get(uuid=first.data["id"]).status == "failed"


@pytest.mark.django_db
def test_plant_id_busy_blocks_diagnose_not_identify():
    client = _client(_user())
    with patch.object(QuotaManager, "can_call_plant_id", return_value=False):
        diagnose = _create(client)
        assert diagnose.status_code == 503
        assert diagnose.data["code"] == "plant_id_busy"
        identify = _create(client, "identify")
    assert identify.status_code == 201


@pytest.mark.django_db
def test_other_users_job_and_photo_404():
    owner = _client(_user("owner"))
    job_id = _create(owner).data["id"]
    other = _client(_user("other"))
    responses = [
        other.get(f"{BASE}{job_id}/"),
        other.get(f"{BASE}{job_id}/photos/problem/"),
        other.post(f"{BASE}{job_id}/cancel/"),
    ]
    for response in responses:
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
    assert ScanJob.objects.get(uuid=job_id).status == "pending"


@pytest.mark.django_db
def test_foreign_and_missing_job_404_bodies_match():
    """No existence leak: another user's job reads exactly like a missing one."""
    owner = _client(_user("owner"))
    job_id = _create(owner).data["id"]
    other = _client(_user("other"))
    missing_id = "00000000-0000-4000-8000-000000000000"

    def body(path):
        data = path.json()
        data.pop("request_id", None)
        return data

    foreign = other.get(f"{BASE}{job_id}/")
    missing = other.get(f"{BASE}{missing_id}/")
    assert foreign.status_code == missing.status_code == 404
    assert body(foreign) == body(missing)
    assert body(foreign)["code"] == "not_found"


@pytest.mark.django_db
def test_refused_enqueue_fails_the_job_and_frees_the_slot(
    django_capture_on_commit_callbacks,
):
    """A broker refusal after commit never 500s and never locks the user out."""
    client = _client(_user())
    with patch(
        "apps.plant_identification.api.scan_views.run_scan_job.delay",
        side_effect=ConnectionError("broker down"),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            first = _create(client)
    assert first.status_code == 201
    job = ScanJob.objects.get(uuid=first.data["id"])
    assert job.status == "failed"
    assert job.failure_reason == "enqueue"
    assert job.finished_at is not None
    assert job.charged_as == ""

    with patch("apps.plant_identification.api.scan_views.run_scan_job.delay"):
        retry = _create(client)
    assert retry.status_code == 201
    assert retry.data["id"] != first.data["id"]


@pytest.mark.django_db
def test_enqueue_failure_never_overwrites_a_job_that_moved_on():
    from apps.plant_identification.api.scan_views import _enqueue_scan_job

    client = _client(_user())
    job = ScanJob.objects.get(uuid=_create(client).data["id"])
    ScanJob.objects.filter(pk=job.pk).update(status="processing")
    with patch(
        "apps.plant_identification.api.scan_views.run_scan_job.delay",
        side_effect=ConnectionError("broker down"),
    ):
        _enqueue_scan_job(job.pk)
    job.refresh_from_db()
    assert job.status == "processing"
    assert job.failure_reason == ""


@pytest.mark.django_db
def test_unauthenticated_is_refused():
    client = APIClient()
    assert client.get(BASE + "allowance/").status_code == 401
    assert client.post(BASE, {"mode": "identify"}).status_code == 401


@pytest.mark.django_db
def test_photo_streams_bytes_private_cache_header():
    client = _client(_user())
    job_id = _create(client).data["id"]
    response = client.get(f"{BASE}{job_id}/photos/problem/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert response["Cache-Control"] == "private, max-age=86400"
    body = b"".join(response.streaming_content)
    assert body[:2] == b"\xff\xd8"
    assert client.get(f"{BASE}{job_id}/photos/flower/").status_code == 404


@pytest.mark.django_db
def test_retrieve_returns_job():
    client = _client(_user())
    created = _create(client)
    _finish(created, "done", "diagnose")
    ScanJob.objects.filter(uuid=created.data["id"]).update(result={"plant_name": "Fig"})
    response = client.get(f"{BASE}{created.data['id']}/")
    assert response.status_code == 200
    assert response.data["status"] == "done"
    assert response.data["charged_as"] == "diagnose"
    assert response.data["result"] == {"plant_name": "Fig"}


@pytest.mark.django_db
def test_allowance_shape():
    client = _client(_user())
    with freeze_time("2026-11-02T23:30:00Z"):
        response = client.get(BASE + "allowance/?utc_offset_minutes=60")
    assert response.status_code == 200
    body = response.data
    assert set(body) == {
        "is_premium",
        "diagnose",
        "identify",
        "resets_at",
        "plant_id_available",
        "slow_after_seconds",
        "premium_diagnose_limit",
    }
    assert body["is_premium"] is False
    assert body["diagnose"] == {"limit": 1, "used": 0, "remaining": 1}
    assert body["identify"] == {"limit": 5, "used": 0, "remaining": 5}
    # Nothing counted: a diagnosis is available now (rolling window, M1).
    assert body["resets_at"] == "2026-11-02T23:30:00Z"
    assert body["plant_id_available"] is True
    assert body["slow_after_seconds"] == 45
    assert body["premium_diagnose_limit"] == 3


@pytest.mark.django_db
def test_cancel_active_then_409_on_second_cancel():
    client = _client(_user())
    job_id = _create(client).data["id"]
    first = client.post(f"{BASE}{job_id}/cancel/")
    assert first.status_code == 200
    assert first.data["status"] == "cancelled"
    assert first.data["finished_at"] is not None
    second = client.post(f"{BASE}{job_id}/cancel/")
    assert second.status_code == 409
    assert second.data["code"] == "not_active"


@pytest.mark.django_db
def test_ratelimit_returns_429_rate_limit_exceeded_distinct_code():
    client = _client(_user())
    with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
        response = _create(client)
    assert response.status_code == 429
    assert response.data["code"] == "rate_limit_exceeded"
    assert response["Retry-After"] == "3600"
    assert not ScanJob.objects.exists()


def _in_own_connection(fn):
    """Run ``fn`` in a fresh thread, so on its own autocommitted connection."""
    out = {}

    def target():
        try:
            out["value"] = fn()
        finally:
            connection.close()

    t = threading.Thread(target=target)
    t.start()
    t.join(timeout=30)
    return out.get("value")


@pytest.mark.django_db
def test_concurrent_last_slot_single_winner():
    """Two simultaneous creates for a free user's last slot: one wins.

    The race needs real commits on separate connections, but
    ``django_db(transaction=True)`` is banned here: its teardown flush wipes
    Wagtail's seeded rows (docs/rules/testing.md). So every row this test
    touches is written and removed by worker threads on their own
    autocommitted connections; the test's own transaction stays empty. The job
    runs on commit (conftest) with the providers stubbed.
    """
    name = "racer-concurrency"
    user = _in_own_connection(lambda: _user(name))
    barrier = threading.Barrier(2)
    statuses = []
    errors = []

    def post():
        try:
            client = _client(user)
            data = {"mode": "diagnose", "problem": _file("problem")}
            barrier.wait(timeout=10)
            statuses.append(client.post(BASE, data, format="multipart").status_code)
        except Exception as exc:  # surfaced below, not swallowed
            errors.append(exc)
        finally:
            connection.close()

    done = {
        "combined_suggestions": [
            {"plant_name": "Fig", "scientific_name": "Ficus", "probability": 0.9}
        ],
        "confidence_score": 0.9,
        "disease_detection": None,
        "disease_detection_status": "ok",
    }
    try:
        with (
            patch.multiple(
                CombinedPlantIdentificationService,
                __init__=lambda self: None,
                scan=Mock(return_value=done),
            ),
            patch("apps.plant_identification.tasks.notify_scan_job_finished"),
        ):
            threads = [threading.Thread(target=post) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)
        jobs = _in_own_connection(
            lambda: list(
                ScanJob.objects.filter(user_id=user.pk).values_list("status", flat=True)
            )
        )
    finally:
        _in_own_connection(
            lambda: get_user_model().objects.filter(username=name).delete()
        )

    assert not errors, errors
    assert len(statuses) == 2
    assert statuses.count(201) == 1
    assert sorted(statuses)[1] in (409, 429)
    assert jobs == ["done"]


def test_schema_generation_queryset_is_empty_without_a_user():
    """drf-spectacular builds the view with no request user."""
    from apps.plant_identification.api.scan_views import ScanJobViewSet

    view = ScanJobViewSet()
    view.swagger_fake_view = True
    assert view.get_queryset().model is ScanJob
    assert view.get_queryset().query.is_empty()


@pytest.mark.django_db
def test_create_rejects_photo_over_pixel_cap():
    with patch("apps.plant_identification.scan_storage.MAX_SCAN_PHOTO_PIXELS", 100):
        response = _create(_client(_user()), "identify")
    assert response.status_code == 400
    assert response.data["code"] == "invalid"
    assert not ScanJob.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("accept", ["image/*", "image/jpeg", "image/webp,image/*"])
def test_photo_accepts_image_accept_headers(accept):
    client = _client(_user())
    job_id = _create(client).data["id"]
    response = client.get(f"{BASE}{job_id}/photos/problem/", HTTP_ACCEPT=accept)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert b"".join(response.streaming_content)[:2] == b"\xff\xd8"


@pytest.mark.django_db
@pytest.mark.parametrize("accept", ["image/*", "image/jpeg"])
def test_photo_404s_stay_404_with_image_accept(accept):
    owner = _client(_user("owner"))
    job_id = _create(owner).data["id"]
    missing = owner.get(f"{BASE}{job_id}/photos/flower/", HTTP_ACCEPT=accept)
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    other = _client(_user("other"))
    foreign = other.get(f"{BASE}{job_id}/photos/problem/", HTTP_ACCEPT=accept)
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "not_found"


@pytest.mark.django_db
def test_exhausted_user_forces_no_photo_decode():
    """M5: the unlocked pre-check refuses before any PIL decode/re-encode."""
    client = _client(_user())
    _finish(_create(client), "done", "diagnose")
    with patch(
        "apps.plant_identification.api.scan_views.normalize_scan_photo"
    ) as normalize:
        refused = _create(client)
    assert refused.status_code == 429
    normalize.assert_not_called()


@pytest.mark.django_db
def test_failed_photo_save_leaves_no_orphaned_file(roots, tmp_path):
    """M5: a rolled-back create deletes the photos it already wrote."""
    real_create = ScanJobImage.objects.create
    calls = []

    def create_then_fail(**kwargs):
        calls.append(kwargs["role"])
        if len(calls) == 2:
            raise RuntimeError("storage hiccup")
        return real_create(**kwargs)

    client = _client(_user())
    client.raise_request_exception = False
    with patch(
        "apps.plant_identification.api.scan_views.ScanJobImage.objects.create",
        side_effect=create_then_fail,
    ):
        response = _create(client)

    assert response.status_code == 500
    assert len(calls) == 2
    assert not ScanJob.objects.exists()
    assert not ScanJobImage.objects.exists()
    written = [p for p in (tmp_path / "private").rglob("*") if p.is_file()]
    assert written == []


@pytest.mark.django_db
def test_invalid_mode_is_400_even_with_an_active_job():
    client = _client(_user())
    assert _create(client).status_code == 201
    response = client.post(BASE, {"mode": "bogus"}, format="multipart")
    assert response.status_code == 400
    assert "mode" in response.data["errors"]


@pytest.mark.django_db
def test_photo_whose_object_is_gone_is_404_not_500(tmp_path):
    """L1: a row whose stored object was deleted answers the documented 404."""
    client = _client(_user())
    job_id = _create(client).data["id"]
    for path in (tmp_path / "private").rglob("problem.jpg"):
        path.unlink()
    response = client.get(f"{BASE}{job_id}/photos/problem/")
    assert response.status_code == 404
    assert response.data["code"] == "not_found"


@pytest.mark.django_db
def test_spoofed_photo_400_names_its_role():
    """L4 (and the L6 gap): the real validate_image_file, end to end."""
    client = _client(_user())
    fake = SimpleUploadedFile("leaf.jpg", b"not an image", content_type="image/jpeg")
    with patch(
        "apps.plant_identification.api.scan_views.validate_image_file",
        wraps=__import__(
            "apps.plant_identification.utils", fromlist=["validate_image_file"]
        ).validate_image_file,
    ):
        response = client.post(
            BASE,
            {"mode": "diagnose", "problem": _file("problem"), "leaf": fake},
            format="multipart",
        )
    assert response.status_code == 400
    assert response.data["code"] == "invalid"
    assert set(response.data["errors"]) == {"leaf"}
    assert not ScanJob.objects.exists()


@pytest.mark.django_db
def test_retrieve_and_photo_query_counts_are_pinned(django_assert_num_queries):
    """L8: retrieve and the photo stream reuse get_object's prefetch."""
    client = _client(_user())
    job_id = _create(client).data["id"]
    # retrieve: stale expiry SELECT, job SELECT, images prefetch.
    with django_assert_num_queries(3):
        assert client.get(f"{BASE}{job_id}/").status_code == 200
    # photo: job SELECT, images prefetch.
    with django_assert_num_queries(2):
        response = client.get(f"{BASE}{job_id}/photos/problem/")
        assert response.status_code == 200
