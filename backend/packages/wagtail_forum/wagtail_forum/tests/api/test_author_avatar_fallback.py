"""``AUTHOR_AVATAR_FALLBACK``: the host's own photo stands in for an author
whose forum profile has no avatar."""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail_forum.api.serializers import serialize_forum_author
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import ForumProfile

User = get_user_model()

HOOK = "wagtail_forum.tests.api.test_author_avatar_fallback"


def host_photo(user):
    return f"/media/accounts/{user.get_username()}.jpg"


def no_photo(user):
    return None


def broken(user):
    raise RuntimeError("boom")


@pytest.mark.django_db
def test_no_hook_and_no_forum_avatar_is_null():
    user = User.objects.create_user(username="plain")

    assert serialize_forum_author(user)["avatar"] is None


@pytest.mark.django_db
def test_host_photo_stands_in_when_the_forum_profile_has_no_avatar(settings):
    settings.WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK = f"{HOOK}.host_photo"
    without_profile = User.objects.create_user(username="noprofile")
    with_profile = User.objects.create_user(username="profiled")
    ForumProfile.for_user(with_profile)
    with_profile.refresh_from_db()

    assert (
        serialize_forum_author(without_profile)["avatar"]
        == "/media/accounts/noprofile.jpg"
    )
    assert (
        serialize_forum_author(with_profile)["avatar"] == "/media/accounts/profiled.jpg"
    )


@pytest.mark.django_db
def test_a_site_relative_host_photo_is_made_absolute(settings):
    settings.WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK = f"{HOOK}.host_photo"
    user = User.objects.create_user(username="rel")
    request = RequestFactory().get("/forum/topics/")

    assert (
        serialize_forum_author(user, request)["avatar"]
        == "http://testserver/media/accounts/rel.jpg"
    )


@pytest.mark.django_db
def test_the_forum_avatar_wins_over_the_host_photo(settings):
    settings.WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK = f"{HOOK}.host_photo"
    user = User.objects.create_user(username="both")
    profile = ForumProfile.for_user(user)
    profile.avatar = get_image_model().objects.create(
        title="forum-avatar",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=user,
    )
    profile.save(update_fields=["avatar"])
    user.refresh_from_db()

    assert serialize_forum_author(user)["avatar"] == profile.avatar.file.url


@pytest.mark.django_db
def test_a_host_with_no_photo_for_the_member_is_null(settings):
    settings.WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK = f"{HOOK}.no_photo"
    user = User.objects.create_user(username="nophoto")

    assert serialize_forum_author(user)["avatar"] is None


@pytest.mark.django_db
def test_a_hook_that_raises_costs_the_avatar_not_the_response(settings, caplog):
    settings.WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK = f"{HOOK}.broken"
    user = User.objects.create_user(username="unlucky")

    author = serialize_forum_author(user)

    assert author["avatar"] is None
    assert author["username"] == "unlucky"
    assert "AUTHOR_AVATAR_FALLBACK failed" in caplog.text
