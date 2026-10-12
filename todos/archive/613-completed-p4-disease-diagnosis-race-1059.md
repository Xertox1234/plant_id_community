---
status: completed
priority: p4
issue_id: "613"
tags: [backend, plant-id, database, follow-ups]
dependencies: []
owner_decision: "Items 1-2: data migration merges case-variant disease_name groups into the oldest row (re-point FKs + M2M, sum diagnosis_count, delete extras), then add UniqueConstraint(Lower('disease_name')); no prod count needed. Items 3-5: fix as usual (2026-10-11)"
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1059 (todo 594, disease diagnosis first-create race)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1059 (todo 594, disease diagnosis first-create race). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Items about the case-sensitive `disease_name` uniqueness need a data decision: a `UniqueConstraint(Lower('disease_name'))` migration must first dedupe any case-variant rows already in production, which only the owner can check.

## Findings

PR #1059 (todo sweep run 2026-10-11-2219, group g11, todos 594); follow-ups: verified.

1. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:90` The race fix assumes the loser's insert hits the unique disease_name constraint, but that constraint is case-sensitive while the lookup uses iexact. Concurrent first diagnoses of 'Black Spot' and 'black spot' both insert and leave duplicate rows. This predates the PR. | also: The race fallback only covers an exact-case collision. disease_name is unique=True (case-sensitive) but the lookup is iexact, so concurrent first diagnoses of 'Black Spot' and 'black spot' both insert and leave two rows. Later iexact .first() calls then merge into whichever row sorts first. | The race fix depends on the unique disease_name constraint, which is case-sensitive, but the lookup uses iexact. Two concurrent first diagnoses named 'Black Spot' and 'black spot' both insert with no IntegrityError and leave duplicate rows. The bug predates this change, but the fix does not cover it. | The race recovery relies on the case-sensitive unique disease_name, but the lookup uses iexact. Two concurrent first diagnoses named 'Black Spot' and 'black spot' create two rows with no IntegrityError, and later .first() lookups pick either one. This was already true before the diff, but the new docstring says both diagnoses are always counted. | The race fix depends on the case-sensitive unique disease_name, but the lookup uses iexact. Two concurrent first diagnoses named 'Black Spot' and 'black spot' both insert without an IntegrityError, so duplicate rows still land. This predates the diff, but the docstring says the race is closed.
2. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:107` The IntegrityError fallback merges into whatever row the iexact lookup returns. A case-variant row, or an IntegrityError from a different constraint while a same-name row exists, is merged into silently and the real error is never surfaced.
3. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:110` When the loser of the create race is merged, its plant species is never added to affected_plants and its description is not saved. Only_create_new_disease links the species, and the savepoint rolled that back. The existing-row path already behaves this way. | also: When a racing create loses and is merged, the loser's request.plant_species is not added to affected_plants: only _create_new_disease links it, and its savepoint rolled that back. The existing-row update path already behaved this way, and the old code dropped the whole diagnosis, so this is a minor data-completeness gap. | The loser-of-race merge path skips the affected_plants link that _create_new_disease adds, so the loser's plant species is not recorded on the winner's row.
4. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:56` The lookup no longer locks the row. If the row is deleted between the lookup and select_for_update().get(pk) in _update_existing_disease, DoesNotExist is raised. The broad except swallows it and returns None, so the diagnosis is dropped instead of being created again. | also: The lookup no longer locks the row. If the row is deleted between the lookup and the re-read, select_for_update().get(pk=...) raises DoesNotExist, the outer except swallows it, and the diagnosis is dropped (returns None) instead of being created again.
5. **low** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:150` The SET-list test parses the UPDATE SQL with a regex on quoted column names and hardcodes the column set, including updated_at, which appears only because of auto_now. An ORM quoting change or a new auto_now field could fail the test without any regression. | also: The SET-list test parses SQL with a regex and hardcodes the column set. It is brittle against ORM quoting changes and any new auto_now field.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1059 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g11`.

### 2026-10-11 - Owner decision: merge migration, then a case-insensitive constraint

**Items 1–2.** Migration 1 (RunPython) groups `PlantDiseaseDatabase` rows by `Lower('disease_name')`. In each
group with more than one row it keeps the **oldest** row and moves everything onto it: `care_instructions`
(FK, CASCADE, so re-point **before** deleting), diagnosis results (FK), and `affected_plants` (M2M, union).
It adds up `diagnosis_count`, then deletes the extra rows. Migration 2 replaces the case-sensitive uniqueness
with `UniqueConstraint(Lower('disease_name'), name=…)`. Follow `docs/rules/database.md` for migrations: no
f-string SQL, and give the data migration a reverse that does nothing.

