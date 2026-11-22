"""A forum name is the member's forum display name, else their username:
never their legal name (owner decision 2026-11-21, audit H1/M6). Sign in
with Apple, Google or Firebase copies the provider's name claim into
``first_name``, and these payloads reach anonymous readers."""

import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.api.serializers import forum_display_name, serialize_forum_author
from wagtail_forum.models import ForumProfile

User = get_user_model()


def _named(username):
    return User.objects.create_user(
        username=username, first_name="Ada", last_name="Lovelace"
    )


@pytest.mark.django_db
def test_author_with_a_real_name_and_no_profile_shows_the_username():
    user = _named("member_abc12345")

    assert serialize_forum_author(user)["display_name"] == "member_abc12345"


@pytest.mark.django_db
def test_author_with_a_blank_forum_display_name_shows_the_username():
    user = _named("member_def67890")
    ForumProfile.for_user(user)  # a profile row with no display name

    user = User.objects.get(pk=user.pk)
    assert serialize_forum_author(user)["display_name"] == "member_def67890"


@pytest.mark.django_db
def test_author_forum_display_name_wins():
    user = _named("member_fern0001")
    profile = ForumProfile.for_user(user)
    profile.display_name = "Fern"
    profile.save(update_fields=["display_name"])

    user = User.objects.get(pk=user.pk)
    assert serialize_forum_author(user)["display_name"] == "Fern"
    assert forum_display_name(user) == "Fern"
