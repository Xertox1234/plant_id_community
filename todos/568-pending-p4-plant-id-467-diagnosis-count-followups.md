---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
