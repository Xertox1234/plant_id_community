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
