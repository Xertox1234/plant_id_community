"""The three profile "privacy settings" are gone (auth audit M9, todo 707).

``profile_visibility``, ``show_email`` and ``show_location`` were stored and
returned but read by nothing: no view hid a profile, an email or a location
because of them. A control that does nothing tells the user something false,
so the columns were removed. Profiles are public (owner decision 2026-11-10).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

REMOVED = ("profile_visibility", "show_email", "show_location")


@pytest.fixture
def signed_in(db):
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="TestPass123!",  # pragma: allowlist secret
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def test_the_model_has_no_visibility_columns():
    names = {f.name for f in User._meta.get_fields()}
    assert names.isdisjoint(REMOVED)


def test_the_profile_does_not_return_them(signed_in):
    client, _ = signed_in
    body = client.get("/api/v1/auth/user/").json()
    profile = body.get("user", body)
    assert "bio" in profile  # the profile itself is there
    assert set(profile).isdisjoint(REMOVED)


def test_an_installed_build_that_still_sends_them_is_not_refused(signed_in):
    """A client that still sends the three keys gets a normal answer."""
    client, user = signed_in
    resp = client.patch(
        "/api/v1/auth/user/update/",
        {
            "bio": "Grows ferns.",
            "profile_visibility": "private",
            "show_email": True,
            "show_location": False,
        },
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert set(resp.data["user"]).isdisjoint(REMOVED)
    user.refresh_from_db()
    assert user.bio == "Grows ferns."
