---
status: completed
priority: p3
issue_id: "571"
tags: [backend, garden-calendar, auditlog, gdpr]
dependencies: []
triage: blocked-owner
triaged: 2026-10-11
blocked_on: "Owner decision on audit scope, specifically whether free-text notes fields belong in LogEntry rows"
owner_decision: "Owner: register all 5 garden models but drop notes and other free-text fields from include_fields so user prose never lands in LogEntry; LogEntry purge on account deletion is a follow-up, not this todo (2026-10-11)"
---

# `garden_calendar/auditlog.py` is never imported, so no garden model is audited

## Problem

`backend/apps/garden_calendar/auditlog.py` calls `auditlog.register(...)` for
CareTask, CareLog, GardenBed, Harvest and Plant. Its comments cite GDPR Art. 30
and SOC 2. Nothing imports the module:

- `apps/users/apps.py` and `apps/plant_identification/apps.py` import their own
  `auditlog` modules from `ready()`.
- `apps/garden_calendar/apps.py` imports only `signals`.
- `grep -rn -E 'garden_calendar\.auditlog|from \.auditlog'` over `backend/apps`
  and `backend/plant_community_backend` finds nothing (checked 2026-10-10).

So none of those models has ever written a `LogEntry`. Found during sweep run
2026-10-11-0053 (PR #998): a reviewer flagged a `QuerySet.update()` for skipping
audit signals, and the registration turned out never to have been active.
Tests confirmed it: a `LogEntry` assertion on `CareTask.mark_complete` saw 0
entries.

## Acceptance Criteria

- [x] `GardenCalendarConfig.ready()` imports `apps.garden_calendar.auditlog` the
      way the users and plant_identification apps do (guarded by
      `"auditlog" in settings.INSTALLED_APPS`).
- [x] A test asserts that `CareTask.mark_complete` and `mark_skip` each write an
      UPDATE `LogEntry` whose changes include `completed` / `skipped`. A second
      test does the same for one other registered model. Both fail with the
      import removed.
- [x] The decision on whether the five registered models and their
      `include_fields` are the right audit scope is recorded in the Work Log.
      Plant notes and care logs are user health-adjacent data, and audit rows
      hold them.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1434)

- `GardenCalendarConfig.ready()` now imports `apps.garden_calendar.auditlog`, guarded by `"auditlog" in settings.INSTALLED_APPS` with the same `RuntimeError` fallback as the users and plant_identification apps.
- Audit scope decision (owner, 2026-10-11): all five models stay registered (GardenBed, Plant, CareTask, CareLog, Harvest), but no free-text field is audited. `notes` (all five), `materials_used` and `weather_conditions` (CareLog) were removed from `include_fields`; `skip_reason` and `description` were never listed. Only structured fields (choices, dates, numbers, flags, foreign keys, short labels) remain, plus `skipped_at` on CareTask. Purging LogEntry rows on account deletion is a follow-up, not this todo.
- `include_fields` also named five fields that do not exist on the models (`last_fertilized`, `last_watered` on GardenBed; `expected_harvest_date` on Plant; `taste_rating`, `shared_with_community` on Harvest); they are gone.
- New `backend/apps/garden_calendar/tests/test_auditlog_registration.py`: `mark_complete` / `mark_skip` each write one UPDATE LogEntry with `completed` / `skipped`; a Plant `health_status` edit writes one without `notes`; a notes-only edit writes none; every `include_fields` entry exists and none is free text. Five of the six fail when the import is stubbed out.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1434)

- AC 1: `grep -n -A20 'def ready' backend/apps/garden_calendar/apps.py` — evidence `.sweep-evidence/g4/571-ac0.txt` (not committed), last lines:

  ```text
  29-            try:
  30-                import apps.garden_calendar.auditlog  # noqa: F401
  31-            except RuntimeError:
  32-                # Auditlog models not yet migrated; registration happens after migrate
  33-                pass
  ```

- AC 2: `cd backend && python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest backend/apps/garden_calendar/tests/test_auditlog_registration.py --create-db -v; echo '=== same tests with apps.garden_calendar.auditlog stubbed out (import removed): expect failures ==='; python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -c "import sys, types; sys.modules['apps.garden_calendar.auditlog'] = types.ModuleType('apps.garden_calendar.auditlog'); import pytest; sys.exit(pytest.main(['backend/apps/garden_calendar/tests/test_auditlog_registration.py', '--create-db', '-v']))"` — evidence `.sweep-evidence/g4/571-ac1.txt` (not committed), last lines:

  ```text
  FAILED apps/garden_calendar/tests/test_auditlog_registration.py::GardenAuditlogRegistrationTest::test_mark_complete_writes_update_logentry_with_completed - AssertionError: 0 != 1
  FAILED apps/garden_calendar/tests/test_auditlog_registration.py::GardenAuditlogRegistrationTest::test_mark_skip_writes_update_logentry_with_skipped - AssertionError: 0 != 1
  FAILED apps/garden_calendar/tests/test_auditlog_registration.py::GardenAuditlogRegistrationTest::test_no_free_text_field_is_audited - KeyError: <class 'apps.garden_calendar.models.GardenBed'>
  FAILED apps/garden_calendar/tests/test_auditlog_registration.py::GardenAuditlogRegistrationTest::test_plant_update_writes_update_logentry_without_notes - AssertionError: 0 != 1
  =================== 5 failed, 1 passed, 2 warnings in 21.17s ===================
  ```

- AC 3: `grep -n -A6 'Implemented by the todo sweep (run 2026-10-11-1434)' todos/archive/571-completed-p3-garden-calendar-auditlog-never-registered.md` — evidence `.sweep-evidence/g4/571-ac2.txt` (not committed), last lines:

  ```text
  50-
  51-- `GardenCalendarConfig.ready()` now imports `apps.garden_calendar.auditlog`, guarded by `"auditlog" in settings.INSTALLED_APPS` with the same `RuntimeError` fallback as the users and plant_identification apps.
  52-- Audit scope decision (owner, 2026-10-11): all five models stay registered (GardenBed, Plant, CareTask, CareLog, Harvest), but no free-text field is audited. `notes` (all five), `materials_used` and `weather_conditions` (CareLog) were removed from `include_fields`; `skip_reason` and `description` were never listed. Only structured fields (choices, dates, numbers, flags, foreign keys, short labels) remain, plus `skipped_at` on CareTask. Purging LogEntry rows on account deletion is a follow-up, not this todo.
  53-- `include_fields` also named five fields that do not exist on the models (`last_fertilized`, `last_watered` on GardenBed; `expected_harvest_date` on Plant; `taste_rating`, `shared_with_community` on Harvest); they are gone.
  54-- New `backend/apps/garden_calendar/tests/test_auditlog_registration.py`: `mark_complete` / `mark_skip` each write one UPDATE LogEntry with `completed` / `skipped`; a Plant `health_status` edit writes one without `notes`; a notes-only edit writes none; every `include_fields` entry exists and none is free text. Five of the six fail when the import is stubbed out.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1434)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
