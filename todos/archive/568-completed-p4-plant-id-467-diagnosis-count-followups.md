---
status: completed
priority: p4
issue_id: "568"
tags: [backend, plant-identification, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Decline the two-thread TransactionTestCase and log the reason in the Work Log (select_for_update serialises the read path); ship the fix itself (2026-10-11)"
---

# Follow-ups from PR #1001 (todo 467, diagnosis_count)

## Problem

Todo-sweep run 2026-10-11-0053 merged PR #1001. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none.
Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1001 (todo sweep run 2026-10-11-0053, group g6, todos 467); follow-ups: verified.

1. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:107` Only diagnosis_count is atomic (F()). The unqualified disease.save() still writes every field from the stale instance, so concurrent diagnoses can drop each other's merged symptoms['identified'] or overwrite a higher confidence_score. Pre-existing, not a regression. | also: The counter now increments in the database, but the bare disease.save() still writes back every other field. Two overlapping diagnoses each merge symptoms['identified'] (and max confidence_score) into a stale copy, so the later write drops the earlier one's symptoms or higher confidence. | The F() fix covers only diagnosis_count. disease.save() still writes every field from the stale instance, so confidence_score and symptoms still lose concurrent updates. A symptoms list merged by a concurrent diagnosis can be overwritten. | Pre-existing, not a regression: the full-row save() still writes back stale confidence_score and symptoms. Two overlapping diagnoses can each drop the other's merged symptoms or overwrite a higher confidence. | Only diagnosis_count is atomic. In the same overlap, the full disease.save() still writes back stale confidence_score and symptoms['identified'], so the second write can lower a higher confidence or drop merged symptoms. | The F() fix covers only diagnosis_count; a stale confidence_score can overwrite a higher one. | The same unqualified save() still writes back stale confidence_score and symptoms from the pre-read instance, so concurrent diagnoses can still lose those updates.
2. **low** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:53` The overlap test simulates concurrency with two pre-loaded instances passed to _update_existing_disease; it never drives two overlapping store_disease_if_qualified calls, so the .first() read path's lost-update window is untested.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Finding 1 (fixed): `_update_existing_disease` in
  `backend/apps/plant_identification/services/disease_diagnosis_service.py` now re-reads the row with
  `select_for_update()` inside `transaction.atomic()`, merges confidence and symptoms into that fresh row,
  and saves only `diagnosis_count`, `confidence_score`, `symptoms` and `updated_at`. A stale caller copy can
  no longer drop another diagnosis's symptoms, lower a higher confidence, or clobber unrelated fields.
- The name lookup in `store_disease_if_qualified` also takes the row lock (`select_for_update().filter(...).first()`),
  so overlapping diagnoses of the same disease serialise on the read path.
- Tests: `DiagnosisMergeStaleInstanceTest` in
  `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py` (both stale copies keep all
  symptoms and the higher confidence; unrelated fields survive; both reads issue `FOR UPDATE`). All three fail
  on the pre-fix service and pass after.
- Finding 2 (declined, owner decision 2026-10-11): no two-thread `TransactionTestCase`. With `select_for_update`
  on the read path the second diagnosis blocks until the first commits, so the `.first()` lost-update window no
  longer exists; the stale-instance tests reproduce the remaining overlap deterministically, and the lock is
  asserted by query capture, without a timing-dependent threaded test.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest apps/plant_identification/tests/test_disease_diagnosis_count.py --create-db -v && grep -n -E 'Finding [12] \((fixed|declined)' todos/archive/568-completed-p4-plant-id-467-diagnosis-count-followups.md` — evidence `.sweep-evidence/g9/568-ac0.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 6 passed, 2 warnings in 17.15s ========================
  36:- Finding 1 (fixed): `_update_existing_disease` in
  47:- Finding 2 (declined, owner decision 2026-10-11): no two-thread `TransactionTestCase`. With `select_for_update`
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
