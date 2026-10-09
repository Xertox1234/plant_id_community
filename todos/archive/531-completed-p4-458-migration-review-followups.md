---
status: completed
priority: p4
issue_id: "531"
tags: [backend, users, migrations, testing]
dependencies: ["458"]
---

# Non-blocking review findings from PR #963 (todo 458)

## Problem

The PR #963 review (2026-10-09) passed with no blocking findings. A finding
two reviewers raised was fixed in the PR: the onboarding remap now runs before
the `auth_user` drop, so the DROP's lock is not held during the loop. These
low-severity items were left:

1. **The remap is tested by a direct call, not through the migration.**
   `RetiredOnboardingStepTest` calls `remap_retired_onboarding_step` with the
   live registry. Removing the `RunPython` from 0017's operations would leave
   the suite green. `docs/rules/database.md` asks for a MigrationExecutor test
   for backfills (it needs `transaction=True`; see the flush caveat in
   `wagtail_forum/tests/api/test_group_conversations.py`).
2. **No test pins the removal of
   `NotificationService.get_/update_user_notification_preferences`.**
3. **`DemoData` rows are not remapped.** Rows with `demo_type="care_reminder"`
   or `target_onboarding_step="care_reminder_set"` keep the raw value (the
   label falls back to it). Nothing creates or reads `DemoData`; deleting the
   model with its own expand/contract would settle this and todo 458 item 4.
4. **Remapped rows keep `is_onboarding_completed = False`** while
   `current_step = "onboarding_completed"`. Nothing reads `current_step`
   outside `models.py`, so it has no effect today.
5. **`PLANNING/DATABASE_SCHEMA.md:133`** still lists `care_reminder_email`.

Rejected in review: `DROP COLUMN IF EXISTS` (one Postgres transaction cannot
leave a half-dropped state; a missing column means drift and should fail
loudly) and a `lock_timeout` on the drop (small table, brief lock).

## Acceptance Criteria

- [x] Each item is fixed, or closed with a recorded reason. (completed 2026-10-09)

## Work Log

### 2026-10-09 - Filed from the PR #963 review

### 2026-10-09 - Resolution

1. Fixed. `test_migration_0017_remap.py` winds `users` back to 0016, seeds a
   row with the historical model, and migrates through 0017. It found a real
   bug: a row on the retired step that also listed it in `completed_steps`
   is UPDATEd twice, queueing a deferred FK check, and the DROP then failed
   with "pending trigger events". 0017 now runs `SET CONSTRAINTS ALL
   IMMEDIATE` (PostgreSQL only) between the remap and the drops. Production
   applied 0017 with 0 such rows, so it was unaffected. Mutation-checked:
   remap removed -> assertion failure; flush removed -> trigger error.
   Rule added to `docs/rules/database.md`.
2. Fixed. `RemovedPreferenceMethodsTest` pins the removal from the core
   `NotificationService`.
3. Moved: deleting `DemoData` -> todo 532 (owner, 2026-10-09).
4. Closed, no change: production had 0 rows on the retired step at deploy
   (todo 458 item 8), and nothing reads `current_step` outside `models.py`.
5. Fixed: the `care_reminder_email` row is gone from
   `PLANNING/DATABASE_SCHEMA.md`.
