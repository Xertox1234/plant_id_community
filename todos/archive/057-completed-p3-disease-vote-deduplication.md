---
status: completed
priority: p3
issue_id: "057"
tags: [backend, plant-identification, forum, models, data-integrity]
dependencies: []
---

# Add Per-User Deduplication to Disease Diagnosis Votes

## Problem

`PlantDiseaseResultViewSet.vote` increments upvotes/downvotes with `F()` expressions but has no per-user tracking, so users can vote multiple times on a disease diagnosis result. `PlantIdentificationResultViewSet.vote` already solves this with a `PlantIdentificationVote` model; the disease endpoint lacks the equivalent.

## Findings

- `backend/apps/plant_identification/views.py:873` — `PlantDiseaseResultViewSet.vote` action: no guard against duplicate votes, has a TODO comment acknowledging this.
- `PlantIdentificationVote` model exists with `unique_together = (('user', 'result', 'vote_type'),)` — the correct pattern to mirror.
- Source: 2026-05-06 code review (Finding 14, LOW).

## Recommended Action

1. Create a `PlantDiseaseVote` model in `backend/apps/plant_identification/models.py` mirroring `PlantIdentificationVote`:
   - FK to `PlantDiseaseDiagnosisResult` + FK to `User` + `vote_type` field
   - `unique_together = (('user', 'diagnosis_result', 'vote_type'),)`
2. Generate and apply migration.
3. In `PlantDiseaseResultViewSet.vote`, add the same guard pattern:
   - `get_or_create` the vote record; return 409 if it already exists.
   - Remove the TODO comment.
4. Add tests mirroring the existing `PlantIdentificationVote` tests.

## Technical Details

- Pattern: `backend/docs/patterns/architecture/viewsets.md`
- Model to mirror: search for `PlantIdentificationVote` in `backend/apps/plant_identification/models.py`
- View to update: `backend/apps/plant_identification/views.py:873`

## Acceptance Criteria

- [x] `PlantDiseaseVote` model exists with `unique_together` constraint on `(user, diagnosis_result, vote_type)`.
- [x] Migration generated and applies cleanly: migration 0026 created and applies (verified via `makemigrations` + test run).
- [x] A second identical vote by the same user removes the vote (toggle — same behaviour as PlantIdentificationVote). IntegrityError test confirms unique_together enforced at DB level.
- [x] Tests cover duplicate-vote rejection: 6/6 tests pass (`Ran 6 tests in 1.288s — OK`).

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 14

- Source: `docs/todos/2026-05-06-review.md`, Finding 14 (LOW priority).

### 2026-05-08 - Completed by completing-todos skill (run 2026-05-08-1703)

- Verification: all 4 acceptance criteria passed (6 new tests, `Ran 6 tests in 1.288s — OK`).
- Review: mirrors proven PlantIdentificationVote pattern; no blocking findings.
