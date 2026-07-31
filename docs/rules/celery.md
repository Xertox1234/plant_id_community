# Celery & async tasks — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/domain/celery.md`.

- **Every task declares retry config** — `autoretry_for`, `retry_backoff`,
  `max_retries`. Never leave a network-touching task with default (no) retries.
- **Tasks are idempotent** — safe to run twice. Guard side effects with a
  dedup key or status check.
- **Pass IDs, not ORM objects**, as task args — objects serialize stale.
- **No secrets in task args** — they are logged by the broker.
- Beat schedules live in config, not scattered across modules.
- Bracketed log prefix per task domain so worker logs stay greppable.
- **Per-task options are UNPREFIXED in the decorator** — `acks_late=True`,
  `reject_on_worker_lost=True`. The `task_`-prefixed names (`task_acks_late`,
  `task_reject_on_worker_lost`) are the *global* config settings; passed to
  `@shared_task(...)` they are silently accepted as inert kwargs and do nothing.
- **`.apply()` proves retry attempt COUNTS but silently ignores `countdown`** —
  eager mode re-executes immediately, so a broken backoff formula ships green. Pin
  the values with `task.push_request(retries=N)` +
  `patch.object(task, "retry", side_effect=Retry())`, asserting the captured
  `countdown` kwarg. And `retry()` called with NO task context re-raises the
  ORIGINAL exception, never `Retry`.
- **A tray-visible FCM `Notification(...)` block in a multi-event task must
  WHITELIST events** (content helper returns `None` for the rest): moderation/
  publish signals fire on every routine autopublish, so an unscoped block pops
  "Your post was published" at users for their own ordinary posts.
- **FCM collapse keys are per-EVENT-TYPE, never per-object** — FCM retains at
  most 4 distinct collapse keys per offline device, so unique per-post keys
  silently drop all but 4 notifications accumulated offline; a fixed
  per-event key still dedupes the retry-after-timeout case it exists for.
- **A retry config justified by "this loop can never raise" is load-bearing, and
  a change to any CALLEE can falsify it from another file.** `send_forum_email_batch`
  documents that all `OperationalError`-raising DB access happens before the send
  loop, so `autoretry_for` can only fire before any email is sent — email has no
  collapse-key dedup, so a retry after a partial send double-emails everyone. A
  refactor of `notification_service` introduced an unpack that could raise
  `TypeError` inside that loop: not in `autoretry_for`, so it would abort the
  batch mid-loop and silently skip every remaining recipient, with no retry.
  When you edit anything a task's loop calls, re-read the task's docstring for a
  stated invariant and guard rather than propagate (return a falsy result + log).
  "Unreachable today" is not a reason to skip the guard when an invariant depends
  on it (todo 287).
