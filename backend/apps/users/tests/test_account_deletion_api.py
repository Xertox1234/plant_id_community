"""The account deletion endpoints (Plan B task 6).

POST auth/account/delete/ (mobile, fresh Firebase re-auth), and the public
emailed-link pair POST auth/account/delete/request/ + .../confirm/.

``delete_account_task`` is not one of the conftest's inline mail tasks, so
every test that reaches ``request_account_deletion`` patches its ``.delay``:
nothing may publish to the dev Redis broker.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from apps.users import tasks
from apps.users.constants import (
    ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE,
    ACCOUNT_DELETE_LINK_CACHE_PREFIX,
    ACCOUNT_DELETE_LINK_INVALID_MESSAGE,
    ACCOUNT_DELETE_LINK_SUBJECT,
)
from apps.users.models import DeletedAccount
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from firebase_admin import auth
from freezegun import freeze_time
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

pytestmark = pytest.mark.django_db

EMAIL = "leaving.k6@example.test"
UID = "firebase-uid-delete-6"
SITE = "https://web.example.test"

DELETE_URL = "/api/v1/auth/account/delete/"
REQUEST_URL = "/api/v1/auth/account/delete/request/"
CONFIRM_URL = "/api/v1/auth/account/delete/confirm/"


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="leaving6",
        email=EMAIL,
        password="pw-not-used-1234",  # pragma: allowlist secret
        firebase_uid=UID,
    )


@pytest.fixture
def queued():
    """``delete_account_task.delay`` replaced, so nothing reaches a broker."""
    with patch.object(tasks.delete_account_task, "delay") as delay:
        yield delay


@pytest.fixture
def client():
    return APIClient()


def _bearer(client, user):
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def _verified(uid=UID, age=0):
    return patch.object(
        auth,
        "verify_id_token",
        return_value={"uid": uid, "auth_time": int(time.time()) - age},
    )


def _post(client, url, body, capture, **extra):
    with capture(execute=True):
        return client.post(url, body, format="json", **extra)


def _link_token(message) -> str:
    for line in message.body.splitlines():
        if "/delete-account/confirm?" in line:
            url = urlparse(line.strip())
            assert f"{url.scheme}://{url.netloc}" == SITE
            assert url.path == "/delete-account/confirm"
            return parse_qs(url.query)["token"][0]
    raise AssertionError("no confirm link in the email")


def _request_link(client, capture, email=EMAIL) -> str:
    with override_settings(SITE_URL=SITE):
        response = _post(client, REQUEST_URL, {"email": email}, capture)
    assert response.status_code == 200
    return _link_token(mail.outbox[-1])


# --- POST account/delete/ (mobile re-auth) ---------------------------------


def test_mobile_fresh_token_schedules(
    client, user, queued, django_capture_on_commit_callbacks
):
    with _verified() as verify:
        response = _post(
            _bearer(client, user),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 202
    assert response.json() == {"status": "scheduled"}
    verify.assert_called_once_with("fake-id-token", check_revoked=True)
    user.refresh_from_db()
    assert user.is_active is False
    record = DeletedAccount.objects.get(user_id=user.pk)
    queued.assert_called_once_with(record.pk)


def test_mobile_stale_auth_time_needs_reauth(
    client, user, queued, django_capture_on_commit_callbacks
):
    with _verified(age=301):
        response = _post(
            _bearer(client, user),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 403
    assert response.json()["code"] == "reauth_required"
    user.refresh_from_db()
    assert user.is_active is True
    assert DeletedAccount.objects.count() == 0
    queued.assert_not_called()


def test_mobile_other_users_uid_needs_reauth(
    client, user, queued, django_capture_on_commit_callbacks
):
    with _verified(uid="someone-else"):
        response = _post(
            _bearer(client, user),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 403
    assert response.json()["code"] == "reauth_required"
    assert DeletedAccount.objects.count() == 0


def test_mobile_account_without_uid_needs_reauth(
    client, user, queued, django_capture_on_commit_callbacks
):
    user.firebase_uid = None
    user.save(update_fields=["firebase_uid"])
    with _verified(uid=""):
        response = _post(
            _bearer(client, user),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 403
    assert response.json()["code"] == "reauth_required"


def test_mobile_revoked_token_needs_reauth(
    client, user, queued, django_capture_on_commit_callbacks
):
    with patch.object(
        auth, "verify_id_token", side_effect=auth.RevokedIdTokenError("revoked")
    ):
        response = _post(
            _bearer(client, user),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 403
    assert response.json()["code"] == "reauth_required"


def test_mobile_verifier_outage_is_503(
    client, user, queued, django_capture_on_commit_callbacks
):
    with patch.object(
        auth,
        "verify_id_token",
        side_effect=auth.CertificateFetchError("down", cause=None),
    ):
        response = _post(
            _bearer(client, user),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 503
    assert response.json()["code"] == "verifier_unavailable"
    user.refresh_from_db()
    assert user.is_active is True


def test_mobile_without_jwt_is_401(client, user, queued):
    with _verified():
        response = client.post(
            DELETE_URL, {"firebase_token": "fake-id-token"}, format="json"
        )

    assert response.status_code == 401
    assert DeletedAccount.objects.count() == 0


def test_mobile_staff_refused(client, queued, django_capture_on_commit_callbacks):
    staff = User.objects.create_user(
        username="staff6", email="staff6@example.test", firebase_uid=UID, is_staff=True
    )
    with _verified():
        response = _post(
            _bearer(client, staff),
            DELETE_URL,
            {"firebase_token": "fake-id-token"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 409
    assert response.json() == {
        "code": "contact_support",
        "error": ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE,
    }
    staff.refresh_from_db()
    assert staff.is_active is True


# --- POST account/delete/request/ ------------------------------------------


def test_request_unknown_email_same_response(
    client, user, django_capture_on_commit_callbacks
):
    with override_settings(SITE_URL=SITE):
        known = _post(
            client, REQUEST_URL, {"email": EMAIL}, django_capture_on_commit_callbacks
        )
        mail.outbox.clear()
        cache.clear()
        unknown = _post(
            client,
            REQUEST_URL,
            {"email": "nobody.k6@example.test"},
            django_capture_on_commit_callbacks,
        )

    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json() == {"status": "sent"}
    assert mail.outbox == []
    assert cache.get(f"{ACCOUNT_DELETE_LINK_CACHE_PREFIX}{user.pk}") is None


def test_request_inactive_account_sends_nothing(
    client, user, django_capture_on_commit_callbacks
):
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = _post(
        client, REQUEST_URL, {"email": EMAIL}, django_capture_on_commit_callbacks
    )

    assert response.json() == {"status": "sent"}
    assert mail.outbox == []


def test_request_known_email_sends_link(
    client, user, django_capture_on_commit_callbacks
):
    # A different case and stray spaces still find the account.
    token = _request_link(
        client, django_capture_on_commit_callbacks, email=f"  {EMAIL.upper()} "
    )

    message = mail.outbox[0]
    assert message.to == [EMAIL]
    assert message.subject == ACCOUNT_DELETE_LINK_SUBJECT
    assert "1 hour" in message.body
    assert token
    assert cache.get(f"{ACCOUNT_DELETE_LINK_CACHE_PREFIX}{user.pk}")
    # Requesting only sends a link: the account is untouched.
    user.refresh_from_db()
    assert user.is_active is True
    assert DeletedAccount.objects.count() == 0


def test_request_queues_the_mail_by_account_id(
    client, user, django_capture_on_commit_callbacks
):
    with patch.object(tasks.send_account_delete_link_task, "delay") as delay:
        response = _post(
            client, REQUEST_URL, {"email": EMAIL}, django_capture_on_commit_callbacks
        )

    assert response.status_code == 200
    # The account id only: the link is built in the worker, never sent
    # through the broker.
    delay.assert_called_once_with(user.pk)
    assert mail.outbox == []


def test_request_rate_limited(client, django_capture_on_commit_callbacks):
    with freeze_time(datetime.now(timezone.utc)):
        for n in range(5):
            response = _post(
                client,
                REQUEST_URL,
                {"email": f"probe{n}.k6@example.test"},
                django_capture_on_commit_callbacks,
            )
            assert response.status_code == 200
        response = _post(
            client,
            REQUEST_URL,
            {"email": "probe5.k6@example.test"},
            django_capture_on_commit_callbacks,
        )

    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0


def test_request_rate_limited_per_email(client, django_capture_on_commit_callbacks):
    with freeze_time(datetime.now(timezone.utc)):
        for n in range(3):
            response = _post(
                client,
                REQUEST_URL,
                {"email": EMAIL},
                django_capture_on_commit_callbacks,
                REMOTE_ADDR=f"10.0.0.{n + 1}",
            )
            assert response.status_code == 200
        # The same address in another case, from yet another IP.
        response = _post(
            client,
            REQUEST_URL,
            {"email": EMAIL.upper()},
            django_capture_on_commit_callbacks,
            REMOTE_ADDR="10.0.0.9",
        )

    assert response.status_code == 429


# --- POST account/delete/confirm/ ------------------------------------------


def test_confirm_valid_token_schedules_and_single_use(
    client, user, queued, django_capture_on_commit_callbacks
):
    token = _request_link(client, django_capture_on_commit_callbacks)

    first = _post(
        client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
    )
    second = _post(
        client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
    )

    assert first.status_code == 202
    assert first.json() == {"status": "scheduled"}
    user.refresh_from_db()
    assert user.is_active is False
    record = DeletedAccount.objects.get(user_id=user.pk)
    assert record.reason == "self"
    queued.assert_called_once_with(record.pk)
    assert second.status_code == 400
    assert second.json() == {
        "code": "link_invalid",
        "error": ACCOUNT_DELETE_LINK_INVALID_MESSAGE,
    }


def test_confirm_clears_jwt_cookies(
    client, user, queued, django_capture_on_commit_callbacks
):
    token = _request_link(client, django_capture_on_commit_callbacks)
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
    client.cookies["refresh_token"] = "stale-refresh"

    response = _post(
        client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
    )

    assert response.status_code == 202
    assert response.cookies["access_token"].value == ""
    assert response.cookies["refresh_token"].value == ""


def test_confirm_superseded_link_is_invalid(
    client, user, queued, django_capture_on_commit_callbacks
):
    old = _request_link(client, django_capture_on_commit_callbacks)
    _request_link(client, django_capture_on_commit_callbacks)

    response = _post(
        client, CONFIRM_URL, {"token": old}, django_capture_on_commit_callbacks
    )

    assert response.status_code == 400
    assert response.json()["code"] == "link_invalid"
    queued.assert_not_called()


def test_confirm_expired_token(
    client, user, queued, django_capture_on_commit_callbacks
):
    issued = datetime.now(timezone.utc)
    with freeze_time(issued):
        token = _request_link(client, django_capture_on_commit_callbacks)
    with freeze_time(issued + timedelta(seconds=3601)):
        response = _post(
            client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
        )

    assert response.status_code == 400
    assert response.json()["code"] == "link_invalid"
    user.refresh_from_db()
    assert user.is_active is True
    queued.assert_not_called()


@pytest.mark.parametrize("token", ["", "not-a-signed-token", None, 42])
def test_confirm_garbage_token(client, queued, token):
    response = client.post(CONFIRM_URL, {"token": token}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "link_invalid"


def test_confirm_after_account_is_gone_answers_scheduled(
    client, user, queued, django_capture_on_commit_callbacks
):
    """R16: the erase finished first (or raced us). Not a link error."""
    token = _request_link(client, django_capture_on_commit_callbacks)
    User.objects.filter(pk=user.pk).delete()

    response = _post(
        client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
    )

    assert response.status_code == 202
    assert response.json() == {"status": "scheduled"}
    queued.assert_not_called()


def test_confirm_race_inside_request_answers_scheduled(
    client, user, queued, django_capture_on_commit_callbacks
):
    token = _request_link(client, django_capture_on_commit_callbacks)
    with patch(
        "apps.users.deletion_views.request_account_deletion",
        side_effect=User.DoesNotExist,
    ):
        response = _post(
            client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
        )

    assert response.status_code == 202


def test_blog_author_refused(client, queued, django_capture_on_commit_callbacks):
    from apps.blog.models import BlogAuthorPage
    from wagtail.models import Page

    author = User.objects.create_user(
        username="author6", email="author6.k6@example.test"
    )
    Page.get_first_root_node().add_child(
        instance=BlogAuthorPage(
            title="An author", slug="an-author-6", author=author, bio="<p>Bio</p>"
        )
    )
    token = _request_link(
        client, django_capture_on_commit_callbacks, email="author6.k6@example.test"
    )

    response = _post(
        client, CONFIRM_URL, {"token": token}, django_capture_on_commit_callbacks
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "contact_support",
        "error": ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE,
    }
    author.refresh_from_db()
    assert author.is_active is True
    assert DeletedAccount.objects.count() == 0
    queued.assert_not_called()


def test_contact_support_copy_keeps_placeholder():
    assert ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE == (
        "This account can't be deleted from the app. Email [[CONTACT_EMAIL]] "
        "and we'll help."
    )
