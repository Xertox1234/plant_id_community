"""Run the scan-job Celery tasks in-process (Scan 2.0 Phase B).

Views queue the scan tasks with ``.delay()``. Tests have no worker and must
never publish to a real broker, so ``.delay`` runs the task synchronously with
``.apply()``. Follows ``apps/users/tests/conftest.py``.
"""

import importlib
from unittest.mock import patch

import pytest

_TASKS = (
    ("apps.plant_identification.tasks", "run_scan_job"),
    ("apps.plant_identification.tasks", "notify_scan_job_finished"),
    ("apps.plant_identification.tasks", "send_scan_push_to_device"),
)


@pytest.fixture(autouse=True)
def run_scan_tasks_inline():
    patches = []
    for module_name, task_name in _TASKS:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # Only the tasks module itself being absent is skippable. A broken
            # import INSIDE it must fail loudly, or the broker guard would
            # silently switch off and tests would publish to the dev broker.
            if exc.name != module_name:
                raise
            continue
        task = getattr(module, task_name)
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
