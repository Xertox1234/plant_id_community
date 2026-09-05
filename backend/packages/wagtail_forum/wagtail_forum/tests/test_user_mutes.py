"""UserMute model (todo 347) — the same guarantees test_user_blocks.py pins
for UserBlock: idempotent create, unmute, no duplicates, no self-mute at the
DB level, and the can_mute() policy."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from wagtail_forum.models import UserMute

User = get_user_model()


@pytest.mark.django_db
def test_mute_is_idempotent_and_unmute_removes_the_row():
    muter = User.objects.create_user(username="m1")
    muted = User.objects.create_user(username="t1")

    first = UserMute.mute(muter, muted)
    second = UserMute.mute(muter, muted)
    assert first.pk == second.pk
    assert UserMute.objects.filter(muter=muter, muted=muted).count() == 1

    UserMute.unmute(muter, muted)
    UserMute.unmute(muter, muted)  # no-op when already gone
    assert not UserMute.objects.exists()


@pytest.mark.django_db
def test_duplicate_and_self_mute_are_rejected_at_the_db_level():
    muter = User.objects.create_user(username="m2")
    muted = User.objects.create_user(username="t2")
    UserMute.objects.create(muter=muter, muted=muted)

    with pytest.raises(IntegrityError), transaction.atomic():  # savepoint
        UserMute.objects.create(muter=muter, muted=muted)
    with pytest.raises(IntegrityError), transaction.atomic():
        UserMute.objects.create(muter=muter, muted=muter)


@pytest.mark.django_db
def test_can_mute_policy():
    from django.contrib.auth.models import AnonymousUser

    a = User.objects.create_user(username="m3")
    b = User.objects.create_user(username="t3")

    assert UserMute.can_mute(a, b) is True
    assert UserMute.can_mute(a, a) is False
    assert UserMute.can_mute(AnonymousUser(), b) is False
    assert UserMute.can_mute(None, b) is False
    assert UserMute.can_mute(a, None) is False
