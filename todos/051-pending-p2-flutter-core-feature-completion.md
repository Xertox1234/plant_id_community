---
status: pending
priority: p2
issue_id: "051"
tags: [mobile, flutter, auth, reliability, feature-completion, stabilization]
dependencies: ["050"]
---

# Complete Flutter Core App Reliability Features

## Problem

The Flutter app has a good foundation but still contains important TODOs and placeholders in core flows. It should be stabilized before adding new mobile features.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- `plant_community_mobile/lib/services/api_service.dart` still has TODOs for:
  - token refresh on 401
  - retry/backoff for 429 rate limiting
  - retry/backoff for 5xx server errors
- `plant_community_mobile/lib/config/theme_provider.dart` still has TODOs for persistence.
- `plant_community_mobile/lib/core/routing/app_router.dart` contains placeholder settings screen.
- Mobile dependency progress docs mention remaining integration-test and dependency work.

## Recommended Action

1. Implement API retry and token refresh behavior or explicitly defer with clear UX handling.
2. Persist theme preference using local storage.
3. Replace placeholder settings screen with minimal useful settings.
4. Finish or retire stale integration-test mock-service TODOs.
5. Manually test camera/gallery/auth flows on iOS and Android.

## Technical Details

Key files:

- `plant_community_mobile/lib/services/api_service.dart`
- `plant_community_mobile/lib/services/auth_service.dart`
- `plant_community_mobile/lib/config/theme_provider.dart`
- `plant_community_mobile/lib/core/routing/app_router.dart`
- `DEPENDENCY_UPDATE_PROGRESS.md`
- `plant_community_mobile/FLUTTER_DEPENDENCY_UPDATES_REMAINING.md`

## Acceptance Criteria

- [x] 401 responses attempt token refresh once and retry the original request, or sign the user out with a clear message.
- [x] 429 and retryable 5xx responses use bounded exponential backoff where appropriate.
- [x] Theme preference persists across app launches.
- [x] Settings route is no longer a placeholder.
- [x] Mobile integration-test docs reflect current reality.
- [ ] Manual iOS/Android smoke test checklist is completed.

## Work Log

### 2026-05-03 - Mobile Reliability Follow-up

- Wired `ApiService` 401 recovery to an `AuthService` session-expired handler because the current backend refresh endpoint is cookie-oriented while mobile uses bearer tokens.
- Added a session-expired handler that clears stored JWTs, removes the API bearer token, signs out Firebase, and leaves a clear sign-in-again message.
- Removed the stale mobile bearer-token refresh implementation until the backend exposes a mobile-compatible JSON refresh contract.
- Added bounded exponential backoff for retryable `429` and `5xx` API responses on safe HTTP methods, with opt-in support for unsafe request retries.
- Persisted theme mode selection through existing secure storage and restored it when the app starts.
- Replaced the placeholder settings route with a usable settings screen for theme selection and app/API information.
- Added a settings shortcut on the home screen so the route is reachable from the current mobile UI.
- Updated mobile dependency/integration-test docs to show that mock signatures are source-updated and now await validation in a Flutter-capable environment.
- Updated service-layer docs to reflect `--dart-define` configuration, current auth response field names, built-in retry behavior, and the remaining backend work needed for recoverable mobile bearer-token refresh.
- Added a mobile validation and manual iOS/Android smoke-test checklist to the mobile README.
- Verified edited files with editor diagnostics. Could not run `flutter analyze` or `flutter test` in the current cloud workspace because Flutter/Dart are not installed.

### 2026-05-01 - Codebase Assessment

- Classified P2 because these issues affect reliability and UX, but are not as fundamental as making the app build from a clean checkout.
