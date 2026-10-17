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
- All failures logged with a bracketed prefix for the task's **domain** plus the
  task ID: `[EMAIL]` for account mail, `[FCM]` for push, `[CELERY]` only for a
  task with no narrower domain. This matches `docs/rules/celery.md`, and grepping
  a domain finds its task failures next to its request-path logs (todo 449 item 5).

```python
@shared_task(bind=True)
def process_plant_image(self, image_id: int) -> None:
    try:
        ...
    except Exception as exc:
        logger.error("[PLANT_ID] Task %s failed: %s", self.request.id, exc)
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

## Periodic tasks: embedded beat in the co-located worker (todo 340)

There was no beat schedule before the digest. `CELERY_BEAT_SCHEDULE` lives
in settings (crontab, UTC), and `bin/start.sh` runs
`celery worker -B --schedule=/tmp/celerybeat-schedule …` so the single
worker container also ticks the schedule — no second process, no second
service. Rules that make this safe: the scheduled task is a thin
`call_command` wrapper around an idempotent management command (per-row
`last_*_sent_at` marker, "due" window, `--dry-run`), so a restart of the
worker (start.sh restarts it up to 5×) or a deploy overlap cannot double
send; and `test_tasks.py` pins the beat entry's `task` to the registered
task's `.name`, because beat only logs a typo'd name. `bin/test-start.sh`
needs bash ≥ 5.1 (`wait -n` pid list) — run it in Docker on macOS:
`docker run --rm -v "$PWD/bin:/w" -w /w bash:5.2 bash test-start.sh`.

## Delivery outbox: send-time recheck, claims, reconciliation (todo 619)

A `.delay()` after commit is not durable, and a send helper that returns
`False` cannot tell an opt-out from a dead SMTP connection. External
deliveries that must not be lost now go through `apps/core/delivery.py`
(model `core.DeliveryIntent`):

- **Record with the event.** `dispatch()` writes one `pending` row per
  recipient for forum email and browser push in the same savepoint as the
  bell rows; `send_verification_email` writes one with the allowance claim.
  A newsletter signup or a lockout writes one only when the broker refuses
  the task. The task is still enqueued on commit; its `batch_id=` kwarg names
  the rows. Payloads hold ids and display fields, never bodies, signed links,
  tokens or addresses.
- **Claim before send, outcome after.** One conditional `UPDATE` claims
  (`pending`, or `claimed` past `DELIVERY_CLAIM_LEASE_SECONDS`), so a
  duplicate enqueue or a racing re-drive finds nothing to send. Claim
  *after* the task's up-front reads, or its `OperationalError` autoretry
  meets its own claim. Outcome writes inside a send loop go through a guard
  that never raises (`forum_host.tasks._record`), for the same reason.
- **Classify, then decide.** `EmailService.last_outcome` (`EmailOutcome`:
  sent / suppressed / permanent / transient) and a browser subscription's
  `is_active` after a failed send separate retryable failures from opt-outs,
  5xx rejections and gone subscriptions. Only transient failures go back to
  `pending` with backoff (`DELIVERY_RETRY_BASE_SECONDS`, doubling), terminal
  at `DELIVERY_MAX_ATTEMPTS`; rows older than `DELIVERY_MAX_AGE_SECONDS` expire.
- **Recheck on every attempt.** `apps/forum_host/eligibility.py::recheck`
  runs in all four forum send tasks, first run and retries alike: active
  account, preferences, address, and (for payloads carrying `actor_id`, which
  `dispatch` always writes) post visibility, blocks/mutes against the actor
  and the topic subscription. `actor_id` never reaches a device or browser.
- **Reconcile** (`reconcile_deliveries`, beat every 5 min) re-drives due
  rows through each kind's redriver, which re-enqueues the owning task. It
  never charges a verification allowance.
- **At-least-once.** No provider idempotency key is available, so a worker
  killed between provider acceptance and the outcome write re-sends that one
  message after the lease. Browser push records outcomes in bulk after its
  loop (a browser collapses a repeat with the same `tag`). FCM has outbox
  rows since todo 624 (`Kind.FORUM_PUSH`) so a hold survives a restart; it
  keeps its per-device retry and credentials stop (todos 593, 606, 621), and
  a hand-off to `send_forum_push` finishes its row.
- **Holds, not countdowns** (todo 624). A delivery that must wait (quiet
  hours, reply coalescing; `apps/forum_host/pacing.py`) is put back to
  `pending` with `mark_held(rows, release_at, reason)`, which does not spend
  an attempt; reconciliation releases it once due and never expires a row
  still inside its hold. Never hold with a Celery `eta`/`countdown` longer
  than the Redis broker's visibility timeout (1 hour by default): an unacked
  message older than that is redelivered, a duplicate send. The 10-minute
  coalescing countdown is far inside it, and the outbox is its backstop.
- **Weekly mail** (digest, newsletter) is not in the outbox: each run's
  per-member claim is already the record. A run that reports `failed=N`
  enqueues at most `WEEKLY_RECOVERY_MAX_RUNS` recovery runs of the same
  command (`schedule_weekly_recovery`), which re-claim with consent rechecked.

Tests: `apps/forum_host/tests/test_send_time_eligibility.py`,
`test_delivery_outbox.py`, `test_quiet_hours_and_coalescing.py`, `apps/users/tests/test_mail_recovery.py`,
`apps/blog/tests/test_newsletter_recovery.py`.

## Outcomes and alerts (todo 623)

One vocabulary, `apps/core/notification_ops.py::Outcome`, for every live
email and push path. It is read from each path's own record (the outbox row,
`EmailOutcome`, `EmailNotification`, a weekly run's summary line, a care
sweep's per-owner result); there is no second ledger.

- **Send side:** `queued`, `attempted`, `accepted`, `retrying`, `failed`,
  `suppressed`. `accepted` is the provider (SMTP relay, FCM, a browser push
  service) taking the message, nothing more. A hold is `queued`, a hand-off to
  another task's retries (`delivery.HANDED_OFF`) is `attempted`.
- **Provider evidence only:** `delivered`, `bounced`, `complained`, written by
  the Resend webhook (`email_feedback.py`, todo 625). `log_outcomes` refuses
  them, so no send path can claim delivery.
- **Engagement is not an outcome.** A click is an `EmailClick` row and leaves
  the status alone; opens are not collected.
- **Where to read it:** `manage.py delivery_outcomes [--hours N]` counts outbox
  rows by kind and outcome. The weekly digest, the newsletter and each care
  sweep log one `[OUTCOME] channel=… path=… accepted=N …` line.

Alerts go to Sentry (owner decision 2026-10-12). The logging integration makes
every ERROR log an event, so an alert is an ERROR line carrying counts, kinds
and exception class names, never an address, token, URL or body:

| Failure | Where it is raised |
| --- | --- |
| Broker refused an enqueue | `notification_ops.log_broker_failure` (class name only, no traceback: a broker error can carry its URL) |
| Retries exhausted | `delivery.mark_retry`; `reconcile` for expired and interrupted rows; the weekly recovery cap |
| Outbox not draining | `check_outbox_lag`, every reconcile pass: a pending row more than `DELIVERY_QUEUE_LAG_ALERT_SECONDS` past due |
| Push not configured, with work to drop | `report_push_unconfigured` (FCM, VAPID), at most hourly per channel |
| Beat or worker stopped, queue backed up | Sentry Cron Monitors (below) |

**Cron Monitors.** `plant_community_backend/sentry_config.py` turns on
`CeleryIntegration(monitor_beat_tasks=True)`. Every `CELERY_BEAT_SCHEDULE`
entry becomes a monitor named after its key. Beat checks in `in_progress` when
it enqueues, the worker `ok` on success and `error` on a failure or a retry.
Sentry reports a **missed** run when beat did not enqueue (worker or beat dead)
and a **timeout** when the task did not finish within the monitor's max
runtime (the queue is backed up or the worker is wedged). The check that runs
inside the worker cannot see its own worker die, which is why that case is
Sentry's. Keep every entry a `crontab` or a `schedule` of a minute or more;
`test_every_beat_entry_gets_a_cron_monitor` fails otherwise. A recovery run
or a manual `.delay()` carries no monitor headers and does not check in.

**One scheduler.** Beat is embedded in the one worker (`worker -B`). Never run
a second `-B` worker or a separate beat beside it: two schedulers fire every
entry twice. The commands' run locks and per-row claims absorb a double fire,
but the monitors then see two runs. Split beat into its own service only when
the worker must scale past one container; then run exactly one beat, and give
the workers no `-B`.

Tests: `apps/core/tests/test_notification_ops.py`.
