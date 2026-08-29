import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail_forum.models import UserBlock

User = get_user_model()


@pytest.mark.django_db
def test_block_creates_row():
    blocker = User.objects.create_user(username="ada")
    blocked = User.objects.create_user(username="babbage")

    block = UserBlock.block(blocker, blocked)

    assert block.pk is not None
    assert UserBlock.objects.filter(blocker=blocker, blocked=blocked).count() == 1


@pytest.mark.django_db
def test_block_is_idempotent():
    blocker = User.objects.create_user(username="ada2")
    blocked = User.objects.create_user(username="babbage2")

    first = UserBlock.block(blocker, blocked)
    second = UserBlock.block(blocker, blocked)

    assert first.pk == second.pk
    assert UserBlock.objects.filter(blocker=blocker, blocked=blocked).count() == 1


@pytest.mark.django_db
def test_unblock_removes_row():
    blocker = User.objects.create_user(username="ada3")
    blocked = User.objects.create_user(username="babbage3")
    UserBlock.block(blocker, blocked)

    UserBlock.unblock(blocker, blocked)

    assert not UserBlock.objects.filter(blocker=blocker, blocked=blocked).exists()


@pytest.mark.django_db
def test_unblock_when_not_blocked_is_noop():
    blocker = User.objects.create_user(username="ada4")
    blocked = User.objects.create_user(username="babbage4")

    UserBlock.unblock(blocker, blocked)  # must not raise

    assert not UserBlock.objects.filter(blocker=blocker, blocked=blocked).exists()


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_row():
    blocker = User.objects.create_user(username="ada5")
    blocked = User.objects.create_user(username="babbage5")
    UserBlock.objects.create(blocker=blocker, blocked=blocked)

    with pytest.raises(IntegrityError):
        UserBlock.objects.create(blocker=blocker, blocked=blocked)


@pytest.mark.django_db
def test_self_block_rejected_at_db_level():
    # Probe with no outer atomic() of its own beyond pytest-django's per-test
    # transaction — this project's constraints have been observed DEFERRED
    # to commit time in at least one case (docs/patterns/architecture/
    # services.md), so a savepoint-wrapped probe can silently observe no
    # exception. This mirrors that file's documented verification approach.
    user = User.objects.create_user(username="ada6")

    with pytest.raises(IntegrityError):
        UserBlock.objects.create(blocker=user, blocked=user)


@pytest.mark.django_db
def test_can_block_rejects_self():
    user = User.objects.create_user(username="ada7")

    assert UserBlock.can_block(user, user) is False


@pytest.mark.django_db
def test_can_block_rejects_anonymous():
    from django.contrib.auth.models import AnonymousUser

    blocked = User.objects.create_user(username="babbage7")

    assert UserBlock.can_block(AnonymousUser(), blocked) is False


@pytest.mark.django_db
def test_can_block_allows_distinct_authenticated_users():
    blocker = User.objects.create_user(username="ada8")
    blocked = User.objects.create_user(username="babbage8")

    assert UserBlock.can_block(blocker, blocked) is True
