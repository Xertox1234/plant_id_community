import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_me_profile_get_and_patch():
    user = User.objects.create_user(username="ada")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    got = client.get("/forum/me/profile/")
    assert got.status_code == 200
    assert got.data["trust_level"] == 0
    assert got.data["capabilities"]["can_react"] is True

    patched = client.patch("/forum/me/profile/", {"bio": "Plant nerd"}, format="json")
    assert patched.status_code == 200
    assert patched.data["bio"] == "Plant nerd"


@pytest.mark.django_db
def test_me_profile_rejects_system_field_edits():
    user = User.objects.create_user(username="ada")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch(
        "/forum/me/profile/", {"trust_level": 4, "post_count": 999}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["trust_level"] == 0
    assert resp.data["post_count"] == 0
    profile = ForumProfile.for_user(user)
    assert profile.trust_level == 0  # unchanged in DB
    assert profile.post_count == 0


@pytest.mark.django_db
def test_me_profile_fcm_token_writes_but_never_reads_back():
    # todo 253 slice 6 (AC6): the mobile client registers its FCM device token
    # through this endpoint. The token is a credential — write-only: it must
    # land in the DB but never appear in any response body (GET or PATCH echo).
    user = User.objects.create_user(username="ada")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch(
        "/forum/me/profile/", {"fcm_token": "device-token-xyz"}, format="json"
    )
    assert resp.status_code == 200
    assert "fcm_token" not in resp.data
    assert ForumProfile.for_user(user).fcm_token == "device-token-xyz"

    # Blank is allowed and persists — the client clears its token on logout.
    resp = client.patch("/forum/me/profile/", {"fcm_token": ""}, format="json")
    assert resp.status_code == 200
    assert ForumProfile.for_user(user).fcm_token == ""

    got = client.get("/forum/me/profile/")
    assert got.status_code == 200
    assert "fcm_token" not in got.data


@pytest.mark.django_db
def test_registering_a_token_releases_it_from_any_other_profile():
    # An FCM token identifies a DEVICE: when a second account on the same
    # device registers it, the first account's stale claim must be released —
    # otherwise the previous user's forum pushes keep appearing on a device
    # someone else is now signed into (todo 253 slice 6 review; also covers a
    # best-effort logout clear that failed offline).
    previous = User.objects.create_user(username="prev-owner")
    prev_profile = ForumProfile.for_user(previous)
    prev_profile.fcm_token = "shared-device-token"
    prev_profile.save()

    newcomer = User.objects.create_user(username="new-owner")
    client = APIClient()
    client.force_authenticate(newcomer)
    resp = client.patch(
        "/forum/me/profile/", {"fcm_token": "shared-device-token"}, format="json"
    )
    assert resp.status_code == 200

    prev_profile.refresh_from_db()
    assert prev_profile.fcm_token == ""
    assert ForumProfile.for_user(newcomer).fcm_token == "shared-device-token"

    # A non-token PATCH must not trigger the release path.
    prev_profile.fcm_token = "unrelated-token"
    prev_profile.save()
    resp = client.patch("/forum/me/profile/", {"bio": "hi"}, format="json")
    assert resp.status_code == 200
    prev_profile.refresh_from_db()
    assert prev_profile.fcm_token == "unrelated-token"


@pytest.mark.django_db
def test_me_profile_requires_auth():
    resp = APIClient().get("/forum/me/profile/")
    assert resp.status_code in (401, 403)
