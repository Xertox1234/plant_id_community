---
status: completed
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

- [x] `PlantSuggestion` interface exists with `probability: number` required
      and no `confidence` field
- [x] `PlantIdentificationResult.suggestions` typed as `PlantSuggestion[]`
- [x] `tsc --noEmit` clean; full `vitest run` green

## Work Log

### 2026-08-28 - Implemented

- Split `PlantSuggestion` out of `plantId.ts`: `probability: number`
  required, no `confidence` field. `PlantIdentificationResult.confidence`
  reverted to required (todo 313 had made it optional only to fix the
  immediate crash) and its `probability` field dropped — grep confirmed
  `.probability` is read only on suggestion/disease items, never on the
  top-level result, in the actual call sites.
- Retyped every call site the todo named: `getPlantKey` (`plantUtils.ts`),
  `IdentificationResults`'s `onSavePlant` prop, `IdentifyPage.handleSavePlant`.
  Also caught by the compiler and fixed: `handleAskCommunity`'s candidate
  mapping (not explicitly named in the todo, but reads `s.probability` on a
  suggestion item the same way).
- Removed the now-dead `?? suggestion.confidence ?? 0` fallback at all 3
  runtime sites (`getPlantKey`, `IdentifyPage`'s save payload, and
  `IdentificationResults`'s `ConfidencePill`) — with `probability` a required
  field on `PlantSuggestion`, the fallback checked a case the type no longer
  allows to exist. `?? 0` was also dropped since `probability` can no longer
  be `undefined`.
- Fixed the 3 test files the type change broke: `plantUtils.test.ts` and
  `IdentificationResults.test.tsx` each had a test exercising the
  now-removed fallback ("falls back to confidence", "renders 0% for a
  suggestion with neither field") — replaced with an equivalent test for the
  one case still worth pinning (a genuine `probability: 0` renders "0%", not
  "NaN%" or something falsy-coerced). `plantIdService.test.ts` had a stray
  `probability` field on a top-level-result fixture that was never asserted
  on; dropped.
- **Verified the protection is real**, not just "it compiles now": wrote a
  scratch file reproducing the exact todo-313 mistake
  (`function bad(s: PlantSuggestion) { return s.confidence; }`), confirmed
  `tsc --noEmit` rejects it with `Property 'confidence' does not exist on
  type 'PlantSuggestion'`, then deleted the scratch file and re-confirmed
  clean.
- Verification:

  ```
  $ npx tsc --noEmit
  (no output — clean)

  $ npm run lint
  ✖ 1 problem (0 errors, 1 warning)   # pre-existing, in generated coverage/ output, unrelated

  $ npx vitest run
  Test Files  84 passed (84)
       Tests  931 passed (931)
  ```

### 2026-08-28 - Code review (react-typescript-reviewer)

- **MEDIUM finding, fixed**: `IdentifyPage.test.tsx`'s two RESULTS fixtures
  (`RESULTS`, `REAL_SHAPE_RESULTS`) were passed through
  `as unknown as PlantIdentificationResult`, which erases structural
  checking — the object literals were never actually validated against the
  new split types. The reviewer's evidence was concrete: `RESULTS`'s
  suggestion items still carried a stale `confidence` key (removed
  everywhere else in this diff) that the cast let survive silently. Fixed
  by typing both fixtures directly as `PlantIdentificationResult` and
  dropping the casts; `tsc` then rejected the stale `confidence` keys on
  the suggestion items exactly as intended, confirming the cast really had
  been hiding drift. Removed those keys, re-verified `tsc --noEmit` clean
  and the file's own 8 tests + full suite (931) green.
- **LOW finding, accepted — not fixed**: `plantIdService.identifyPlant()`
  has no runtime schema validation at the network boundary, so the type
  split's guarantees are compile-time only — a future backend response
  missing `probability` on a suggestion item would still crash at runtime,
  same failure mode as todo 313, just undetected until then. Reviewer
  confirmed this is pre-existing and unrelated to this diff (every other
  field on `PlantIdentificationResult`/`SavePlantInput` has the same
  no-validation trust level), not something this diff's scope covers.
  Left as-is; flagged here in case the network boundary is ever revisited.

### 2026-08-28 - Completed by todo-sweep

- Verification: all 3 acceptance criteria passed — `tsc --noEmit` clean,
  full `vitest run` 931/931 green (see Work Log above for exact output).
- Review: react-typescript-reviewer found 2 findings — 1 MEDIUM fixed
  (drift-hiding `as unknown as` casts in test fixtures), 1 LOW accepted as
  pre-existing and out of scope (no runtime schema validation at the
  network boundary).
- `source_review` is a todo cross-reference ("todo 313"), not a
  `docs/reviews/*.md` path — no Finding Status section to check off.

## Notes

Filed from a MEDIUM finding surfaced during todo 313's code review
(react-typescript-reviewer): "the exact root cause of the todo-313 crash is
a type-conflation the diff documents but does not close off." Deferred
rather than fixed inline — todo 313 was a p1 crash fix and this is a
type-safety hardening with a broader (though still small) call-site blast
radius; kept separate per surgical-changes discipline.
