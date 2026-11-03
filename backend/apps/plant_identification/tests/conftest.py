"""Run the scan-job Celery tasks in-process (Scan 2.0 Phase B).

Views queue the scan tasks with ``.delay()``. Tests have no worker and must
never publish to a real broker, so ``.delay`` runs the task synchronously with
``.apply()``. Follows ``apps/users/tests/conftest.py``. The tasks arrive in
B3; until then there is nothing to patch.
"""

import importlib
from unittest.mock import patch

import pytest

_TASKS = (
    ("apps.plant_identification.tasks", "run_scan_job"),
    ("apps.plant_identification.tasks", "notify_scan_job_finished"),
)


@pytest.fixture(autouse=True)
def run_scan_tasks_inline():
    patches = []
    for module_name, task_name in _TASKS:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue  # B3 has not added the tasks module yet
        task = getattr(module, task_name, None)
        if task is None:
            continue
        patches.append(
            patch.object(
                task,
                "delay",
                side_effect=lambda *a, _t=task, **kw: _t.apply(args=a, kwargs=kw),
            )
        )
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
