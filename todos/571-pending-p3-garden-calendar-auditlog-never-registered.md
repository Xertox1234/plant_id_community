---
status: pending
priority: p3
issue_id: "571"
tags: [backend, garden-calendar, auditlog, gdpr]
dependencies: []
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

- [ ] `GardenCalendarConfig.ready()` imports `apps.garden_calendar.auditlog` the
      way the users and plant_identification apps do (guarded by
      `"auditlog" in settings.INSTALLED_APPS`).
- [ ] A test asserts that `CareTask.mark_complete` and `mark_skip` each write an
      UPDATE `LogEntry` whose changes include `completed` / `skipped`. A second
      test does the same for one other registered model. Both fail with the
      import removed.
- [ ] The decision on whether the five registered models and their
      `include_fields` are the right audit scope is recorded in the Work Log.
      Plant notes and care logs are user health-adjacent data, and audit rows
      hold them.

## Work Log
