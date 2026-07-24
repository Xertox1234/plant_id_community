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


def _forum_image(uploader, title="avatar"):
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    return get_image_model().objects.create(
        title=title,
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=uploader,
    )


@pytest.mark.django_db
def test_me_profile_avatar_set_and_read():
    # todo 257 slice A (AC): avatar settable via /me/profile with a bare image
    # id; response + GET echo the ABSOLUTE URL (same shape rendered on posts).
    user = User.objects.create_user(username="ada")
    ForumProfile.for_user(user)
    image = _forum_image(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch("/forum/me/profile/", {"avatar_id": image.id}, format="json")
    assert resp.status_code == 200
    assert resp.data["avatar"] == f"http://testserver{image.file.url}"
    assert "avatar_id" not in resp.data  # write-only, never echoed
    assert ForumProfile.for_user(user).avatar_id == image.id

    got = client.get("/forum/me/profile/")
    assert got.data["avatar"] == f"http://testserver{image.file.url}"


@pytest.mark.django_db
def test_me_profile_avatar_rejects_foreign_image():
    # IDOR: a caller must not set their avatar to an image ANOTHER user
    # uploaded — mirrors the inline-image membership check (api/sanitize.py).
    owner = User.objects.create_user(username="owner")
    attacker = User.objects.create_user(username="attacker")
    ForumProfile.for_user(attacker)
    foreign = _forum_image(owner)
    client = APIClient()
    client.force_authenticate(attacker)

    resp = client.patch("/forum/me/profile/", {"avatar_id": foreign.id}, format="json")
    assert resp.status_code == 400
    assert ForumProfile.for_user(attacker).avatar_id is None  # unchanged


@pytest.mark.django_db
def test_me_profile_avatar_rejects_image_outside_forum_collection():
    # The other IDOR half: an image the caller DID upload but that lives outside
    # the forum collection (e.g. a blog image) is not a valid avatar.
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file

    user = User.objects.create_user(username="ada")
    ForumProfile.for_user(user)
    outside = get_image_model().objects.create(
        title="blog-hero", file=get_test_image_file(), uploaded_by_user=user
    )
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch("/forum/me/profile/", {"avatar_id": outside.id}, format="json")
    assert resp.status_code == 400
    assert ForumProfile.for_user(user).avatar_id is None


@pytest.mark.django_db
def test_me_profile_avatar_clear():
    # An explicit null clears the avatar (no ownership check needed).
    user = User.objects.create_user(username="ada")
    image = _forum_image(user)
    profile = ForumProfile.for_user(user)
    profile.avatar = image
    profile.save(update_fields=["avatar"])
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch("/forum/me/profile/", {"avatar_id": None}, format="json")
    assert resp.status_code == 200
    assert resp.data["avatar"] is None
    assert ForumProfile.for_user(user).avatar_id is None


@pytest.mark.django_db
def test_me_profile_requires_auth():
    resp = APIClient().get("/forum/me/profile/")
    assert resp.status_code in (401, 403)
