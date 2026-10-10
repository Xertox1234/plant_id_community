---
status: completed
priority: p4
issue_id: "532"
tags: [backend, users, migrations]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "One PR: a single DeleteModel migration (0018) drops the model and its table; nothing queries it, so a rolling deploy is safe (2026-10-10)"
---

# Delete the unused `users.DemoData` model

## Problem

Nothing creates or reads `DemoData`: outside its migrations, `apps/users/models.py`
is its only reference (checked 2026-10-09). Rows with
`demo_type="care_reminder"` or `target_onboarding_step="care_reminder_set"`
keep the retired values (todo 531 item 3; todo 458 item 4). Deleting the
model settles both instead of remapping data nobody reads.

Owner decision (2026-10-09): record it in 531 and do the deletion as its own
todo, not inside a p4 cleanup.

## Approach

Expand/contract, per `docs/rules/database.md`: first remove the model from
Django state only (`SeparateDatabaseAndState`, `DeleteModel` in state), so the
old container never selects a missing table during the rolling deploy; drop
the table in a later deploy. Check the admin, serializers, fixtures and the
web/mobile clients for any reference first.

## Acceptance Criteria

- [x] No code references `DemoData` (grep across backend, web, mobile).
- [ ] State-only removal shipped and deployed. → todo 536 (re-pointed 2026-10-10)
- [x] Table dropped in a later PR.

## Work Log

### 2026-10-09 - Filed from todo 531 item 3

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-0234)

- Deleted the `DemoData` class from `backend/apps/users/models.py`; the admin,
  serializers, fixtures, web and mobile held no reference.
- Added `users/migrations/0018_delete_demodata.py`: one `DeleteModel`
  (`DROP TABLE "users_demodata" CASCADE`), per the owner decision of
  2026-10-10, instead of the state-only / later-drop pair the Approach named.
- Caveat recorded in the migration docstring: `DemoData.created_by` was
  `SET_NULL`, so the old container's `User.delete()` UPDATEs the dropped table
  and fails (rolled back) between `migrate` and cutover.
- New test `test_the_demo_data_model_and_table_are_gone` pins both the model
  and the table as gone.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-0234)

- AC 1: `/usr/bin/grep -rn DemoData backend web/src plant_community_mobile/lib firebase --exclude-dir=migrations --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=venv; echo "exit=$? (1 = no match)"` — evidence `.sweep-evidence/g3/532-ac0.txt` (not committed), last lines:

  ```text
  exit=1 (1 = no match)
  ```

- AC 3: `cd backend && python3 scripts/todos/slot_env.py 3 -- env DATABASE_URL=postgresql://%2Ftmp/postgres backend/venv/bin/python backend/manage.py sqlmigrate users 0018 && python3 scripts/todos/slot_env.py 3 -- backend/venv/bin/python -m pytest backend/apps/users/tests/test_onboarding_checklist.py --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g3/532-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 16 passed, 3 warnings in 20.29s ========================
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-0234)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

- 2026-10-10 (todo 537, finding #979-1): the Approach and the last two
  criteria describe an expand/contract sequence that did not happen. By the
  owner decision in the frontmatter, ONE `DeleteModel` migration
  (`users/migrations/0018_delete_demodata.py`, PR #979) removed the model and
  dropped `users_demodata` in the same deploy. There was no state-only step
  and no later drop PR: read "Table dropped in a later PR" as "table dropped
  by 0018, in #979". The deploy confirmation (and the pre-drop row count, if
  one can be had) is todo 536.
