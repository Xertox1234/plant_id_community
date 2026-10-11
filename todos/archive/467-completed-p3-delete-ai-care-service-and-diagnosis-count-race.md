---
status: completed
priority: p3
issue_id: "467"
tags: [backend, dead-code, race-condition]
dependencies: []
source_review: "todos/archive/394-completed-p3-triage-the-grandfathered-archived-todos.md"
triage: ready
triaged: 2026-10-10
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

- [x] `ai_care_service.py` is deleted, and the architecture doc's tree no
      longer lists it; the full backend suite passes.
- [x] `diagnosis_count` is incremented with `F()`, with a test that fails on
      the read-modify-write version.
- [x] The other read-modify-write counters are listed with a keep or fix
      verdict each.

## Read-modify-write Counter Audit

Search: every `+= 1` / `-= 1` on a persisted field in `backend/apps` and
`backend/packages` outside tests and migrations (2026-10-10). Local loop
tallies (`totals[...]`, `bed_count`, `warmed_count`, `streak`, `counter` in
`users/oauth_views.py`) are not stored counters and are left out.

- **fix** `PlantDiseaseDatabase.diagnosis_count`
  (`plant_identification/services/disease_diagnosis_service.py`): now
  `F("diagnosis_count") + 1`, pinned by
  `plant_identification/tests/test_disease_diagnosis_count.py`.
- **keep** `EmailNotification.open_count` / `click_count`
  (`core/models.py`, `mark_opened` / `mark_clicked`): no caller outside
  tests, so no live path can race. Use `F()` if open/click tracking is
  ever wired up.
- **keep** `CircuitMonitor.consecutive_failures`
  (`plant_identification/circuit_monitoring.py`): an in-process listener
  attribute, never written to the database.
- **keep** `User.forum_posts_count` / `posts_count_verified`
  (`users/models.py`): nothing increments them; they are only read.
- **keep** the rest of `_update_existing_disease`: the `confidence_score`
  max and the `symptoms` merge are still read-modify-write on the same
  `save()`. A lost merge drops a symptom string that the next diagnosis
  re-adds; no count or money depends on it.
- Already atomic, for the record: blog `view_count` and `flag_count`,
  `PlantSpecies.identification_count`, forum `Topic.view_count`.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- Deleted `backend/apps/plant_identification/services/ai_care_service.py`
  (no importers), its line in the `backend/docs/architecture/analysis.md`
  service tree, and its entry in `scripts/add_log_prefixes.py`, which
  exits `MISSING` when a listed file is gone.
- `DiseaseAutostorageService._update_existing_disease` now increments
  `diagnosis_count` with `F()` and re-reads it, so the returned instance
  holds an integer.
- Added `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py`:
  two instances loaded before either update must count to 3; the
  `+= 1` version gives 2 (mutation-checked).
- Listed the other read-modify-write counters with a verdict each (above).

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `bash -c "test ! -e backend/apps/plant_identification/services/ai_care_service.py && echo 'ai_care_service.py: deleted' && ! grep -n ai_care_service backend/docs/architecture/analysis.md && echo 'analysis.md: no ai_care_service line' && cd backend && python3 scripts/todos/slot_env.py --main-root . 6 -- backend/venv/bin/python -m pytest --create-db -q -p no:cacheprovider"` — evidence `.sweep-evidence/g6/467-ac0.txt` (not committed), last lines:

  ```text
    File "backend/apps/plant_identification/services/combined_identification_service.py", line 121, in _cleanup_executor
      logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  EXIT=0
  ```

- AC 2: `bash -c "grep -n 'F(\"diagnosis_count\") + 1' backend/apps/plant_identification/services/disease_diagnosis_service.py && cd backend && python3 scripts/todos/slot_env.py --main-root . 6 -- backend/venv/bin/python -m pytest apps/plant_identification/tests/test_disease_diagnosis_count.py --create-db -q -p no:cacheprovider"` — evidence `.sweep-evidence/g6/467-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 2 warnings in 18.56s ========================
  ```

- AC 3: `sed -n '/^## Read-modify-write Counter Audit/,/^## Work Log/p' todos/archive/467-completed-p3-delete-ai-care-service-and-diagnosis-count-race.md` — evidence `.sweep-evidence/g6/467-ac2.txt` (not committed), last lines:

  ```text
    re-adds; no count or money depends on it.
  - Already atomic, for the record: blog `view_count` and `flag_count`,
    `PlantSpecies.identification_count`, forum `Topic.view_count`.

  ## Work Log
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
