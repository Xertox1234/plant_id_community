---
status: completed
priority: p2
issue_id: "082"
tags: [web, react, typescript, flutter, audit-2026-05-17]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "H20,H21,H22,H23,H24,H25,H26,H27"
---

# Web & Flutter High-severity audit findings

## Problem

Eight High-severity frontend/mobile findings from the 2026-05-17 full audit,
deferred at triage. Full detail per finding is in `docs/audits/2026-05-17-full.md`.

## Findings

- **H20** — `StreamFieldEditor.tsx` — implicit-`any` params throughout, no props
  interfaces. Largest type-safety gap in `web/src/`.
- **H21** — 14 `.test.jsx`/`.js` files violate the "no JavaScript in `web/src/`"
  rule — should be `.test.tsx`/`.test.ts`.
- **H22** — `DiagnosisDetailPage.tsx` double-casts StreamField values
  `as unknown as string` (lines 90,96,167) — can render `[object Object]` on a
  backend shape change.
- **H23** — Raw email addresses logged in 5 `debugPrint` sites (GDPR/PII).
  `plant_community_mobile/lib/services/auth_service.dart:95,137,147,176,189`.
- **H24** — `ThemeModeNotifier` manual `_isDisposed` flag + unguarded async gap.
- **H25** — `showLoadingDialog` uses `BuildContext` across an async gap, no
  `mounted` guard. `loading_indicator.dart:160`.
- **H26** — `SplashScreen` navigates inside a `setState`/`Timer` callback.
- **H27** — `appRouter` rebuilds the whole `GoRouter` on every auth change — should
  use `refreshListenable`. `app_router.dart:35`.

## Recommended Action

Triage each against `docs/audits/2026-05-17-full.md` and the pattern docs
(`web/docs/patterns/react-typescript.md`, `plant_community_mobile/docs/patterns/`).
H23 (PII in logs) is the highest-priority — apply the `redact_email()` pattern.

## Acceptance Criteria

- [x] Each finding fixed or explicitly closed as false-positive with evidence.
- [x] `npm run type-check && npm run lint && npm run test` (web) and
      `flutter analyze && flutter test` (mobile) pass.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4).

### 2026-05-21 - Started by completing-todos skill (run 2026-05-21-0238)

- Picked up by automated workflow.

### 2026-05-21 - Flutter findings (H23-H27)

- **H23 — fixed.** Added `lib/core/utils/log_redaction.dart` (`redactEmail`,
  mirroring the backend `redact_email`) and applied it to all 5 email-logging
  `debugPrint` sites in `auth_service.dart` (95/137/147/176/189). Verified no
  unredacted `.email` logging remains anywhere in `lib/`.
- **H24 — fixed.** `ThemeModeNotifier` manual `_isDisposed` flag replaced with the
  Riverpod 3.x idiom `ref.mounted` (removed the flag + its `ref.onDispose`).
- **H25 — false-positive.** `loading_indicator.dart:160` `showLoadingDialog` calls
  `showDialog` synchronously — there is no `await`/async gap, and `flutter analyze`
  reports no `use_build_context_synchronously`. No change.
- **H26 — fixed.** `SplashScreen` progress timer no longer performs navigation
  inside `setState`; `setState` now wraps only the `_progress` mutation, and the
  timer-cancel + deferred `context.go` run outside it.
- **H27 — fixed.** `appRouter` no longer `ref.watch`es the auth provider (which
  rebuilt the whole `GoRouter` on every auth change). It now builds once, uses a
  `ValueNotifier` driven by `ref.listen(...select(isAuthenticated))` as
  `refreshListenable`, and reads auth state via `ref.read` inside `redirect`.

Mobile verification: `flutter analyze` — **No issues found**; `flutter test` —
**All tests passed** (+72, ~3 skipped).

### 2026-05-21 - Web findings (H20-H22, via subagent + my verification)

Web fixes implemented by a dispatched subagent (non-overlapping `web/` tree),
then independently re-verified by me:

- **H20 — fixed.** `web/src/types/diagnosis.ts` `DiagnosisBlock` made a proper
  discriminated union (one variant per block type + `image`). `StreamFieldEditor.tsx`
  given `StreamFieldEditorProps`/`ListEditorProps`/`BlockControlsProps`/`BlockTypeOption`
  interfaces and all handler params typed; per-case `value as {...}` casts removed
  (narrowing via `block.type`). Typing-only, no runtime change.
- **H21 — fixed.** All 14 `.test.jsx`/`.test.js` renamed to `.test.tsx`/`.test.ts`
  via `git mv` (history preserved). Renaming surfaced 101 previously-unchecked type
  errors (`.jsx`/`.js` skip type-checking), all fixed with real types (missing
  fixture fields, literal widening, `vi.mocked(...)`) — no `any`/`@ts-ignore`.
- **H22 — fixed.** `DiagnosisDetailPage.tsx` no longer double-casts
  `as unknown as string`; it imports the shared `DiagnosisBlock` and switches on
  `block.type` so values narrow. One boundary cast kept where `unknown[]` enters.
- Judgment call (reviewed + accepted): `web/src/types/forum.ts`
  `Post.author.trust_level` changed from `User & {trust_level?: string}` to
  `Omit<User,'trust_level'> & {...}` — the plain `&` collapsed the free-string
  label to the auth enum. Minimal, correct, surfaced by H21's new type-checking.

Web verification (independently re-run by me from `web/`): `npm run type-check`
**0 errors**; `npm run lint` **0 errors**; `npm run test` **669 passed (24 files)** —
matches baseline, no regressions.

### 2026-05-21 - Code review + completion

- Code review (code-review-orchestrator → flutter-dart, flutter-firebase,
  react-typescript, security checklists): **0 findings**. Confirmed: `redactEmail`
  matches the backend byte-for-byte and covers every email log site (no PII leak);
  `ref.mounted` valid for H24; H27's `ValueNotifier` is disposed via `ref.onDispose`
  and cannot outlive its provider (kept alive by `main.dart`), no listener leak; H22
  has no `[object Object]` risk; the `Omit<User,'trust_level'>` widening is the only
  correct shape.
- Manifest `docs/audits/2026-05-17-full.md` High table updated: H20/H21/H22/H23/
  H24/H26/H27 → verified; H25 → false-positive.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-0238)

- Verification: both acceptance criteria passed (7 findings fixed, 1 false-positive;
  web type-check/lint/test green at 669, mobile analyze clean + 72 tests pass).
- Review: 0 blocking findings (0 findings total).
