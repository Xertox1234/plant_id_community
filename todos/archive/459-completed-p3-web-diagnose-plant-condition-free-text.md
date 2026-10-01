---
status: completed
priority: p3
issue_id: "459"
tags: [web, diagnosis, bug]
dependencies: []
source_review: "todos/archive/444-completed-p3-mobile-diagnose-missing.md"
triage: ready
triaged: 2026-09-30
---

# Web `/diagnose` sends free-text plant condition to a choices field

## Problem

`web/src/pages/diagnosis/DiseaseDiagnosePage.tsx` renders "Plant condition
(optional)" as a free-text `<input>`, and `diseaseService.submitDiagnosis`
posts whatever was typed as `plant_condition`. The backend field
(`PlantDiseaseRequest.plant_condition`,
`backend/apps/plant_identification/models.py`) is a `CharField` with
`choices` (`excellent`, `good`, `fair`, `poor`, `critical`), so the serializer
rejects any other value with a 400. A user who types "yellowing" gets
"Failed to submit diagnosis" and no idea why.

Found while building the mobile Diagnose screen (todo 444), which uses a
dropdown of the five choices.

## Acceptance Criteria

- [x] The web field is a `<select>` of the model's five choices, with an
      empty "not specified" option that sends nothing.
- [x] A test submits a chosen condition and asserts the posted key.

## Work Log

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- `DiseaseDiagnosePage.tsx`: the free-text "Plant condition" `<input>` is now a
  `<select>` of the five `PlantDiseaseRequest.plant_condition` keys (same labels
  as the model and the mobile screen), plus an empty "not specified" option.
  The value is narrowed with a type guard rather than a cast.
- New `PlantCondition` union in `web/src/types/diagnosis.ts`;
  `SubmitDiagnosisInput.plant_condition` is typed with it, so free text no
  longer type-checks.
- Tests: the page test selects "Poor" and asserts `plant_condition: 'poor'`
  reaches `submitDiagnosis`; another asserts the option list and that "not
  specified" sends `undefined`; the service test asserts the multipart
  `plant_condition` key is `poor` when chosen and absent otherwise. Both new
  page tests fail against the old page (mutation-checked).

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-1/web && npx vitest run --reporter=verbose src/pages/diagnosis/DiseaseDiagnosePage.test.tsx src/services/diseaseService.test.ts` — evidence `.sweep-evidence/g1/459-ac0.txt`, last lines:

  ```text

   Test Files  2 passed (2)
        Tests  11 passed (11)
     Start at  19:36:58
     Duration  1.25s (transform 78ms, setup 208ms, import 271ms, tests 343ms, environment 999ms)
  ```

- AC 2: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-1/web && npx vitest run --reporter=verbose src/pages/diagnosis/DiseaseDiagnosePage.test.tsx src/services/diseaseService.test.ts` — evidence `.sweep-evidence/g1/459-ac1.txt`, last lines:

  ```text

   Test Files  2 passed (2)
        Tests  11 passed (11)
     Start at  19:37:06
     Duration  906ms (transform 86ms, setup 118ms, import 202ms, tests 352ms, environment 531ms)
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
