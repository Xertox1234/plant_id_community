---
status: skipped
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

### 2026-05-18 - Investigated by completing-todos skill (run 2026-05-18-2300) — SKIPPED

- Picked up by automated workflow; investigated and **skipped** — see below.
- **The todo's assumption about dev is wrong.** The local dev DB
  (`plant_community`) DOES contain orphaned forum tables, despite the
  `ENABLE_FORUM=True` reasoning in Findings. Verified via Django DB introspection:
  - 8 orphan tables: `forum_attachment`, `forum_category`, `forum_flaggedcontent`,
    `forum_moderationaction`, `forum_post`, `forum_reaction`, `forum_thread`,
    `forum_userprofile`.
  - 6 stale `django_migrations` rows for app `forum`.
  - These belong to the custom headless `apps/forum/` app (their names do not
    match Machina's schema, e.g. Machina has no `forum_thread`/`forum_userprofile`).
- Confirmed `apps/forum/` still exists on disk but is fully deactivated:
  it is in **neither** branch of `INSTALLED_APPS` (`settings.py` LOCAL_APPS), and
  `apps/forum/migrations/` contains no migration files. So the 8 tables are
  genuine orphans — the custom forum app was installed + migrated at some earlier
  point, then removed without dropping its tables.
- **Why skipped:** This is a destructive, multi-environment ops task that cannot
  be safely completed from an automated coding session:
  1. Dropping the 8 tables requires a DB backup first (per the Recommended
     Action) — an unbacked-up `DROP TABLE ... CASCADE` is irreversible.
  2. Staging/production cannot be inspected or modified from this session.
  Needs a human/ops runbook execution with backups, per environment.

### Corrected status

- Dev: orphan tables/migration rows **present** (listed above) — drop pending,
  backup-first.
- Staging/Production: **unknown** — not reachable from this session.

### 2026-05-21 - Re-confirmed SKIP by completing-todos skill (run 2026-05-21-2253)

- Picked up again as part of a 4-todo goal sweep (086, 087, 088, 091).
- Re-confirmed **not completable from a coding session** — the prior skip stands:
  1. Acceptance criteria require checking + dropping orphan tables in **each
     environment** (incl. staging/production), which are unreachable from this
     session.
  2. `DROP TABLE ... CASCADE` is destructive and irreversible without a prior
     backup — outside the safe scope of automated work, and authoring a
     table-dropping migration unilaterally is a hard-to-reverse design decision
     that needs human/ops sign-off.
- **Human action needed:** per-environment ops runbook — back up, run the
  inspect/DROP SQL in Recommended Action, delete the stale `forum`
  `django_migrations` rows. Left `pending`.

### 2026-05-26 - Re-confirmed SKIP by completing-todos skill (run 2026-05-26-1959)

- Picked up as part of a 4-todo sweep (086, 087, 097, 098).
- Same prior-skip reasoning still stands — no change in circumstances:
  1. Acceptance criteria require inspecting and dropping orphan tables in **each
     environment** (dev + staging/production). Staging/production remain
     unreachable from this coding session.
  2. `DROP TABLE ... CASCADE` is irreversible without a prior backup; executing
     destructive DB ops without a backup is outside safe automated scope.
- **Human action needed:** back up each environment, run the inspect/DROP SQL
  from Recommended Action, delete stale `django_migrations` rows for app `forum`.
  Left in `in_progress` / skipped by automated sweep.

### 2026-05-28 - Archived as skipped (run 2026-05-28-1709)

- No accessible dev DB (psql not on PATH, Django virtualenv not active). Prior skip entries checked a DB that is no longer reachable.
- Staging/production remain unreachable from this coding session.
- Zero functional impact — purely dead storage. The SQL runbook in Recommended Action is documented; ops can execute it when desired.
- Archived rather than left cycling through automated sweeps.

## Notes

p3 — no functional impact; purely storage/cleanliness. Skip entirely for any
environment that ran `ENABLE_FORUM=True` (the app was never migrated there).
