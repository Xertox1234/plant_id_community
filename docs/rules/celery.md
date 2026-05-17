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
