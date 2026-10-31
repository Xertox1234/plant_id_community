---
status: pending
priority: p3
issue_id: "684"
tags: [forum, forum-categories, database, migrations]
dependencies: ["675"]
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

- [ ] A new `wagtail_forum` migration drops `is_hidden` from the database only. `makemigrations --check` reports no changes.
- [ ] `migrate` forward then back to 0049 then forward again succeeds on a local Postgres database.
- [ ] After migrating, `information_schema.columns` shows no `is_hidden` column on the forum table.
- [ ] The full backend suite passes.

## Work Log

- 2026-10-31: Filed at the owner's request after the forum categories sweep (PR #1228). Migration 0049 left the column for the contract step and nothing tracked it.
