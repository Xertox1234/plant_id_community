"""One active push subscription per endpoint (todo 602 item 3).

``transaction.atomic()`` around release + upsert did not hold this under READ
COMMITTED: two concurrent subscribes of one endpoint by different accounts
each released nothing the other had committed, and both inserted an active
row. A partial unique constraint now refuses the second, the services retry
the release once, and migration 0019 deactivates the duplicates that already
exist before 0020 adds the constraint.
"""

import uuid
from unittest.mock import patch

import pytest
from apps.users.models import PushSubscription
from apps.users.services import NotificationService, PushEndpointConflict
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from rest_framework.test import APIClient

User = get_user_model()

ENDPOINT = "https://fcm.googleapis.com/fcm/send/one-browser"
KEYS = {"p256dh": "BPk-key", "auth": "auth-secret"}  # pragma: allowlist secret
SUBSCRIPTION = {"endpoint": ENDPOINT, "keys": KEYS}


def _row(user, *, active=True, endpoint=ENDPOINT):
    return PushSubscription.objects.create(
        user=user,
        endpoint=endpoint,
        p256dh_key=KEYS["p256dh"],
        auth_key=KEYS["auth"],
        is_active=active,
    )


@pytest.mark.django_db
def test_two_active_rows_for_one_endpoint_cannot_coexist():
    first = User.objects.create_user(username="first602")
    second = User.objects.create_user(username="second602")
    _row(first)

    with pytest.raises(IntegrityError), transaction.atomic():
        _row(second)

    # An inactive row on the same endpoint is still allowed: that is what a
    # released shared-browser subscription looks like.
    _row(second, active=False)
    assert PushSubscription.objects.filter(endpoint=ENDPOINT).count() == 2


def _rival_lands_after_each_release(rivals):
    """Patch ``_release_endpoint`` so that, after each real release, the next
    rival account's active row lands. That is what another transaction
    committing between this subscribe's release and its upsert looks like.

    The rival row is written OUTSIDE the upsert's savepoint (todo 628 item 1):
    a row created inside it would vanish with the IntegrityError rollback,
    leaving the retry's release nothing to do, so a retry loop without the
    per-attempt release would still pass."""
    real = NotificationService._release_endpoint
    calls = []

    def release_then_race(user, endpoint):
        calls.append(user)
        real(user, endpoint)
        if rivals:
            _row(rivals.pop(0), endpoint=endpoint)

    return calls, patch.object(
        NotificationService, "_release_endpoint", side_effect=release_then_race
    )


@pytest.mark.django_db
def test_a_subscribe_that_lost_the_race_releases_again_and_wins():
    rival = User.objects.create_user(username="rival602")
    user = User.objects.create_user(username="user602")
    calls, racing = _rival_lands_after_each_release([rival])

    with racing:
        subscription = NotificationService.subscribe_to_push(user, SUBSCRIPTION)

    assert calls == [user, user], "todo 628: one release per upsert attempt"
    rival_row = PushSubscription.objects.get(user=rival)
    assert rival_row.is_active is False, (
        "todo 628 item 1: the retry's own release must deactivate the rival "
        "row that survived the failed upsert"
    )
    active = PushSubscription.objects.filter(endpoint=ENDPOINT, is_active=True)
    assert list(active.values_list("user_id", flat=True)) == [user.pk]
    assert subscription.user_id == user.pk


@pytest.mark.django_db
def test_a_second_lost_race_raises_instead_of_looping():
    rivals = [User.objects.create_user(username=f"rival602-{i}") for i in range(2)]
    user = User.objects.create_user(username="loser602")
    calls, racing = _rival_lands_after_each_release(rivals)

    with racing, pytest.raises(IntegrityError):
        NotificationService.subscribe_to_push(user, SUBSCRIPTION)

    assert len(calls) == 2, "todo 628: two attempts, then give up"


