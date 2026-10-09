"""0017's remap runs as part of the migration, not only as a function (todo 531).

`RetiredOnboardingStepTest` calls `remap_retired_onboarding_step` directly, so
removing the `RunPython` from 0017's operations would leave it green. This
winds `users` back to 0016, seeds a row on the retired step with the
historical model, and migrates forward through 0017 for real.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("users", "0016_drop_care_reminder_onboarding_step")
AFTER = ("users", "0017_drop_care_reminder_columns")


# transaction=True is unavoidable for MigrationExecutor (DDL cannot run with
# pending trigger events inside the test transaction); docs/rules/testing.md
# allows this one exception. serialized_rollback is NOT used: the host's
# post_migrate bootstrap re-creates rows the snapshot also carries. The full
# backend suite ran with this marker in place as one process (2026-10-09:
# 4382 passed, 8 skipped, 1 failed — the sqlite validate_environment test,
# which fails the same way on main in the sandbox).
@pytest.mark.django_db(transaction=True)
def test_migrating_through_0017_moves_rows_off_the_retired_step():
    # The user is created with the real model before winding back: the
    # reverse of 0017 re-adds the dropped columns with a DB default.
    user = get_user_model().objects.create_user(
        username="mig-0017", email="mig-0017@example.com"
    )
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE])
    try:
        old_apps = executor.loader.project_state([BEFORE]).apps
        OldProgress = old_apps.get_model("users", "OnboardingProgress")
        OldProgress.objects.create(
            user_id=user.pk,
            current_step="care_reminder_set",
            completed_steps=["account_created", "care_reminder_set"],
        )

        executor = MigrationExecutor(connection)
        executor.migrate([AFTER])
    finally:
        # Never leave the test DB on an old schema for later tests.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    from apps.users.models import OnboardingProgress

    progress = OnboardingProgress.objects.get(user=user)
    assert progress.current_step == "onboarding_completed"
    assert progress.completed_steps == ["account_created"]
