"""Policy-consent helpers: strict boolean check, server-stamped acceptance, 428."""

import datetime

import pytest
from apps.users.consent import (
    ConsentRequired,
    consent_required_response,
    is_accepted,
    record_policy_acceptance,
)
from apps.users.constants import (
    CONSENT_REQUIRED_CODE,
    CONSENT_REQUIRED_MESSAGE,
    LEGAL_POLICY_VERSION,
)
from django.contrib.auth import get_user_model
from freezegun import freeze_time

User = get_user_model()


@pytest.mark.parametrize(
    "value, expected",
    [(True, True), ("true", False), (1, False), (None, False), (False, False)],
)
def test_is_accepted_only_true(value, expected):
    assert is_accepted(value) is expected


@pytest.mark.django_db
def test_record_policy_acceptance_stamps_server_version():
    user = User.objects.create_user(username="consent1", password="x-Pass-12345")
    with freeze_time("2026-11-07 12:00:00"):
        record_policy_acceptance(user)
    user.refresh_from_db()
    assert user.policy_version_accepted == LEGAL_POLICY_VERSION == "2026-11-06"
    assert user.policy_accepted_at == datetime.datetime(
        2026, 11, 7, 12, 0, 0, tzinfo=datetime.timezone.utc
    )


@pytest.mark.django_db
def test_existing_users_have_null_acceptance():
    user = User.objects.create_user(username="consent2", password="x-Pass-12345")
    assert user.policy_version_accepted is None
    assert user.policy_accepted_at is None


def test_consent_required_response():
    response = consent_required_response()
    assert response.status_code == 428
    assert response.data == {
        "error": CONSENT_REQUIRED_MESSAGE,
        "code": CONSENT_REQUIRED_CODE,
    }
    assert CONSENT_REQUIRED_CODE == "consent_required"


def test_consent_required_is_exception():
    assert issubclass(ConsentRequired, Exception)
