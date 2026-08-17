---
status: pending
priority: p1
issue_id: "313"
tags: [web, react, plant-identification, bug, crash]
dependencies: []
---

# Identify results screen crashes on every successful identification (getPlantKey reads a field the API never sends)

## Problem

`IdentificationResults.tsx` crashes to the app's generic error boundary
("Oops! Something went wrong") on **every** successful plant identification
that returns at least one suggestion — which is the normal, expected case.
The crash is unconditional: it happens during render for every user
(authenticated or not), not only on a save-button click. This breaks the
core "AI Plant Identification" feature end to end — a user can upload a
photo, wait for analysis, and never see a single result.

Found during the manual visual QA pass for Canopy PR 4
(`docs/superpowers/specs/2026-08-16-canopy-areas-design.md` §6.4), which
that PR's merge (2026-08-17) shipped without running. Confirmed **not**
caused by Canopy PR 4 — see Findings.

## Findings

- Live-reproduced 2026-08-17: real login (`e2e_test_user`), real photo
  upload, real `POST /api/v1/plant-identification/identify/` call (200 OK,
  live Plant.id + PlantNet APIs, no mocking). The backend correctly
  identified the plant (Monstera deliciosa, 99% confidence) and returned a
  normal `suggestions` array. The frontend then crashed to the error
  boundary instead of rendering results.
- Browser console captured the exact stack trace:

  ```
  TypeError: Cannot read properties of undefined (reading 'toFixed')
      at getPlantKey (web/src/utils/plantUtils.ts:9:43)
      at web/src/components/PlantIdentification/IdentificationResults.tsx:179:24
      at IdentificationResults (.../IdentificationResults.tsx:100:35)
  ```

  (line numbers from the dev bundle's own reporting; see Technical Details
  for the current file's real line numbers.)
- **Root cause — a type/reality mismatch, not a Canopy regression:**
  `PlantIdentificationResult` (`web/src/types/plantId.ts:8-32`) declares
  `confidence: number` as a **required** field (line 10) alongside an
  unrelated, separately-added `probability?: number` (line 24, comment:
  "Properties for compatibility with IdentificationResults component").
  The live API response's `suggestions[]` array items only ever populate
  `probability` (confirmed from the actual response body — each suggestion
  has `"probability": 0.99` etc., **no `confidence` key at all**); only the
  top-level result object carries `confidence`. `getPlantKey()`
  (`web/src/utils/plantUtils.ts:10-13`) calls
  `suggestion.confidence.toFixed(4)` — `suggestion.confidence` is
  `undefined` for every array item, so this throws unconditionally.
  `strict: false` (`web/CLAUDE.md`) doesn't change this: property-existence
  typing isn't a strict-mode-gated check, but the type itself is simply
  wrong — it promises a field the real runtime shape never sends for
  suggestion items — so `tsc` has no signal that would catch it.
- **Two call sites hit this**, both pre-existing (see below):
  1. `IdentificationResults.tsx:107` — inside `onSavePlant && (() => {...})()`,
     which runs **unconditionally during render** for every suggestion,
     because `onSavePlant={handleSavePlant}` is passed to
     `<IdentificationResults>` unconditionally in `IdentifyPage.tsx:247`
     (not gated on `isAuthenticated`). This is the crash that's actually
     hit — it fires before a user can even see results, logged in or not.
  2. `IdentifyPage.tsx:145` (`getPlantKey(suggestion)` inside
     `handleSavePlant`) and `:157` (`confidence: suggestion.confidence` in
     the save payload) — unreachable right now because (1) crashes first,
     but would independently send `confidence: undefined` to the backend
     even if the render crash were fixed and even after todo 311's dead-route
     fix lands.
- **Confirmed pre-existing, not introduced by Canopy PR 4:** the exact
  `onSavePlant && (() => { const plantKey = getPlantKey(suggestion); ...`
  block already existed, unchanged, at `main~20`
  (`git show main~20:web/src/components/PlantIdentification/IdentificationResults.tsx`).
  `plantUtils.ts` hasn't been touched since the original TypeScript
  migration (`ed40134`/`ceec5c0`, both long before any Canopy work).
  Canopy PR 4's Task 3 wrapped this same block in `Card` and added a
  `ConfidencePill`/`suffix` prop — it did not touch the `getPlantKey` call
  or the `confidence` field at all.
- **Why automated tests never caught this:** every test double for a
  "suggestion" object (component tests, e2e mocks) apparently includes a
  `confidence` field matching the type declaration, rather than a
  realistic API response shaped like the real backend's (`probability`
  only, on suggestion items). This is exactly the gap manual QA with a
  **real** identification call — never previously run per Canopy PR 4's
  spec §6.4 — was designed to catch.

