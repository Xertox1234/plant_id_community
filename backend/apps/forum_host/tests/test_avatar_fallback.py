"""The forum shows a member's account photo when they have no forum avatar
(``WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK`` -> ``account_avatar_url``)."""

import pytest
from apps.forum_host.avatars import account_avatar_url
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.images.tests.utils import get_test_image_file
from wagtail_forum.models import ForumProfile
from wagtail_forum.tests.factories import make_forum

User = get_user_model()


def _expert(username, *, photo):
    user = User.objects.create_user(username=username)
    if photo:
        user.avatar.save(f"{username}.png", get_test_image_file(), save=True)
    profile = ForumProfile.for_user(user)
    profile.trust_level = 3
    profile.save(update_fields=["trust_level"])
    return user


@pytest.mark.django_db
def test_account_avatar_url_is_the_photo_or_none():
    with_photo = User.objects.create_user(username="photo")
    with_photo.avatar.save("photo.png", get_test_image_file(), save=True)
    without = User.objects.create_user(username="nophoto")

    assert account_avatar_url(with_photo) == with_photo.avatar.url
    assert account_avatar_url(without) is None


@pytest.mark.django_db
def test_forum_author_carries_the_account_photo_through_the_real_mount():
    make_forum()
    user = _expert("grasshopper", photo=True)
    _expert("initial", photo=False)

    resp = APIClient().get("/api/v1/forum/users/experts/")

    assert resp.status_code == 200
    avatars = {r["username"]: r["avatar"] for r in resp.data["results"]}
    assert avatars["grasshopper"].endswith(user.avatar.url)
    assert avatars["grasshopper"].startswith("http")
    assert avatars["initial"] is None


@pytest.mark.django_db
def test_the_fallback_adds_no_query_per_author():
    """The hook runs once per author per row, so it must read a column the
    list query already loaded: photos on every row cost nothing extra."""
    make_forum()
    for i in range(4):
        _expert(f"plain{i}", photo=False)
    with CaptureQueriesContext(connection) as without:
        APIClient().get("/api/v1/forum/users/experts/")

    for user in User.objects.filter(username__startswith="plain"):
        user.avatar.save(f"{user.username}.png", get_test_image_file(), save=True)
    with CaptureQueriesContext(connection) as with_photos:
        resp = APIClient().get("/api/v1/forum/users/experts/")

    assert all(r["avatar"] for r in resp.data["results"])
    assert len(with_photos) == len(without)
