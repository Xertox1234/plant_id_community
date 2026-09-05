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
- **`retry_backoff=` on an `autoretry_for` task is the backoff FACTOR, and
  `default_retry_delay` is ignored on that path.** Celery computes
  `factor = int(max(1.0, float(retry_backoff)))`, so `retry_backoff=True` is
  factor 1 (~1s/2s/4s jittered) no matter what `default_retry_delay` says.
  Pass the delay itself (`retry_backoff=RAG_INDEX_RETRY_DELAY`) and pin the
  countdowns with `push_request(retries=N)` + a mocked `retry()` + full jitter
  patched to its maximum (`celery.utils.time.random.randrange`). Verified in
  `celery/app/autoretry.py` (PR #606 review).
- **Enqueue from a signal receiver with `transaction.on_commit`, never a bare
  `.delay()`.** Wagtail's admin publish and Django's `Model.delete()` cascade
  fire `page_published`/`page_unpublished`/`post_delete` INSIDE
  `transaction.atomic()`, so an inline enqueue lets the worker read the
  pre-commit row (a first publish indexes nothing; a mid-delete row gets
  re-embedded into an orphan). Put the try/except INSIDE the callback — an
  exception there surfaces after the commit, from the view. Test with
  `django_capture_on_commit_callbacks(execute=True)`, and keep any `patch()`
  open while the captured callbacks run.
- **Per-task options like `ignore_result` are baked into each message at ENQUEUE
  time** (`Task.apply_async` → the message headers); the worker only falls back
  to the task class's value when the header is missing. Changing the decorator
  fixes messages produced from now on — a broker backlog keeps the old value
  and will still write result rows when first consumed. Say so in the runbook
  before someone reads it as "the fix didn't take" (audit 2026-09-04 L3/H1).
- **A package feature that needs a schedule ships a management command; the
  host schedules it (beat or cron) and the package never imports Celery.**
  `send_forum_digest` is the package boundary; the host's beat entry is a
  one-line `call_command` task. Make the command idempotent per row (a
  `last_*_sent_at` marker + "due" window) so an overlapping double fire — a
  deploy briefly running two containers with embedded beat — cannot send
  twice, and give it `--dry-run` that sends and writes NOTHING (todo 340).
- **Embedded beat (`celery worker -B`) is fine for a single co-located
  worker; put its schedule file in `/tmp`, pin the beat entry's task name
  to the registered task in a test, and re-check the todo's premise — "beat
  already exists" was false here.** A beat entry with a typo'd task name
  fails silently in prod logs (todo 340).
- **"Idempotent per row" is not overlap safety — a check-then-act loop
  double-sends for its whole duration.** A batch command needs BOTH a run
  lock (`cache.add` key per job, released in `finally`, ignored by
  `--dry-run`) and an atomic per-row claim (`UPDATE … WHERE marker =
  <value read>`, reverted on failure) before the side effect. Size a
  cohort task's `soft_time_limit`/`time_limit` yourself (the global 90 s is
  request-shaped), declare `autoretry_for=(OperationalError,)`, and on
  `SoftTimeLimitExceeded` re-enqueue a continuation; package code that
  catches `Exception` must re-raise that class BY NAME (`type(exc).__name__`)
  since it cannot import Celery (todo 340 review).
- **Gate a per-recipient preference inside the fan-out task, where the profile
  row is already in hand**, not in the enqueueing request; map event names to
  preference verbs explicitly and leave unmapped events UNGATED so a future
  event cannot be silently dropped by an old preference row (todo 343).
