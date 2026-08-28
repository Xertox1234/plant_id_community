---
status: pending
priority: p3
issue_id: "316"
tags: [web, typescript, plant-identification, type-safety]
dependencies: []
source_review: "todo 313 (react-typescript-reviewer, code review round, 2026-08-28)"
---

# Split PlantSuggestion out of PlantIdentificationResult to close off the todo-313 crash class structurally

## Problem

`PlantIdentificationResult` (`web/src/types/plantId.ts`) is used recursively
as both the top-level identify-response shape AND the type of each item in
`suggestions?: PlantIdentificationResult[]`. Todo 313 fixed the immediate
crash (`suggestion.confidence.toFixed()` throwing because suggestion items
never carry `confidence`, only `probability`) by making `confidence`
optional and adding `?? probability` fallbacks at every read site — but the
single shared interface still lets a future author write
`suggestion.confidence` again and have it compile silently, since nothing at
the type level distinguishes "the top-level result" from "an item inside
`suggestions[]`".

## Recommended Action

Split into two interfaces:

- `PlantSuggestion` — `probability: number` (required), no `confidence`
  field. Used for `suggestions?: PlantSuggestion[]` and
  `disease_suggestions` items.
- `PlantIdentificationResult` — keeps `confidence: number` (required, it's
  always present at the top level), plus `suggestions?: PlantSuggestion[]`.

This makes `suggestion.confidence` a compile error again — the same
protection `strict: false` would give under `strictNullChecks`, achieved
structurally instead.

## Technical Details

- `web/src/types/plantId.ts:8-32` — the interface to split.
- Call sites that read a suggestion-shaped value and would need the new
  type: `IdentificationResults.tsx`, `IdentifyPage.tsx` (`handleSavePlant`,
  `handleAskCommunity`), `plantUtils.ts::getPlantKey`.
- Not urgent — todo 313's fallbacks already close the actual bug. This is
  hardening against a *recurrence* of the same class, not a live defect.

## Acceptance Criteria

- [ ] `PlantSuggestion` interface exists with `probability: number` required
      and no `confidence` field
- [ ] `PlantIdentificationResult.suggestions` typed as `PlantSuggestion[]`
- [ ] `tsc --noEmit` clean; full `vitest run` green

## Notes

Filed from a MEDIUM finding surfaced during todo 313's code review
(react-typescript-reviewer): "the exact root cause of the todo-313 crash is
a type-conflation the diff documents but does not close off." Deferred
rather than fixed inline — todo 313 was a p1 crash fix and this is a
type-safety hardening with a broader (though still small) call-site blast
radius; kept separate per surgical-changes discipline.
