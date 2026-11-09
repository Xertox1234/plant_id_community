"""DeletedAccount record and blocked re-sign-up (Plan B task 1)."""

import time
from unittest.mock import patch

import pytest
from apps.users import oauth_views
from apps.users.deletion import (
    SignupBlocked,
    email_hash,
    is_signup_blocked,
    signup_blocked_response,
)
from apps.users.models import DeletedAccount
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

User = get_user_model()

BLOCKED = "Blocked@Example.com"


def _deleted(email, reason, uid):
    return DeletedAccount.objects.create(
        user_id=uid, email_hash=email_hash(email), reason=reason
    )


@pytest.mark.django_db
def test_email_hash_matches_real_suppression_row():
    from apps.core.email_feedback import _suppress
    from apps.core.models import EmailSuppression

    _suppress([" Foo@Example.com "], EmailSuppression.Reason.HARD_BOUNCE, "svix-1")
    stored = EmailSuppression.objects.get().address_hash
    assert email_hash(" Foo@Example.com ") == stored
    assert email_hash("foo@example.com") == stored


@pytest.mark.django_db
@pytest.mark.parametrize(
    "reason, blocked",
    [("abuse", True), ("under_13", True), ("self", False), ("staff", False)],
)
def test_is_signup_blocked_by_reason(reason, blocked):
    _deleted("a@example.com", reason, 1)
    assert is_signup_blocked("A@example.com") is blocked
    assert is_signup_blocked("other@example.com") is False


def test_signup_blocked_response_shape():
    r = signup_blocked_response()
    assert r.status_code == 403
    assert r.data == {
        "error": "This email address can't be used to create an account.",
        "code": "signup_blocked",
    }
    assert issubclass(SignupBlocked, Exception)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.mark.django_db
def test_register_blocked_is_403_not_428(client):
    _deleted(BLOCKED, "abuse", 2)
    token = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
    r = client.post(
        "/api/v1/auth/register/",
        data={
            "username": "blockeduser",
            "email": BLOCKED,
            "password": "TestPassword123!",  # pragma: allowlist secret
            "confirmPassword": "TestPassword123!",  # pragma: allowlist secret
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert r.status_code == 403
    assert r.json()["code"] == "signup_blocked"
    assert not User.objects.filter(username="blockeduser").exists()


@pytest.mark.django_db
@patch("apps.users.firebase_auth_views.firebase_auth.verify_id_token")
def test_token_exchange_new_uid_blocked(mock_verify, client):
    _deleted(BLOCKED, "under_13", 3)
    mock_verify.return_value = {
        "uid": "new-uid-1",
        "email": BLOCKED,
        "email_verified": True,
    }
    r = client.post(
        reverse("v1:users:firebase_token_exchange"),
        {"firebase_token": "tok"},
        content_type="application/json",
    )
    assert r.status_code == 403
    assert r.json()["code"] == "signup_blocked"
    assert User.objects.count() == 0


@pytest.mark.django_db
@patch("apps.users.firebase_auth_views.firebase_auth.verify_id_token")
def test_token_exchange_existing_user_on_list_still_signs_in(mock_verify, client):
    from apps.users.email_verification import mark_email_verified

    user = User.objects.create_user(
        username="old", email=BLOCKED, firebase_uid="old-uid"
    )
    mark_email_verified(user)
    _deleted(BLOCKED, "abuse", 4)
    mock_verify.return_value = {
        "uid": "old-uid",
        "email": BLOCKED,
        "email_verified": True,
    }
    r = client.post(
        reverse("v1:users:firebase_token_exchange"),
        {"firebase_token": "tok"},
        content_type="application/json",
    )
    assert r.status_code == 200


@pytest.mark.django_db
@patch("apps.users.firebase_auth_views.firebase_auth.verify_id_token")
def test_token_exchange_refused_while_a_deletion_holds_the_uid(mock_verify, client):
    """Between the django and firebase_auth steps the login still exists but
    the account does not: a sign-in must not create a fresh account."""
    DeletedAccount.objects.create(
        user_id=5,
        email="leaving@example.com",
        email_hash=email_hash("leaving@example.com"),
        firebase_uid="doomed-uid",
        reason="self",
        status="pending",
    )
    mock_verify.return_value = {
        "uid": "doomed-uid",
        "email": "leaving@example.com",
        "email_verified": True,
    }
    r = client.post(
        reverse("v1:users:firebase_token_exchange"),
        {"firebase_token": "tok", "accepted_terms": True},
        content_type="application/json",
    )
    assert r.status_code == 401
    assert r.json() == {"error": "Invalid Firebase token"}
    assert User.objects.count() == 0

    # Once the deletion is done, the uid is free again (the record clears it).
    DeletedAccount.objects.update(status="done", firebase_uid="")
    r = client.post(
        reverse("v1:users:firebase_token_exchange"),
        {"firebase_token": "tok", "accepted_terms": True},
        content_type="application/json",
    )
    assert r.status_code == 200


GOOGLE = {"id": "g-1", "email": BLOCKED, "given_name": "B", "family_name": "L"}


def _callback(client, accepted=False):
    session = client.session
    session["oauth_state"] = "test-state"
    if accepted:
        session["oauth_accepted_terms"] = True
    session.save()
    with patch.object(
        oauth_views, "_handle_google_callback", return_value=dict(GOOGLE)
    ):
        return client.get(
            reverse("v1:users:oauth_callback", kwargs={"provider": "google"}),
            {"code": "abc", "state": "test-state"},
        )


@pytest.mark.django_db
def test_oauth_callback_blocked_redirects_with_error(client):
    _deleted(BLOCKED, "abuse", 5)
    r = _callback(client)
    assert r.status_code == 302
    assert r["Location"].endswith("?error=signup_blocked")
    assert User.objects.count() == 0
    assert "oauth_pending_signup" not in client.session


@pytest.mark.django_db
def test_oauth_callback_existing_user_on_list_still_signs_in(client):
    from apps.users.email_verification import mark_email_verified

    user = User.objects.create_user(username="old2", email=BLOCKED)
    mark_email_verified(user)
    _deleted(BLOCKED, "abuse", 6)
    r = _callback(client)
    assert r["Location"].endswith("?success=true")


@pytest.mark.django_db
def test_oauth_finish_blocked_is_403_and_creates_nothing(client):
    _deleted(BLOCKED, "under_13", 7)
    session = client.session
    session["oauth_pending_signup"] = {
        "provider": "google",
        "user_data": dict(GOOGLE),
        "created_at": int(time.time()),
    }
    session.save()
    r = client.post(
        reverse("v1:users:oauth_finish_signup"),
        {"accepted_terms": True},
        content_type="application/json",
    )
    assert r.status_code == 403
    assert r.json()["code"] == "signup_blocked"
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_oauth_finish_blocked_without_consent_is_403_not_428(client):
    _deleted(BLOCKED, "abuse", 8)
    session = client.session
    session["oauth_pending_signup"] = {
        "provider": "google",
        "user_data": dict(GOOGLE),
        "created_at": int(time.time()),
    }
    session.save()
    r = client.post(
        reverse("v1:users:oauth_finish_signup"),
        {},
        content_type="application/json",
    )
    assert r.status_code == 403
    assert r.json()["code"] == "signup_blocked"
    assert User.objects.count() == 0
