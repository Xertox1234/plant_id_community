---
status: completed
priority: p3
issue_id: "684"
tags: [forum, forum-categories, database, migrations]
dependencies: ["675"]
triage: ready
triaged: 2026-11-01
---

# Drop the `wagtail_forum_forum.is_hidden` column (contract half of migration 0049)

## Problem

Todo 675 (PR #1228, merged 2026-10-30 as 86895a62) replaced `Forum.is_hidden` with per-forum permission grants. Following the expand/contract rule in `docs/rules/database.md`, migration `wagtail_forum/0049_remove_forum_is_hidden.py` only removed the field from Django state and gave the column `db_default=False`. The column itself is still in the database, so a later migration has to drop it. Nothing tracked that until this todo.

## Findings

- `0049_remove_forum_is_hidden.py`: `AlterField(... db_default=False)` followed by a state-only `RemoveField` in `SeparateDatabaseAndState`. Its header comment says "the column itself is dropped by a later migration, once this release is live."
- 0049 shipped to production with #1228's deploy on 2026-10-30. Every container now runs code that never selects `is_hidden`, so the drop is safe in any later deploy.
- Precedent: `backend/apps/users/migrations/0017_drop_care_reminder_columns.py` (todo 458) is the contract half of `users/0015`. It uses `SeparateDatabaseAndState(database_operations=[RunSQL("ALTER TABLE … DROP COLUMN …", reverse_sql="… ADD COLUMN … boolean NOT NULL DEFAULT false")])`.

## Proposed Solution

Add `wagtail_forum/0050_drop_forum_is_hidden_column.py` (or the next free number), depending on the latest `wagtail_forum` migration:

- Wrap it in `SeparateDatabaseAndState` with `database_operations` only. Django state already has no field.
- `RunSQL("ALTER TABLE wagtail_forum_forum DROP COLUMN is_hidden", reverse_sql="ALTER TABLE wagtail_forum_forum ADD COLUMN is_hidden boolean NOT NULL DEFAULT false")`. Use literal SQL strings, never f-strings (CLAUDE.md gotcha 3).
- Keep it a migration of its own: no `RunPython` row writes on the forum table in the same migration (the "pending trigger events" rule in `docs/rules/database.md`).
- Before writing it, confirm the real table name with `Forum._meta.db_table`.

## Acceptance Criteria

- [x] A new `wagtail_forum` migration drops `is_hidden` from the database only. `makemigrations --check` reports no changes.
- [x] `migrate` forward then back to 0049 then forward again succeeds on a local Postgres database.
- [x] After migrating, `information_schema.columns` shows no `is_hidden` column on the forum table.
- [x] The full backend suite passes.

## Work Log

- 2026-10-31: Filed at the owner's request after the forum categories sweep (PR #1228). Migration 0049 left the column for the contract step and nothing tracked it.

### 2026-11-01 - Implemented by the todo sweep (run 2026-11-01-1340)

- Added `backend/packages/wagtail_forum/wagtail_forum/migrations/0053_drop_forum_is_hidden_column.py` (0050–0052 were taken): a database-only `SeparateDatabaseAndState` with a literal-SQL `RunSQL` that drops `wagtail_forum_forum.is_hidden`, reversed by re-adding it as `boolean NOT NULL DEFAULT false` (the `users/0017` precedent). Table name confirmed from `Forum._meta.db_table`.
- Updated `test_forum_permissions_deploy_window.py`, which asserted the column still existed: that was the 0047–0049 deploy window, and this todo closes it. The previous release is now the 0052 state, which must still read and write forums with the column gone; a new test asserts the column is absent; the NOT NULL default check keeps the five 0047 columns.
- Proved `migrate` forward, back to 0049 and forward again on a fresh local Postgres database (`plant_community_w1`), then checked `information_schema.columns`.

### 2026-11-01 - Verified by the todo sweep (run 2026-11-01-1340)

- AC 1: `bash -c 'ls backend/packages/wagtail_forum/wagtail_forum/migrations/0053_drop_forum_is_hidden_column.py && cat backend/packages/wagtail_forum/wagtail_forum/migrations/0053_drop_forum_is_hidden_column.py && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python backend/manage.py makemigrations --check --dry-run && echo MAKEMIGRATIONS_CHECK_OK'` — evidence `.sweep-evidence/g1/684-ac0.txt` (not committed), last lines:

  ```text
    from wagtail.images import permissions as image_permissions
  [settings] ENABLE_FILE_LOGGING=True (argv=['backend/manage.py', 'makemigrations', '--check', '--dry-run'])
  ✅ Environment configuration validated successfully
  No changes detected
  MAKEMIGRATIONS_CHECK_OK
  ```

- AC 2: `bash -c 'set -e; for target in "" "wagtail_forum 0049" ""; do python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python backend/manage.py migrate $target --noinput; done; python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python backend/manage.py showmigrations wagtail_forum; echo ALL_STEPS_OK'` — evidence `.sweep-evidence/g1/684-ac1.txt` (not committed), last lines:

  ```text
   [X] 0050_forum_display_settings
   [X] 0051_forum_subscription
   [X] 0052_forum_theme
   [X] 0053_drop_forum_is_hidden_column
  ALL_STEPS_OK
  ```

- AC 3: `psql -h /tmp -d plant_community_w1 -c "SELECT count(*) AS is_hidden_columns FROM information_schema.columns WHERE table_name = 'wagtail_forum_forum' AND column_name = 'is_hidden'" -c "SELECT count(*) AS forum_columns FROM information_schema.columns WHERE table_name = 'wagtail_forum_forum'"` — evidence `.sweep-evidence/g1/684-ac2.txt` (not committed), last lines:

  ```text

   forum_columns
  ---------------
              27
  (1 row)
  ```

- AC 4: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g1/684-ac3.txt` (not committed), last lines:

  ```text
  =========== 6170 passed, 8 skipped, 27 warnings in 565.57s (0:09:25) ===========
  …
      self.callHandlers(record)
    File "backend/venv/lib/python3.13/site-packages/sentry_sdk/integrations/logging.py", line 171, in sentry_patched_callhandlers
      return old_callhandlers(self, record)
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  ```

### 2026-11-01 - Completed by the todo sweep (run 2026-11-01-1340)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-01 - Review round 1: non-blocking findings (PR #1234)

Round 1 found 5 lows and nothing blocking.

- Fixed: the deploy-window test's module docstring still said the column "must still exist". Its first paragraph is now the past-tense history of the 0047-0049 window. No test needed; this is a docstring.
- Declined: `DROP COLUMN IF EXISTS`. The precedent `users/0017` uses a plain `DROP COLUMN`. A missing column means the schema has drifted, and the deploy should fail loudly then, not pass silently.
- Declined: the previous-release test at 0052 passes with or without 0053. That is expected: the 0053 assertion is `test_the_is_hidden_column_is_dropped` (information_schema), and the 0047 default checks belonged to the 0049 window, which shipped.
- Owner hand-off, not run: a pre-0047 container could have written `is_hidden=True` after 0048 converted flags to grants during the #1228 deploy window, and 0053 would drop that record. This is unlikely: the window lasted minutes. Checking it needs a prod query (`SELECT id FROM wagtail_forum_forum WHERE is_hidden`), and this sweep never reads prod. The owner can run it before deploying if they want.

### 2026-11-01 - Review round 2: non-blocking findings (PR #1234)

Round 2 found 3 lows and nothing blocking. Round 2 makes no code changes, so each one is declined:

- Declined: the information_schema queries have no `table_schema` filter. The test DB has only the `public` schema, and `wagtail_forum_forum` is unique there.
- Declined: the 0052 previous-release test now checks only model defaults. That is intended, since `test_every_new_column_has_a_database_default` covers the DB defaults.
- Owner hand-off (the same as the round 1 item): a guard against an `is_hidden=True` row that has no No-access grants. To check prod once by hand before the deploy: `SELECT id FROM wagtail_forum_forum WHERE is_hidden` (expected: only forums that already have both no_access grants, or none).