RESUBSCRIBE_URL = "/api/v1/auth/push-notifications/resubscribe/"
SUBSCRIBE_URL = "/api/v1/auth/me/push-notifications/subscribe/"
NEW_ENDPOINT = "https://fcm.googleapis.com/fcm/send/new-browser"
NEW_KEYS = {"p256dh": "BNew-key", "auth": "new-secret"}  # pragma: allowlist secret


@pytest.fixture
def own_cache():
    """The push endpoints are rate limited in the shared cache: give the test
    an empty in-memory one. Never cache.clear(), which flushes dev Redis."""
    locmem = {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"push-resubscribe-test-{uuid.uuid4()}",
    }
    with override_settings(CACHES={"default": locmem, "renditions": locmem}):
        yield


@pytest.mark.django_db
def test_a_second_lost_resubscribe_race_is_a_409_and_changes_nothing(own_cache):
    """Todo 628 item 3 (owner decision 2026-10-12): the unauthenticated
    worker endpoint answers a twice-lost race with 409, not a 500."""
    owner = User.objects.create_user(username="owner628")
    old = _row(owner)
    rivals = [User.objects.create_user(username=f"rival628-{i}") for i in range(2)]
    _, racing = _rival_lands_after_each_release(rivals)

    with racing:
        response = APIClient(enforce_csrf_checks=True).post(
            RESUBSCRIBE_URL,
            {
                "old_subscription": {"endpoint": ENDPOINT, "auth": KEYS["auth"]},
                "subscription": {"endpoint": NEW_ENDPOINT, "keys": NEW_KEYS},
            },
            format="json",
        )

    assert response.status_code == 409, response.content
    assert "error" in response.json()
    old.refresh_from_db()
    assert old.is_active is True, "todo 628: the 409 rolled the swap back"
    assert not PushSubscription.objects.filter(endpoint=NEW_ENDPOINT).exists()


@pytest.mark.django_db
def test_a_second_lost_subscribe_race_is_a_409(own_cache):
    user = User.objects.create_user(username="sub628")
    rivals = [User.objects.create_user(username=f"subrival628-{i}") for i in range(2)]
    _, racing = _rival_lands_after_each_release(rivals)
    client = APIClient()
    client.force_authenticate(user)

    with racing:
        response = client.post(
            SUBSCRIBE_URL, {"subscription": SUBSCRIPTION}, format="json"
        )

    assert response.status_code == 409, response.content
    assert not PushSubscription.objects.filter(user=user).exists()


def _not_a_race():
    """An IntegrityError that is not the one-active-endpoint constraint, such
    as an FK violation when the user row is deleted mid-request."""
    return IntegrityError("insert or update violates foreign key constraint")


@pytest.mark.django_db
def test_a_non_race_integrity_error_is_not_retried_or_called_a_conflict():
    """Todo 641 item 2: only the endpoint race is retried and becomes
    PushEndpointConflict; any other IntegrityError propagates as itself."""
    user = User.objects.create_user(username="fk641")
    calls, racing = _rival_lands_after_each_release([])

    with (
        racing,
        patch.object(
            PushSubscription.objects, "update_or_create", side_effect=_not_a_race()
        ),
        pytest.raises(IntegrityError) as raised,
    ):
        NotificationService.subscribe_to_push(user, SUBSCRIPTION)

    assert not isinstance(raised.value, PushEndpointConflict)
    assert len(calls) == 1, "todo 641: a non-race fault is not retried"


@pytest.mark.django_db
def test_a_second_lost_race_is_a_push_endpoint_conflict():
    rivals = [User.objects.create_user(username=f"rival641-{i}") for i in range(2)]
    user = User.objects.create_user(username="loser641")
    _, racing = _rival_lands_after_each_release(rivals)

    with racing, pytest.raises(PushEndpointConflict):
        NotificationService.subscribe_to_push(user, SUBSCRIPTION)


