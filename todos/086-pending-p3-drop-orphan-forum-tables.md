---
status: pending
priority: p3
issue_id: "086"
tags: [database, ops, cleanup]
dependencies: []
---

# Drop orphaned forum_* tables in any DB that ran ENABLE_FORUM=False

## Problem

The headless `apps/forum/` app was deleted along with its migrations. The app
was only ever in `INSTALLED_APPS` when `ENABLE_FORUM=False`. Any database that
was migrated under `ENABLE_FORUM=False` now has orphaned `forum_*` tables and
stale `django_migrations` rows for the `forum` app, with no migration files to
manage them.

This does **not** break `manage.py migrate` (Django tolerates orphan migration
records for uninstalled apps), and `apps/forum/` is a leaf app so there are no
cross-table FKs — the tables are simply dead weight.

## Findings

- Dev environment uses `ENABLE_FORUM=True`, so `apps.forum` was never migrated
  there — no cleanup needed for dev.
- Staging/production: unknown. Check each environment's `ENABLE_FORUM` value and
  whether `forum_*` tables exist.

## Recommended Action

For each environment, check and clean up if needed:

```sql
-- Inspect:
SELECT tablename FROM pg_tables WHERE tablename LIKE 'forum_%';
SELECT * FROM django_migrations WHERE app = 'forum';

-- If orphan tables exist, drop them (back up first):
DROP TABLE IF EXISTS forum_<...> CASCADE;   -- repeat per table
DELETE FROM django_migrations WHERE app = 'forum';
```

## Acceptance Criteria

- [ ] Each environment checked for `forum_*` tables / `forum` migration rows.
- [ ] Orphan tables and migration rows dropped where present (after backup).

## Work Log

### 2026-05-18 - Created

- Follow-up to the `apps/forum/` deletion. Flagged by kimi-review during the
  deletion commit.

## Notes

p3 — no functional impact; purely storage/cleanliness. Skip entirely for any
environment that ran `ENABLE_FORUM=True` (the app was never migrated there).
