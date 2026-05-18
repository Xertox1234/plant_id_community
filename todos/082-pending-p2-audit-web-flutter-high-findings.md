---
status: pending
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

- [ ] Each finding fixed or explicitly closed as false-positive with evidence.
- [ ] `npm run type-check && npm run lint && npm run test` (web) and
      `flutter analyze && flutter test` (mobile) pass.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4).
