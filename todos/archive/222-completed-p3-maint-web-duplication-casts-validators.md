---
status: completed
priority: p3
issue_id: "222"
tags: [maintainability, web, react, typescript, audit]
dependencies: []
source_review: "docs/audits/2026-06-09-maintainability.md"
source_finding: "M12,M13,M14,M15,M16,L8,L9"
---

# Maintainability: web duplication, casts, coupling & unwired validators

## Problem

The 2026-06-09 maintainability audit found web-frontend duplication that has
drifted, a harmful type-escape at an API boundary, edit-in-N-places coupling,
and a `validation.ts` "library" that is mostly unwired — including tested
**security validators** whose deletion-vs-wiring is a judgment call. Deferred
from that audit (fix-now batch was dead-code + hollow-tests).

## Findings

Source: `docs/audits/2026-06-09-maintainability.md`.

- **M12 (residual)** `validation.ts` has ~14 unused exports; the audit removed the
  clearly-dead `getNameError`. The rest are **tested, security-focused validators**
  (`validateSlug/Token/ContentType/Url/Integer/Pagination/CategorySlug/FileType`,
  `sanitizeSearchQuery`). Decide per-validator: **wire up** where it applies
  (e.g. `validateFileType` at `ImageUploadWidget`, `sanitizeSearchQuery` at the
  search box) or **remove** with its tests. Do NOT blind-delete — some may close
  latent client-side validation gaps. `web/src/utils/validation.ts`.
- **M13** Case-collision sanitize names (`sanitizeHtml` live vs `sanitizeHTML` dead vs `domSanitizer.sanitizeHTML` async) + needless `Promise` wrapper forcing `useState`/`useEffect`/`isMounted`/"Loading…" in `SafeHTML`. `web/src/utils/sanitize.ts:207,286,338`; `domSanitizer.ts`; `StreamFieldRenderer.tsx:16-37`.
- **M14** `handlePageChange` byte-identical in two forum pages; pagination render block copy-pasted and **already diverged** (variant, "Page X of Y" vs "Page X", `<=1` vs `===1`). `pages/forum/ThreadListPage.tsx:118-128,262-281`; `SearchPage.tsx:240-250,495-514`.
- **M15** Harmful double-cast at the diagnosis-create API boundary: `cardData as unknown as CreateDiagnosisCardInput` defeats the compiler. `components/diagnosis/SaveDiagnosisModal.tsx:59,83`. Type `cardData` as `CreateDiagnosisCardInput` directly.
- **M16** Diagnosis StreamField block-type dispatch switched in 3 spots (menu array + editor switch + renderer switch) → add-a-block = 3 edits; labels/icons hard-coded in `case` JSX despite `BLOCK_TYPES`. `components/diagnosis/StreamFieldEditor.tsx:20-27,58`; `DiagnosisDetailPage.tsx:62-180`.
- **L8** `getSeverityColor` duplicated in two files with **drifted** signatures (`string` vs `SeverityAssessment`). `components/diagnosis/DiagnosisCard.tsx:24`; `DiagnosisDetailPage.tsx:37`.
- **L9** `Attachment` type has 5 overlapping URL fields forcing `getAttachmentImageUrl` to fall through all 5. `web/src/types/forum.ts:75-79`.

## Recommended Action

1. M12: per-validator wire-or-remove decision; if wiring, add the call site + keep the test; if removing, delete export + test together.
2. M13: collapse to one `sanitizeHtml`; drop the needless async wrapper + the `SafeHTML` loading scaffolding.
3. M14: extract shared `handlePageChange` + a `<Pagination>` component; unify the two forum pages.
4. M15: type `cardData` precisely; remove the double-cast.
5. M16: drive editor + renderer + menu from one block-type registry.
6. L8: single-source `getSeverityColor` with the precise type; L9: collapse `Attachment` URL fields to the authoritative one.

## Technical Details

Per-finding file:line above. Patterns: `web/docs/patterns/react-typescript.md`,
`docs/rules/react.md`, `docs/rules/typescript.md`.

## Acceptance Criteria

- [~] M12 validators each wired or removed — **split to todo 225** (security
      judgment call; user chose to defer to its own todo). Investigation done:
      all 9 validators have 0 import sites; `validateFileType` is redundant with
      ImageUploadWidget's MIME check; `sanitizeSearchQuery` is the one genuine
      wire site.
- [x] M13 single sanitize fn; no needless async/loading scaffolding.
      (done 2026-06-10 — `SafeHTML` uses the sync `createSafeMarkup` from
      `utils/sanitize` directly (no useState/useEffect/loading); dead
      `sanitizeHTML` removed from `sanitize.ts`; orphaned `utils/domSanitizer.ts`
      deleted.)
- [x] M14 pagination single-sourced across forum pages.
      (done 2026-06-10 — `components/ui/Pagination.tsx` + `hooks/useHandlePageChange.ts`
      replace the byte-identical handler and the drifted JSX in ThreadListPage and
      SearchPage.)
- [x] M15 double-cast removed; `tsc` clean.
      (done 2026-06-10 — `cardData` typed as `CreateDiagnosisCardInput`; the
      `as unknown as` double-cast removed. It was hiding real mismatches:
      `diagnosis_result` made optional (matches the code + backend), non-create
      `plant_recovered` dropped, and the two enum fields narrowed at the boundary.)
- [~] M16 block-type registry single-sourced — **split to todo 225** (a
      component-extraction refactor; the per-block editor/renderer JSX genuinely
      differ with per-block theming — not a mechanical dedup, not safe to rush).
- [x] L8/L9 addressed; `npm run test` + `type-check` + `lint` green.
      (done 2026-06-10 — L8: `utils/diagnosisDisplay.ts::getSeverityColor`
      (typed `SeverityAssessment`) single-sources the two drifted copies. L9:
      `Attachment` narrowed to the authoritative `image_url`/`thumbnail_url`
      (the mapper filled 5 aliases from 2 backend fields); `getAttachmentImageUrl`
      + mapper + tests updated. **type-check + 94 affected tests + lint all green.**)

## Work Log

### 2026-06-10 - Completed (5 of 7 findings); M12 + M16 split to todo 225

- Completed the five mechanical dedups: M13, M14, M15, L8, L9.
  Verification: `npm run type-check` clean, `eslint` clean on all changed files,
  and `vitest run` on the affected suites = **94 passed (4 files)**.
- M12 (security validators) split to **todo 225** per the user's explicit choice
  to defer it to its own todo. M16 (block-type registry) also split to 225: its
  proper fix is a component-extraction refactor (per-block editor/renderer JSX
  with per-block theming), not a mechanical dedup, and was not safe to rush.
- Review: deferred to the run's end-of-sweep code-review-orchestrator pass.

### 2026-06-10 - Started by completing-todos skill (run 2026-06-10-0251)

- Picked up by automated workflow (final todo of the sweep). M12 (wire-or-remove
  the tested security validators) is the one real judgment call — handled
  directly, not blind-deleted.

### 2026-06-09 - Created

- Deferred from the 2026-06-09 maintainability audit. `getNameError` (clear dead)
  removed in that audit; security validators (M12) intentionally left for a
  wire-vs-remove decision per the deletion-safety guidance.

## Notes

p3: quality/maintenance, no user-facing bug. M12 is the only item with a real
judgment call (don't delete potentially-should-be-wired security validators).
