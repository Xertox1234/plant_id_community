"""Collapsed index categories stored per member (todo 673): the web PUTs
the list to ``/forum/me/collapsed-categories/`` (its own throttle scope, not
the shared profile-edit one), and any later session of the same member reads
it back as ``collapsed_categories`` on ``/forum/me/profile/``."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail_forum.api.serializers import MAX_COLLAPSED_CATEGORIES
from wagtail_forum.models import ForumProfile

User = get_user_model()

pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

URL = "/forum/me/profile/"
SAVE = "/forum/me/collapsed-categories/"


def _session(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_collapsing_persists_across_sessions_for_a_signed_in_user():
    user = User.objects.create_user(username="ada", email="a@x.io")
    assert _session(user).get(URL).json()["collapsed_categories"] == []

    resp = _session(user).put(SAVE, {"collapsed_categories": [7, 3, 7]}, format="json")

    assert resp.status_code == 200
    assert resp.json()["collapsed_categories"] == [7, 3]
    # A new session (another device, after a sign-out) sees the same state.
    later = _session(User.objects.get(pk=user.pk))
    assert later.get(URL).json()["collapsed_categories"] == [7, 3]
    assert ForumProfile.objects.get(user=user).collapsed_categories == [7, 3]

    # Expanding everything again is stored too.
    later.put(SAVE, {"collapsed_categories": []}, format="json")
    assert _session(user).get(URL).json()["collapsed_categories"] == []


def test_another_member_never_sees_my_collapsed_categories():
    ada = User.objects.create_user(username="ada", email="a@x.io")
    bob = User.objects.create_user(username="bob", email="b@x.io")
    _session(ada).put(SAVE, {"collapsed_categories": [5]}, format="json")

    assert _session(bob).get(URL).json()["collapsed_categories"] == []


@pytest.mark.parametrize(
    "value",
    [
        ["x"],
        [0],
        "5",
        list(range(1, MAX_COLLAPSED_CATEGORIES + 2)),
    ],
)
def test_bad_collapsed_categories_are_refused(value):
    user = User.objects.create_user(username="ada", email="a@x.io")

    resp = _session(user).put(SAVE, {"collapsed_categories": value}, format="json")

    assert resp.status_code == 400
    # Refused before the profile is touched: none stored (or none created).
    assert (
        not ForumProfile.objects.filter(user=user)
        .exclude(collapsed_categories=[])
        .exists()
    )


def test_anonymous_callers_cannot_store_collapsed_categories():
    resp = APIClient().put(SAVE, {"collapsed_categories": [1]}, format="json")

    assert resp.status_code in (401, 403)


def test_the_profile_patch_does_not_write_collapsed_categories():
    """Read-only there: the profile PATCH shares one throttle budget with
    FCM registration and the logout clear, so header clicks must not use it."""
    user = User.objects.create_user(username="ada", email="a@x.io")

    _session(user).patch(URL, {"collapsed_categories": [4]}, format="json")

    assert ForumProfile.objects.get(user=user).collapsed_categories == []
