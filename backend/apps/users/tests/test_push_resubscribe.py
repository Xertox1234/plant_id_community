"""One active push subscription per endpoint (todo 602 item 3).

``transaction.atomic()`` around release + upsert did not hold this under READ
COMMITTED: two concurrent subscribes of one endpoint by different accounts
each released nothing the other had committed, and both inserted an active
row. A partial unique constraint now refuses the second, the services retry
the release once, and migration 0019 deactivates the duplicates that already
exist before 0020 adds the constraint.
"""

from unittest.mock import patch

import pytest
from apps.users.models import PushSubscription
from apps.users.services import NotificationService
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

User = get_user_model()

ENDPOINT = "https://fcm.googleapis.com/fcm/send/one-browser"
KEYS = {"p256dh": "BPk-key", "auth": "auth-secret"}  # pragma: allowlist secret
SUBSCRIPTION = {"endpoint": ENDPOINT, "keys": KEYS}


def _row(user, *, active=True):
    return PushSubscription.objects.create(
        user=user,
        endpoint=ENDPOINT,
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


@pytest.mark.django_db
def test_a_subscribe_that_lost_the_race_releases_again_and_wins():
    """Another account's active row lands between this subscribe's release
    and its upsert (what the other transaction committing looks like)."""
    rival = User.objects.create_user(username="rival602")
    user = User.objects.create_user(username="user602")
    real = PushSubscription.objects.update_or_create
    calls = []

    def racing_upsert(*args, **kwargs):
        calls.append(kwargs["user"])
        if len(calls) == 1:
            _row(rival)
        return real(*args, **kwargs)

    with patch.object(
        PushSubscription.objects, "update_or_create", side_effect=racing_upsert
    ):
        subscription = NotificationService.subscribe_to_push(user, SUBSCRIPTION)

    assert calls == [user, user]
    active = PushSubscription.objects.filter(endpoint=ENDPOINT, is_active=True)
    assert list(active.values_list("user_id", flat=True)) == [user.pk]
    assert subscription.user_id == user.pk


@pytest.mark.django_db
def test_a_second_lost_race_raises_instead_of_looping():
    rivals = [User.objects.create_user(username=f"rival602-{i}") for i in range(2)]
    user = User.objects.create_user(username="loser602")
    real = PushSubscription.objects.update_or_create

    def always_racing(*args, **kwargs):
        _row(rivals.pop())
        return real(*args, **kwargs)

    with (
        patch.object(
            PushSubscription.objects, "update_or_create", side_effect=always_racing
        ),
        pytest.raises(IntegrityError),
    ):
        NotificationService.subscribe_to_push(user, SUBSCRIPTION)


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
