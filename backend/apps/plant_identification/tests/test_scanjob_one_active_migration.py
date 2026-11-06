"""0031 fails a user's older duplicate active scan jobs before its constraint.

The create view's row lock always allowed one active job per user, so prod
should hold none, but a row from another writer must not abort the deploy.
The data step is driven with a stub model rather than MigrationExecutor:
``django_db(transaction=True)`` flushes Wagtail's migration-seeded rows and
breaks later tests in the suite (docs/rules/testing.md), and the constraint
under test is pinned separately in test_scan_task.py.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

migration = importlib.import_module(
    "apps.plant_identification.migrations.0031_scanjob_one_active_per_user"
)


def _apps_with(rows):
    """A historical-apps stub whose ScanJob yields ``rows`` (pk, user_id)."""
    manager = Mock()
    manager.filter.return_value.order_by.return_value.values_list.return_value = rows
    model = SimpleNamespace(objects=manager)
    return SimpleNamespace(get_model=lambda app, name: model), manager


def test_keeps_each_users_newest_and_fails_the_rest():
    # Ordered newest first per user, as the migration's order_by asks.
    apps, manager = _apps_with([(9, 1), (4, 1), (2, 1), (8, 2)])

    migration.fail_extra_active_jobs(apps, None)

    order = manager.filter.return_value.order_by
    assert order.call_args.args == ("user_id", "-created_at", "-pk")
    update_filter = manager.filter.call_args_list[-1]
    assert sorted(update_filter.kwargs["pk__in"]) == [2, 4]
    fields = manager.filter.return_value.update.call_args.kwargs
    assert fields["status"] == "failed"
    assert fields["failure_reason"] == "stale"


def test_no_duplicates_writes_nothing():
    apps, manager = _apps_with([(9, 1), (8, 2)])

    migration.fail_extra_active_jobs(apps, None)

    manager.filter.return_value.update.assert_not_called()