@pytest.mark.django_db
def test_a_non_race_subscribe_integrity_error_is_a_logged_500(own_cache):
    """Todo 641 item 2: not a retryable 409, and not silent."""
    user = User.objects.create_user(username="sub641")
    client = APIClient()
    client.force_authenticate(user)

    with (
        patch.object(
            NotificationService, "subscribe_to_push", side_effect=_not_a_race()
        ),
        patch("apps.users.views.logger") as logger,
    ):
        response = client.post(
            SUBSCRIBE_URL, {"subscription": SUBSCRIPTION}, format="json"
        )

    assert response.status_code == 500, response.content
    assert logger.error.called, "todo 641 item 2: the fault is logged"
    logged = " ".join(str(c) for c in logger.error.call_args_list)
    assert ENDPOINT not in logged, "the endpoint is a capability URL"


@pytest.mark.django_db
def test_a_non_race_resubscribe_integrity_error_is_a_logged_500(own_cache):
    owner = User.objects.create_user(username="owner641")
    old = _row(owner)

    with (
        patch.object(
            NotificationService, "_store_subscription", side_effect=_not_a_race()
        ),
        patch("apps.users.views.logger") as logger,
    ):
        response = APIClient(enforce_csrf_checks=True).post(
            RESUBSCRIBE_URL,
            {
                "old_subscription": {"endpoint": ENDPOINT, "auth": KEYS["auth"]},
                "subscription": {"endpoint": NEW_ENDPOINT, "keys": NEW_KEYS},
            },
            format="json",
        )

    assert response.status_code == 500, response.content
    assert logger.error.called, "todo 641 item 2: the fault is logged"
    logged = " ".join(str(c) for c in logger.error.call_args_list)
    assert NEW_ENDPOINT not in logged, "the endpoint is a capability URL"
    old.refresh_from_db()
    assert old.is_active is True, "the failed swap rolled back"


@pytest.mark.django_db
def test_a_lost_race_409_is_logged(own_cache):
    """Todo 641 item 2: the 409 leaves a server-side trace."""
    user = User.objects.create_user(username="log641")
    rivals = [User.objects.create_user(username=f"logrival641-{i}") for i in range(2)]
    _, racing = _rival_lands_after_each_release(rivals)
    client = APIClient()
    client.force_authenticate(user)

    with racing, patch("apps.users.views.logger") as logger:
        response = client.post(
            SUBSCRIBE_URL, {"subscription": SUBSCRIPTION}, format="json"
        )

    assert response.status_code == 409, response.content
    assert logger.warning.called


BEFORE = ("users", "0018_delete_demodata")
AFTER = ("users", "0020_pushsubscription_unique_active_endpoint")


# transaction=True is unavoidable for MigrationExecutor (see
# test_migration_0017_remap.py and docs/rules/testing.md).
@pytest.mark.django_db(transaction=True)
def test_migrating_keeps_only_the_newest_active_row_per_endpoint():
    users = [User.objects.create_user(username=f"dupe602-{i}") for i in range(3)]
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE])
    try:
        old_apps = executor.loader.project_state([BEFORE]).apps
        OldSubscription = old_apps.get_model("users", "PushSubscription")
        rows = [
            OldSubscription.objects.create(
                user_id=user.pk,
                endpoint=ENDPOINT,
                p256dh_key=KEYS["p256dh"],
                auth_key=KEYS["auth"],
                is_active=True,
            )
            for user in users
        ]
        other = OldSubscription.objects.create(
            user_id=users[0].pk,
            endpoint=f"{ENDPOINT}-other",
            p256dh_key=KEYS["p256dh"],
            auth_key=KEYS["auth"],
            is_active=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([AFTER])
    finally:
        # Never leave the test DB on an old schema for later tests.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    state = dict(PushSubscription.objects.values_list("pk", "is_active"))
    # Same created_at to the microsecond is possible; the pk breaks the tie.
    assert state == {
        rows[0].pk: False,
        rows[1].pk: False,
        rows[2].pk: True,
        other.pk: True,
    }
