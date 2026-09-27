---
status: pending
priority: p3
issue_id: "459"
tags: [web, diagnosis, bug]
dependencies: []
source_review: "todos/444-pending-p3-mobile-diagnose-missing.md"
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

- [ ] The web field is a `<select>` of the model's five choices, with an
      empty "not specified" option that sends nothing.
- [ ] A test submits a chosen condition and asserts the posted key.
