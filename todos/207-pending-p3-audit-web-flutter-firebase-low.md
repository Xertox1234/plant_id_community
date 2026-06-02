---
status: pending
priority: p3
issue_id: "207"
tags: [web, flutter, firebase, testing, audit]
dependencies: []
source_review: "docs/audits/2026-06-02-full.md"
source_finding: "L2, L3, L7, L8, L14, L16"
---

# Web / Flutter / Firebase low-severity polish (audit 2026-06-02)

## Problem

Six low-severity frontend/rules findings from the full audit — TypeScript
nits, dark-mode contrast, a disabled-button visual, a weak test assertion, and a
deliberate-but-flagged open storage read. Cosmetic/quality, none functional.

## Findings

- **L2 — inline prop type literals.** `web/src/components/ui/Eyebrow.tsx:5-10`
  and `GrainOverlay.tsx:7` type props inline; sibling `ClayButton` uses an
  explicit interface. Extract `EyebrowProps` / `GrainOverlayProps`.
- **L3 — double cast.** `web/src/pages/forum/SearchPage.tsx:96`
  `data as unknown as CategoriesResponse` — narrow with the existing
  `Array.isArray` guard instead.
- **L7 — dark-mode badge contrast.** Identified-badge uses
  `colorScheme.onSurface` over light `ext.leaf` → light-on-light in dark mode:
  `lib/features/results/results_screen.dart:93,98` and
  `lib/features/collection/collection_screen.dart:149`. Use a fixed on-leaf color.
- **L8 — invisible disabled ClayButton.** `lib/shared/widgets/clay_button.dart:41,47`
  disabled bg `surfaceContainerHighest` falls back to `surface` (= scaffold bg).
  Set `surfaceContainerHighest` in the scheme or use `bg3` for the disabled fill.
- **L14 — weak test assertion.** `web/src/pages/HomePage.test.tsx:23` asserts
  only the unconditional `rounded-pill`, never `bg-clay` — the variant the test
  name claims. Add `expect(cta).toHaveClass('bg-clay')`.
- **L16 — open avatar read.** `firebase/storage.rules:51` `allow read: if true`.
  Likely intentional (public avatars); add a confirming comment, or scope it.

Source: audit 2026-06-02.

## Recommended Action

Cosmetic/quality sweep — address alongside the next frontend touch in each file.
L14 is the most worth doing (a test that under-verifies its own name).

## Acceptance Criteria

- [ ] L2/L3 resolved; `tsc --noEmit` clean.
- [ ] L7/L8 verified in dark mode on device/emulator; `flutter analyze` clean.
- [ ] `HomePage.test.tsx` asserts `bg-clay`; vitest green.
- [ ] L16 has an explicit deliberate-public comment or a tighter rule.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from `docs/audits/2026-06-02-full.md` (L2, L3, L7, L8, L14, L16).

## Notes

p3 — all cosmetic/quality. No functional or security impact.
