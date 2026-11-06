"""0032 adds the decision fields with ``kept`` as the default.

Like the 0031 test, this does not drive MigrationExecutor
(``django_db(transaction=True)`` breaks later tests, docs/rules/testing.md).
The migration has no data step: AddField's default fills every existing row,
so pinning the operations is what proves old jobs (``done``, ``degraded``,
``failed`` and ``pending``, which an old build will still auto-save) become
``kept``.
"""

import importlib

from django.db import migrations

migration = importlib.import_module(
    "apps.plant_identification.migrations.0032_scanjob_decision"
)


def _ops(kind):
    return [op for op in migration.Migration.operations if isinstance(op, kind)]


def test_existing_finished_jobs_become_kept():
    fields = {op.name: op.field for op in _ops(migrations.AddField)}
    assert fields["decision"].default == "kept"
    assert fields["decision"].max_length == 16
    assert fields["decided_at"].null is True


def test_no_data_step_or_raw_sql():
    assert not _ops(migrations.RunPython)
    assert not _ops(migrations.RunSQL)


def test_adds_the_user_decision_index():
    (op,) = _ops(migrations.AddIndex)
    assert op.index.name == "scanjob_user_decision_idx"
    assert list(op.index.fields) == ["user", "decision"]


def test_depends_on_0031():
    assert (
        "plant_identification",
        "0031_scanjob_one_active_per_user",
    ) in migration.Migration.dependencies