Test the merge with fixture rows 'Black Spot' and 'black spot', each with a care instruction, a diagnosis and
an affected plant. After the merge there is one row, and every reference and count is on it. Then the race
fallback can rely on the constraint, so item 2's merge into a case-variant row is correct by construction.
Nobody needs to count prod rows by hand, because the migration handles any data.

**Items 3–5:** fix or decline as usual.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- **Items 1-2 (fixed, per the owner decision).** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py` folds every group of `disease_name` rows that differ only in case into its oldest row: care instructions and diagnosis results are re-pointed before the extras are deleted, `affected_plants` is the union, and `diagnosis_count` is the sum. The reverse does nothing. `0029_disease_name_lower_unique.py` drops `unique=True` and adds `UniqueConstraint(Lower("disease_name"), name="plant_disease_name_lower_unique")`. The service's name lookup now compares with `LOWER()` as well, so lookup and constraint agree. The IntegrityError fallback merges only when that constraint fired (read from the driver's `diag.constraint_name`), so any other IntegrityError surfaces even when a same-name row exists. Tests: `backend/apps/plant_identification/tests/test_disease_name_case_merge_migration.py` (migrates 0027 -> 0029 over 'black spot'/'Black Spot' fixtures), and the case-variant race and other-constraint tests in `test_disease_diagnosis_count.py`.
- **Item 3 (species fixed, description declined).** `_update_existing_disease` now adds the diagnosis's plant species to `affected_plants`, so both the lost-race merge and the ordinary existing-row merge record it. The description is not written on a merge: the merge writes only the fields it combines, so a moderator's edit to the description survives (todo 568, `test_update_writes_only_the_merged_fields`), and the winner's row already has the API description.
- **Item 4 (fixed).** When the row is deleted between the lookup and the locked re-read, `store_disease_if_qualified` catches `DoesNotExist` and creates the row again instead of dropping the diagnosis.
- **Item 5 (declined).** The SET-list test pins the `update_fields` contract on purpose, and `updated_at` is named explicitly in that list, not added by `auto_now`. A new column in the UPDATE should fail it. Its regex matches Django's quoted identifiers on PostgreSQL, the only backend the suite runs.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `sh -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest backend/apps/plant_identification/tests/test_disease_diagnosis_count.py backend/apps/plant_identification/tests/test_disease_name_case_merge_migration.py --create-db -v -p no:cacheprovider && grep -n "^- \*\*Item" todos/archive/613-completed-p4-disease-diagnosis-race-1059.md'` — evidence `.sweep-evidence/g11/613-ac0.txt` (not committed), last lines:

  ```text
  ======================= 17 passed, 2 warnings in 18.83s ========================
  59:- **Items 1-2 (fixed, per the owner decision).** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py` folds every group of `disease_name` rows that differ only in case into its oldest row: care instructions and diagnosis results are re-pointed before the extras are deleted, `affected_plants` is the union, and `diagnosis_count` is the sum. The reverse does nothing. `0029_disease_name_lower_unique.py` drops `unique=True` and adds `UniqueConstraint(Lower("disease_name"), name="plant_disease_name_lower_unique")`. The service's name lookup now compares with `LOWER()` as well, so lookup and constraint agree. The IntegrityError fallback merges only when that constraint fired (read from the driver's `diag.constraint_name`), so any other IntegrityError surfaces even when a same-name row exists. Tests: `backend/apps/plant_identification/tests/test_disease_name_case_merge_migration.py` (migrates 0027 -> 0029 over 'black spot'/'Black Spot' fixtures), and the case-variant race and other-constraint tests in `test_disease_diagnosis_count.py`.
  60:- **Item 3 (species fixed, description declined).** `_update_existing_disease` now adds the diagnosis's plant species to `affected_plants`, so both the lost-race merge and the ordinary existing-row merge record it. The description is not written on a merge: the merge writes only the fields it combines, so a moderator's edit to the description survives (todo 568, `test_update_writes_only_the_merged_fields`), and the winner's row already has the API description.
  61:- **Item 4 (fixed).** When the row is deleted between the lookup and the locked re-read, `store_disease_if_qualified` catches `DoesNotExist` and creates the row again instead of dropping the diagnosis.
  62:- **Item 5 (declined).** The SET-list test pins the `update_fields` contract on purpose, and `updated_at` is named explicitly in that list, not added by `auto_now`. A new column in the UPDATE should fail it. Its regex matches Django's quoted identifiers on PostgreSQL, the only backend the suite runs.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
