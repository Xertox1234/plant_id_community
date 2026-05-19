---
status: completed
priority: p2
issue_id: "080"
tags: [testing, tech-debt, audit-2026-05-17]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "H37,H38"
---

# Remove or rewrite stale DiagnosisCard test/API modules + fix PlantDiseaseDatabaseSerializer

## Problem

`DiagnosisCard` was added in migration `0020_add_diagnosis_card_and_reminder_models.py`
and removed in `0025_remove_diagnosisreminder_diagnosis_card_and_more.py`, but several
modules still import it. The test modules now raise `ImportError` on collection — this
keeps the backend test baseline at 2 errors. The breakage was previously hidden by the
`tests.py`/`tests/` discovery collision (audit C1); fixing C1 unmasked it.

## Findings

- `backend/apps/plant_identification/test_diagnosis_api.py:15` and
  `test_diagnosis_models.py:16` — `ImportError: cannot import name 'DiagnosisCard'
  from 'apps.plant_identification.models'`.
- `backend/apps/plant_identification/api/diagnosis_serializers.py` and
  `diagnosis_viewsets.py` also reference `DiagnosisCard` — verify whether they are
  live (routed) dead code or only string/comment references.
- **H38** — `PlantDiseaseDatabaseSerializer` (`apps/plant_identification/serializers.py`)
  lists a `created_at` field that the `PlantDiseaseDatabase` model does not have.
  `ImproperlyConfigured` is raised whenever the serializer's fields are built,
  which **breaks `drf-spectacular` OpenAPI schema generation** (`backend/test_schema.py`
  exits non-zero). Fix: remove `created_at` from the serializer `fields`, or add the
  column to the model if it was intended.

## Recommended Action

1. Determine whether the diagnosis-card feature was fully removed or replaced
   (compare against `SavedDiagnosis`, the surviving model).
2. If removed: delete the stale `test_diagnosis_{api,models}.py` and any unused
   `api/diagnosis_{serializers,viewsets}.py`.
3. If replaced: rewrite the tests/serializers against the current model.
4. Confirm `python manage.py test apps.plant_identification --noinput` reports 0 errors.

## Technical Details

Current diagnosis model: `apps/plant_identification/models.py:1412 class SavedDiagnosis`.
Removal migration: `apps/plant_identification/migrations/0025_*`.

## Acceptance Criteria

- [x] No module imports the non-existent `DiagnosisCard`.
- [x] `python manage.py test apps.plant_identification --noinput` — 0 errors.

## Work Log

### 2026-05-17 - Created

- Discovered during Phase 3 verification of the 2026-05-17 full audit.

### 2026-05-18 - Started by completing-todos skill (run 2026-05-18-2300)

- Picked up by automated workflow.

### 2026-05-18 - Implementation

- Confirmed `DiagnosisCard` + `DiagnosisReminder` models were deleted in
  migration `0025`; only `SavedDiagnosis` survives, and the router registers
  `SavedDiagnosisViewSet` (not `DiagnosisCardViewSet`).
- `api/diagnosis_serializers.py` and `api/diagnosis_viewsets.py` formed a
  self-contained dead-code island (nothing else imports them). Deleted all four
  stale modules via `git rm`: `test_diagnosis_api.py`, `test_diagnosis_models.py`,
  `api/diagnosis_serializers.py`, `api/diagnosis_viewsets.py`.
- H38: `PlantDiseaseDatabase` has `first_diagnosed` + `updated_at` but no
  `created_at`. Removed the invalid `created_at` from `PlantDiseaseDatabaseSerializer.Meta.fields`.
- Verification:
  - `grep -rn "DiagnosisCard" --include="*.py" apps/ | grep -v /migrations/` → NONE.
  - `python manage.py test apps.plant_identification --noinput` → `Ran 104 tests in 57.575s` / `OK` / exit 0.

### 2026-05-18 - Completed by completing-todos skill (run 2026-05-18-2300)

- Verification: both acceptance criteria passed (no `DiagnosisCard` imports; 104 tests OK).
- Review: code-review-orchestrator dispatched (django-drf / api-design / test-quality / performance reviewers) — 0 findings, no blocking.
- Source audit `docs/audits/2026-05-17-full.md`: H37 and H38 table rows marked `fixed`. Doc not renamed COMPLETED — the audit has many other open findings.
