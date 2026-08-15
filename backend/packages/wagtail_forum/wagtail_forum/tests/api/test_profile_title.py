import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail_forum.api.serializers import serialize_forum_author
from wagtail_forum.models import ForumProfile

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_author_payload_carries_title():
    user = User.objects.create_user(username="iris")
    profile = ForumProfile.for_user(user)
    profile.title = "Head moderator"
    profile.save(update_fields=["title"])
    assert serialize_forum_author(user)["title"] == "Head moderator"


@pytest.mark.django_db
def test_author_payload_title_defaults_empty():
    user = User.objects.create_user(username="noprofile")
    # No profile row at all → empty title, no crash.
    assert serialize_forum_author(user)["title"] == ""


@pytest.mark.django_db
def test_me_profile_cannot_patch_title():
    # PATCH {"title": "Grand Wizard"} as an authenticated user, expect
    # 200 with title unchanged ("" in the response), and DB value unchanged.
    user = User.objects.create_user(username="ada")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch("/forum/me/profile/", {"title": "Grand Wizard"}, format="json")
    assert resp.status_code == 200
    assert resp.data["title"] == ""
    profile = ForumProfile.for_user(user)
    assert profile.title == ""  # unchanged in DB
