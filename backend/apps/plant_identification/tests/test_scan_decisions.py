"""The scan decision fields and their serializer output (keep-or-dismiss, 1/11)."""

from datetime import timedelta

import pytest
from apps.plant_identification.api.scan_serializers import ScanJobSerializer
from apps.plant_identification.constants import SCAN_DECISION_WINDOW_HOURS
from apps.plant_identification.scan_models import ScanJob
from django.contrib.auth import get_user_model
from django.utils import timezone
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
