---
status: pending
priority: p3
issue_id: "467"
tags: [backend, dead-code, race-condition]
dependencies: []
source_review: "todos/394-pending-p3-triage-the-grandfathered-archived-todos.md"
---

# Delete the orphaned `ai_care_service.py`; make `diagnosis_count` atomic

## Problem

Two items from the todo 394 triage:

- **From 009 (dead code services):**
  `backend/apps/plant_identification/services/ai_care_service.py` has had
  no code references since 1b8efa66 (#800, todo 405 slice 2). Its only
  mention is a tree listing in `backend/docs/architecture/analysis.md`.
  None of the other 11 services 009 listed is dead now (8 have live
  importers). `plant_care_reminder_service.py` is deleted by todo 410
  slice B.
- **From 004 (vote race):** its "similar patterns" AC never landed. The
  one read-modify-write counter on a live, paid path is
  `disease.diagnosis_count += 1` in
  `backend/apps/plant_identification/services/disease_diagnosis_service.py`
  (about line 90). Two simultaneous diagnoses of the same disease lose an
  increment. Others (`users/models.py`, `core/models.py`) are lower stakes;
  list them when fixing.

## Acceptance Criteria

- [ ] `ai_care_service.py` is deleted, and the architecture doc's tree no
      longer lists it; the full backend suite passes.
- [ ] `diagnosis_count` is incremented with `F()`, with a test that fails on
      the read-modify-write version.
- [ ] The other read-modify-write counters are listed with a keep or fix
      verdict each.
