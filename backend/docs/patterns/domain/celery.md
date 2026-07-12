# Celery Async Task Patterns

**Stack**: Celery with Redis broker · configuration in `backend/plant_community_backend/settings.py`

---

## Idempotency — Required for All Tasks

Tasks can be retried by Celery on failure or timeout. Every task that modifies state must be safe to run multiple times with the same input.

```python
@shared_task(bind=True, max_retries=3)
def send_care_reminder(self, care_task_id: int) -> None:
    care_task = CareTask.objects.get(id=care_task_id)
    if care_task.reminder_sent:  # idempotency guard
        return
    send_email(care_task.user.email, ...)
    care_task.reminder_sent = True
    care_task.save(update_fields=["reminder_sent"])
```

Tasks that send notifications must check a `sent` flag before acting.

---

## Retry Configuration

```python
@shared_task(
    bind=True,
    max_retries=3,                          # Never leave unlimited
    autoretry_for=(requests.RequestException,),  # Specific exceptions only — not bare Exception
    default_retry_delay=30,                 # Avoid thundering herd
)
def call_external_api(self, ...):
    ...
```

Permanent errors (bad input, validation failure) must NOT be retried — catch and log instead:

```python
try:
    result = process(data)
except ValueError as exc:
    logger.error("[CELERY] Permanent error in task %s: %s", self.request.id, exc)
    return  # Don't re-raise — stops retry loop
```

---

## Error Handling

- `on_failure` handler required for tasks that interact with external services.
- All failures logged with `[CELERY]` prefix + task ID.

```python
@shared_task(bind=True)
def process_plant_image(self, image_id: int) -> None:
    try:
        ...
    except Exception as exc:
        logger.error("[CELERY] Task %s failed: %s", self.request.id, exc)
        raise self.retry(exc=exc)
```

---

## Beat Schedules

```python
CELERY_BEAT_SCHEDULE = {
    "send-daily-garden-reminders": {          # Descriptive key
        "task": "apps.garden_calendar.tasks.send_care_reminders",
        "schedule": crontab(hour=8, minute=0),
    },
}
CELERY_TIMEZONE = "UTC"  # Always timezone-aware
```

Periodic tasks that touch the DB must use `select_related`/`prefetch_related`.

---

## Task Organisation

- Tasks live in `tasks.py` within their app directory — not in views or models.
- Task names follow `module.task_name` format: `apps.garden_calendar.tasks.send_care_reminder`.
- Tasks used only for side effects: `@shared_task(ignore_result=True)`.
- Long-running tasks: use `celery.utils.functional.chunk` for large datasets to avoid blocking the worker pool.

## Testing Retry Backoff (2026-07-11, forum audit)

Three eager-mode traps when testing a `bind=True` retrying task:

1. `self.retry()` with NO task context re-raises the ORIGINAL exception, not
   `celery.exceptions.Retry` — a bare function-call test never observes `Retry`.
2. `task.apply(args=…)` runs WITH a task context and re-executes retries
   synchronously — assert attempt counts (`initial + max_retries` sends) and the
   final `FAILURE` result carrying the transient error…
3. …but `.apply()` IGNORES `countdown`, so backoff VALUES are structurally
   invisible to it. Pin them by faking the retry counter:

```python
from celery.exceptions import Retry

with patch.object(send_forum_push, "retry", side_effect=Retry("retried")) as mock_retry:
    send_forum_push.push_request(retries=1)
    try:
        with pytest.raises(Retry):
            send_forum_push.run("reply_added", user.pk, {"topic_id": "1"})
    finally:
        send_forum_push.pop_request()

assert mock_retry.call_args.kwargs["countdown"] == 60  # 30 * 2**1
```

Reference: `backend/apps/forum_host/tests/test_tasks.py` (exhaustion via
`.apply()` + countdown pins via `push_request`).
