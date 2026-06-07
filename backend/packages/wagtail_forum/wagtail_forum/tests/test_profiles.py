import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail_forum.models import ForumProfile, TrustLevel

User = get_user_model()


@pytest.mark.django_db
def test_for_user_creates_profile_once():
    user = User.objects.create_user(username="ada", password="x")

    profile = ForumProfile.for_user(user)
    again = ForumProfile.for_user(user)

    assert profile.pk == again.pk
    assert profile.trust_level == TrustLevel.NEW
    assert profile.post_count == 0
    assert ForumProfile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_str_prefers_display_name():
    user = User.objects.create_user(username="ada", password="x")
    profile = ForumProfile.for_user(user)
    profile.display_name = "Ada L."
    assert str(profile) == "Ada L."


@pytest.mark.django_db
def test_for_user_falls_back_on_integrity_error(monkeypatch):
    """Simulate a lost create race: get_or_create raises IntegrityError because
    a concurrent request already inserted the profile; for_user must recover by
    returning the existing row rather than propagating the error."""
    user = User.objects.create_user(username="ada", password="x")
    existing = ForumProfile.objects.create(user=user)

    def _raise(**kwargs):
        raise IntegrityError("duplicate key")

    monkeypatch.setattr(ForumProfile.objects, "get_or_create", _raise)

    recovered = ForumProfile.for_user(user)

    assert recovered.pk == existing.pk
