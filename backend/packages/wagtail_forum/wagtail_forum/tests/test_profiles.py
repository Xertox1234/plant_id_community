from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from wagtail_forum.models import ForumProfile, TrustLevel
from wagtail_forum.signals import _refresh_profile

User = get_user_model()


@pytest.mark.django_db
def test_for_user_creates_profile_once():
    user = User.objects.create_user(username="ada")

    profile = ForumProfile.for_user(user)
    again = ForumProfile.for_user(user)

    assert profile.pk == again.pk
    assert profile.trust_level == TrustLevel.NEW
    assert profile.post_count == 0
    assert ForumProfile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_for_user_seeds_read_watermark_from_date_joined():
    """Todo 285: the seed comes from a stable per-user fact, not from the wall
    clock at whichever trigger happened to create the row.

    Deliberately backdates `date_joined` well outside the test's own execution
    window — the previous version of this test asserted `before <= watermark <=
    after` around a `create_user()` call, which `date_joined = now` satisfies
    too, so it would have kept passing if the derivation regressed to now().
    """
    joined = timezone.now() - timedelta(days=365)
    user = User.objects.create_user(username="ada-sleeper")
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    user.refresh_from_db()

    profile = ForumProfile.for_user(user)

    assert profile.read_watermark_at == joined
    # ...and it survived the round trip, i.e. it was persisted, not just set
    # on the in-memory instance.
    profile.refresh_from_db()
    assert profile.read_watermark_at == joined


def test_initial_watermark_falls_back_to_now_without_date_joined():
    """Host-agnostic fallback: `date_joined` is `AbstractUser`-only, not part of
    the `AbstractBaseUser` contract this package assumes, so a host whose user
    model lacks it must keep the pre-285 wall-clock behaviour rather than crash.

    Stands in a `date_joined`-less user object rather than swapping
    `AUTH_USER_MODEL`, which cannot be done per-test (the FK is resolved at
    import time).
    """
    minimal_host_user = SimpleNamespace(pk=1, username="ada-no-joined")
    assert not hasattr(minimal_host_user, "date_joined")  # guard the premise

    before = timezone.now()
    watermark = ForumProfile.initial_read_watermark(minimal_host_user)
    after = timezone.now()

    assert before <= watermark <= after


@pytest.mark.django_db
def test_initial_watermark_for_user_id_handles_a_missing_user():
    """The by-id helper is called from a signal handler that can race a user
    deletion — a vanished user must fall back, not raise."""
    before = timezone.now()
    watermark = ForumProfile.initial_read_watermark_for_user_id(10**9)
    after = timezone.now()

    assert before <= watermark <= after


@pytest.mark.django_db
def test_signals_profile_creation_also_seeds_from_date_joined():
    """`signals.py::_refresh_profile` creates the row by `user_id`, bypassing
    `for_user()` entirely — todo 285 fixed both paths, so a recount for a user
    with no profile yet must not stamp the watermark to now() either."""
    joined = timezone.now() - timedelta(days=200)
    user = User.objects.create_user(username="ada-recount")
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    assert not ForumProfile.objects.filter(user=user).exists()

    _refresh_profile(user.pk)

    profile = ForumProfile.objects.get(user=user)
    assert profile.read_watermark_at == joined


@pytest.mark.django_db
def test_signals_recount_queries_the_user_table_only_when_creating():
    """The seed is handed to `get_or_create` as a CALLABLE, so its user lookup
    stays on the create branch.

    `_refresh_profile` runs on every post publish/unpublish/delete, so an
    eagerly-evaluated seed would add a user SELECT to that hot path. Asserted
    through the production function rather than through a copy of its
    `get_or_create` call — a hand-rolled copy is correct by construction and
    would stay green while `signals.py` regressed.
    """
    user_table = User._meta.db_table

    existing = User.objects.create_user(username="ada-existing")
    ForumProfile.objects.create(user=existing)
    with CaptureQueriesContext(connection) as ctx:
        _refresh_profile(existing.pk)
    hot_path = [q for q in ctx.captured_queries if user_table in q["sql"]]
    assert not hot_path, (
        f"recount on an existing profile hit {user_table} — the seed callable "
        f"was resolved on the already-exists path: {hot_path}"
    )

    # Counterpart, so the assertion above is not vacuous: the SAME call does
    # pay for the lookup when it actually creates the row. Without this,
    # deleting the seed entirely would also leave the first assertion green.
    newcomer = User.objects.create_user(username="ada-newcomer")
    with CaptureQueriesContext(connection) as ctx:
        _refresh_profile(newcomer.pk)
    assert [q for q in ctx.captured_queries if user_table in q["sql"]], (
        f"recount that CREATES a profile never read {user_table} — the seed "
        "is not being resolved at all"
    )


@pytest.mark.django_db
def test_str_prefers_display_name():
    user = User.objects.create_user(username="ada")
    profile = ForumProfile.for_user(user)
    profile.display_name = "Ada L."
    assert str(profile) == "Ada L."


@pytest.mark.django_db
def test_for_user_does_not_mask_an_unrecoverable_integrity_error(monkeypatch):
    """get_or_create already recovers a lost create race itself (its INSERT
    runs in a savepoint and an IntegrityError is retried as a .get() before
    it is re-raised), so the only IntegrityError that can escape it is one
    whose retry ALSO found no row — e.g. the user row vanished. The former
    outer `except IntegrityError: .get()` wrapper (audit 2026-09-04 L1)
    turned that into a misleading DoesNotExist; it must propagate as-is."""
    user = User.objects.create_user(username="ada")

    def _raise(**kwargs):
        raise IntegrityError("user row vanished")

    monkeypatch.setattr(ForumProfile.objects, "get_or_create", _raise)

    with pytest.raises(IntegrityError):
        ForumProfile.for_user(user)
