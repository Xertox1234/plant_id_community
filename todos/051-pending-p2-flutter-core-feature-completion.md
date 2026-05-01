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

- [ ] 401 responses attempt token refresh once and retry the original request, or sign the user out with a clear message.
- [ ] 429 and retryable 5xx responses use bounded exponential backoff where appropriate.
- [ ] Theme preference persists across app launches.
- [ ] Settings route is no longer a placeholder.
- [ ] Mobile integration-test docs reflect current reality.
- [ ] Manual iOS/Android smoke test checklist is completed.

## Work Log

### 2026-05-01 - Codebase Assessment

- Classified P2 because these issues affect reliability and UX, but are not as fundamental as making the app build from a clean checkout.
