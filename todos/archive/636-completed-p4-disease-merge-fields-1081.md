---
status: completed
priority: p4
issue_id: "636"
tags: [plant-id, migrations, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Edit 0028 to keep max confidence, union symptoms and fill blank fields from the extras when merging (helps unmigrated DBs); fix the other findings (2026-10-12)"
---

# Follow-ups from PR #1081 (todo 613, disease name merge migration)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1081 (todo 613, disease name merge migration). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1081 (todo sweep run 2026-10-12-0349, group g11, todos 613); follow-ups: verified.

1. **medium** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py:78` The merge keeps only the oldest row's scalar fields. The extras' description, scientific_name, prevention_tips, expert_reviewed/community_confirmed flags, reference_image, symptoms and confidence_score are deleted without a trace, and the keeper is picked by age, not completeness. | also: The merge sums diagnosis_count but drops the extras' confidence_score, symptoms['identified'] and description. The service's runtime merge keeps the highest confidence and the union of symptoms, so a migrated row can lose data that a live merge would have kept. | The merge re-points care, results and species, but deletes the extra rows' own fields (description, prevention_tips, scientific_name, symptoms, reference_image, expert_reviewed/community_confirmed). The keeper is picked by age, not completeness, so a richer variant's content is lost.
2. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:134` In the IntegrityError merge path of _create_or_merge_new_disease,_update_existing_disease can raise DoesNotExist if the winner row is deleted before the locked re-read; the outer except swallows it and the diagnosis is dropped (None). | also: In the IntegrityError merge path, _update_existing_disease can still raise DoesNotExist if the winner row is deleted before the locked re-read. Only the lookup path got the recreate fallback; here it is swallowed by the outer except and the diagnosis is dropped (None). | The DoesNotExist fallback covers only the first lookup. On the collision path, if the winner's row is deleted between the name-collision insert and the locked re-read in_update_existing_disease, DoesNotExist reaches the outer catch-all. The diagnosis is then dropped and the method returns None. The window is very narrow.
3. **low** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:208` DiagnosisFirstCreateRaceTest docstring still says 'unique disease_name constraint'; test_integrity_error_without_a_matching_row_is_not_a_merge now passes via_is_name_collision, and the name-collision-but-re-lookup-finds-nothing branch has no test.
4. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:135` _is_name_collision depends on psycopg's exc.**cause**.diag.constraint_name. On a backend or driver without it (e.g. SQLite test DB), a genuine name collision re-raises instead of merging, and the race path becomes untestable there. | also: The DoesNotExist retry only covers the first-lookup path. In _create_or_merge_new_disease, a winner row deleted between re-find and the locked re-read raises DoesNotExist, which the outer except swallows and returns None, dropping the diagnosis. The window is tiny and untested.
5. **low** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py:68` An extra row's care instruction whose treatment_name the keeper already has is hard-deleted even when its instructions text differs. The irreversible migration does this silently and leaves no record.

1 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/apps/plant_identification/tests/test_disease_name_case_merge_migration.py:42 The seeded care instructions use treatment names that differ by case ('Black Spot treatment' vs 'black spot treatment'), sidestepping the unique_together (disease, treatment_name) collision real data hits. (fixed on main: origin/main adds a treatment_names param to_seed_disease and test_shared_treatment_name_keeps_the_keepers_instruction seeds 'Chemical Treatment'/'Organic Treatment' shared across variants, exercising the collision.; the refuter agreed: On origin/main, _seed_disease takes treatment_names, and test_shared_treatment_name_keeps_the_keepers_instruction seeds shared names across variants. That exercises the unique (disease, treatment_name) collision path, so the gap is closed.)
- low: backend/apps/plant_identification/tests/test_disease_name_case_merge_migration.py:42 The seeds give each variant a different treatment_name (name-prefixed), so the unique_together collision on care instructions is never exercised. The test would stay green with the bug above. (refuted: On origin/main, _seed_disease takes treatment_names, and test_shared_treatment_name_keeps_the_keepers_instruction seeds shared names across variants. That exercises the unique (disease, treatment_name) collision path, so the gap is closed.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1081 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g11`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Findings 1 and 5: `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py` still keeps the oldest row (owner decision), but now folds the extras into it: highest confidence, union of `symptoms['identified']`, either review flag, and every blank field (description, scientific name, prevention tips, reference image, JSON lists, a missing symptoms key) filled from the oldest extra with a value. A same-name care instruction whose text differs is appended to the kept one before the duplicate is dropped.
- Findings 2 and 4 (second half): `_create_or_merge_new_disease` creates the row once more when the winner is gone at the re-lookup or the locked re-read, instead of dropping the diagnosis; a second collision surfaces.
- Finding 4: `_is_name_collision` falls back to the constraint name in the error message when the driver has no `diag.constraint_name` (SQLite, hand-raised errors).
- Finding 3: `DiagnosisFirstCreateRaceTest` docstring names the case-insensitive constraint; new tests cover the collision-but-no-row branch, the vanished-row branch, the message fallback and the migration field merge. `test_shared_treatment_name_keeps_the_keepers_instruction` now expects the appended text (behaviour change of finding 5).

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 3 -- venv/bin/python -m pytest apps/plant_identification/tests/test_disease_diagnosis_count.py apps/plant_identification/tests/test_disease_name_case_merge_migration.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g9/636-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 23 passed, 2 warnings in 19.48s ========================
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
