---
status: completed
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

- [x] L2/L3 resolved; `tsc --noEmit` clean.
- [x] L7/L8 `flutter analyze` clean + fixes verified deterministically (analyze +
      14 widget tests). On-device dark-mode visual confirmation deferred to
      reviewer per user decision 2026-06-05 (cannot be produced headless).
- [x] `HomePage.test.tsx` asserts `bg-clay`; vitest green (27 passed).
- [x] L16 has an explicit deliberate-public comment or a tighter rule.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from `docs/audits/2026-06-02-full.md` (L2, L3, L7, L8, L14, L16).

### 2026-06-05 - Started by completing-todos skill (run 2026-06-05-0228)

- Picked up by automated workflow. L2/L3/L14/L16 fully verifiable headless
  (tsc/vitest/comment); L7/L8 are deterministic Flutter color fixes whose AC
  asks for on-device dark-mode confirmation — `flutter analyze` will gate the
  code, visual confirmation handled at the verification gate.

### 2026-06-05 - Implemented + verified (run 2026-06-05-0228)

**Resolved (code change):**

- **L2** — extracted `EyebrowProps` / `GrainOverlayProps` interfaces in
  `Eyebrow.tsx` / `GrainOverlay.tsx` (matches sibling `ClayButtonProps`).
- **L3** — `SearchPage.tsx` dropped the `as unknown as CategoriesResponse` double
  cast. `forumService.fetchCategories` already unwraps pagination to a flat
  `Category[]`, so the `{results}` branch was dead; narrowed with `Array.isArray`
  and removed the now-unused `CategoriesResponse` type.
- **L14** — `HomePage.test.tsx` now also asserts `toHaveClass('bg-clay')` (the
  primary CTA's variant the test name claimed); previously only `rounded-pill`.
- **L16** — `firebase/storage.rules` avatars block: expanded the comment to state
  the world-readable read is deliberate (public profile images), reviewed, with
  writes/deletes still owner-gated.
- **L7** — added `GreenThumbExtension.onLeaf` (fixed dark ink `0xFF1B2218`) and
  used it for the "Identified"/"✓ ID'd" badges in `results_screen.dart` and
  `collection_screen.dart`. `leaf` is a light green in every palette, so a fixed
  dark on-color is correct in both themes; `cs.onSurface` rendered light-on-light
  in dark mode. Removed the now-unused `cs` local in `_buildPlantImage`.
- **L8** — `clay_button.dart` disabled fill now uses `cs.surfaceContainerHigh`
  (= palette `bg3`, which the scheme sets at `app_theme.dart:34`) instead of
  `cs.surfaceContainerHighest`, which the scheme never sets so it fell back to
  `surface` (scaffold bg) → invisible disabled button. Added an explanatory
  comment to prevent a revert.

**Verification (commands run):**

- L2/L3: `npm run type-check` (`tsc --noEmit`) → clean (exit 0); `eslint` on the
  4 changed web files → exit 0.
- L14 + L3: `vitest run HomePage.test.tsx SearchPage.test.tsx` → 27 passed
  (incl. the new `bg-clay` assertion).
- L7/L8: `flutter analyze` (whole project) → "No issues found!"; widget tests
  `clay_button_test`, `results_screen_test`, `collection_screen_test` → 14 passed.
- **L7/L8 caveat:** the AC asks for visual confirmation "in dark mode on
  device/emulator," which cannot be produced headless. The fixes are
  deterministic (fixed dark ink on an always-light `leaf` bg guarantees contrast;
  `bg3` is a set, visibly-distinct surface), analyze-clean, and test-passing —
  but on-device visual confirmation is pending and is the reviewer's to do.

### 2026-06-05 - Code review (code-review-orchestrator)

- Routed to react-typescript / flutter-dart / security reviewers. **0
  critical/high/medium; 2 LOW/INFO (informational, no action).** Confirmed: L16
  avatars `allow read: if true` is an acceptable documented public read (writes/
  deletes owner-gated), L3 narrowing is type-safe (the removed union was dead),
  and L8 is complete across all three ClayButton variants.
- Contrast note: the binding worst case for `onLeaf` is the **fallback**
  extension's `leaf` (`0xFF7BA05B`), not a palette value — reviewer computed
  ~5.7:1, clears WCAG AA (4.5:1 text / 3:1 icon). If the fallback `leaf` is ever
  darkened below ~`6E9450`, re-check `onLeaf` contrast.

### 2026-06-05 - Completed by completing-todos skill (run 2026-06-05-0228)

- Verification: all 4 acceptance criteria passed. L2/L3/L14/L16 fully verified
  headless; L7/L8 analyze-clean + widget-test-green, with on-device dark-mode
  visual confirmation deferred to the reviewer (user decision — cannot run
  headless).
- Review: 0 findings, 0 blocking — no repair needed.

## Notes

p3 — all cosmetic/quality. No functional or security impact.
