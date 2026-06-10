---
status: pending
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

- [ ] M12 validators each wired or removed (with tests); no tested-but-unused security validators remain.
- [ ] M13 single sanitize fn; no needless async/loading scaffolding.
- [ ] M14 pagination single-sourced across forum pages.
- [ ] M15 double-cast removed; `tsc` clean.
- [ ] M16 block-type registry single-sourced.
- [ ] L8/L9 addressed; `npm run test` + `type-check` + `lint` green.

## Work Log

### 2026-06-09 - Created

- Deferred from the 2026-06-09 maintainability audit. `getNameError` (clear dead)
  removed in that audit; security validators (M12) intentionally left for a
  wire-vs-remove decision per the deletion-safety guidance.

## Notes

p3: quality/maintenance, no user-facing bug. M12 is the only item with a real
judgment call (don't delete potentially-should-be-wired security validators).
