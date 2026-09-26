"""Run the account-mail Celery tasks in-process (todo 447 item 11).

The views queue ``apps.users.tasks`` with ``.delay()`` after commit. Tests
have no worker and must never publish to a real broker, so ``.delay`` runs
the task synchronously with ``.apply()`` (Celery's eager path, retries
included). Tests that assert on the queueing itself patch ``.delay`` again
inside the test, which takes precedence.
"""

from unittest.mock import patch

import pytest
from apps.users import tasks

MAIL_TASKS = (
    tasks.send_verification_email_task,
    tasks.send_welcome_email_task,
    tasks.send_provider_linked_notice_task,
)


@pytest.fixture(autouse=True)
def run_mail_tasks_inline():
    patches = [
        patch.object(task, "delay", side_effect=lambda *a, _t=task: _t.apply(args=a))
        for task in MAIL_TASKS
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
