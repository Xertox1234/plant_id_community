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
def test_me_profile_requires_auth():
    resp = APIClient().get("/forum/me/profile/")
    assert resp.status_code in (401, 403)