## Recommended Action

1. Fix `getPlantKey()` (`web/src/utils/plantUtils.ts:10-13`) to use
   `suggestion.probability ?? suggestion.confidence` (or just
   `suggestion.probability`, if `confidence` truly never appears on
   suggestion-array items — confirm against the top-level non-array
   identify response too, which does carry `confidence`).
2. Fix `IdentifyPage.tsx:157`'s save payload
   (`confidence: suggestion.confidence`) the same way, so a saved plant's
   `care_instructions_json.confidence` isn't silently `undefined`.
3. Consider whether `PlantIdentificationResult.confidence` should be
   `confidence?: number` (optional) at the type level, given the real API
   never guarantees it on suggestion items — the current `required` typing
   is what let this compile without a `tsc` error in the first place.
4. Add a regression test for `getPlantKey()` (currently has zero direct
   test coverage) using a suggestion shaped like the **real** API response
   (`probability` only, no `confidence`) — the exact shape that crashed.
5. Add or extend an `IdentificationResults` test that renders with
   `onSavePlant` set and a `probability`-only suggestion (no `confidence`
   key at all, not just `confidence: undefined`) to catch this class of
   bug at the component level going forward.
6. Once fixed, re-run the manual QA flow (real login → real identify) to
   confirm results render and the crash boundary no longer fires.

## Technical Details

- Crash site: `web/src/utils/plantUtils.ts:11`
  (`suggestion.confidence.toFixed(4)`)
- Triggering call: `web/src/components/PlantIdentification/IdentificationResults.tsx:107`
  (inside the `onSavePlant && (() => {...})()` IIFE, `:105-138`)
- Unconditional prop: `web/src/pages/IdentifyPage.tsx:247`
  (`onSavePlant={handleSavePlant}`, not gated on `isAuthenticated`)
- Secondary call site (unreachable until the above is fixed):
  `web/src/pages/IdentifyPage.tsx:145` and `:157`
- Type declaration: `web/src/types/plantId.ts:8-32`
  (`confidence: number` required at line 10, `probability?: number`
  optional at line 24)
- Real API response observed (`POST /api/v1/plant-identification/identify/`,
  live Plant.id + PlantNet), abbreviated:

  ```json
  {
    "confidence": 0.99,
    "suggestions": [
      { "plant_name": "Monstera deliciosa", "probability": 0.99, "source": "plant_id", ... },
      { "plant_name": "Swiss cheese-plant", "probability": 0.03577, "source": "plantnet", ... }
    ]
  }
  ```

  Note `confidence` only at top level; every `suggestions[]` item has
  `probability`, never `confidence`.

## Acceptance Criteria

- [ ] A real (or realistically-shaped, `probability`-only) identification
      result with `suggestions` renders in `IdentificationResults` without
      throwing
- [ ] `getPlantKey()` has a regression test using a `probability`-only
      suggestion (no `confidence` key)
- [ ] `IdentifyPage.tsx`'s save payload no longer sends
      `confidence: undefined`
- [ ] Manual smoke test: real login → real identify → results visible, no
      error boundary

## Work Log

### 2026-08-17 - Filed

- Found and root-caused by Claude during Canopy PR 4's deferred manual
  visual QA pass (spec §6.4), run after the PR (#558) had already merged.
  Confirmed pre-existing via git history (unrelated to Canopy PR 4's
  changes) before filing at p1 given severity: this breaks the app's core
  feature for every user, on every successful identification.

## Notes

- p1, not p2/p3: unlike todo 311 (save-to-collection's dead route, which
  at least lets a user *see* their identification before the save action
  fails) or todo 312 (e2e-only, no user impact), this crash means **no
  identification result is ever visible to any user**, logged in or not —
  the error boundary fires before the results UI can render at all. This
  is the app's primary advertised feature ("Houseplant MD — the plant
  clinic" / "AI Plant Identification").
- Related: todo 311 (same `IdentifyPage.tsx`/`plantIdService.ts` save
  flow, independent bug, fix that one too but it won't matter until this
  one is fixed since the crash happens first); Canopy PR 4 / #558
  (`docs/superpowers/plans/2026-08-16-canopy-areas.md`,
  `docs/superpowers/specs/2026-08-16-canopy-areas-design.md` §6.4 — the
  QA pass that found this).
