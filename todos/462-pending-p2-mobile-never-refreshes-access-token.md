---
status: pending
priority: p2
issue_id: "462"
tags: [mobile, flutter, auth, bug]
dependencies: []
source_review: "todos/444-pending-p3-mobile-diagnose-missing.md"
---

# Mobile signs the user out when the access JWT expires, and never refreshes it

## Problem

Found by the PR #857 review (todo 444) and confirmed by reading the code.

- `ApiService` (`plant_community_mobile/lib/services/api_service.dart`) sends
  every 401 to `_handleSessionExpired`, except requests marked
  `skipSessionExpiryKey`.
- `AuthService._handleSessionExpired`
  (`plant_community_mobile/lib/services/auth_service.dart`) clears both
  tokens, signs out of Firebase and shows "Your session expired. Please sign
  in again."
- The app stores the Django refresh token (`django_refresh_token`) but never
  uses it. Nothing calls a token-refresh endpoint.
- The access token lasts `JWT_ACCESS_TOKEN_LIFETIME` minutes, 15 by default
  (`backend/plant_community_backend/settings.py`, `SIMPLE_JWT`). The
  production value is unverified.

So a user who keeps the app open past the access lifetime is signed out on
their next authenticated request, and loses whatever they were doing: a
forum draft, a diagnosis photo and symptoms. Relaunching hides it, because
launch re-exchanges the Firebase token for a fresh JWT.

Hypothesis, not verified on a device: this is also why testers see
unexplained "session expired" sign-outs.

## Recommended Action

On a 401, first try to recover silently, then retry the original request
once:

- use the stored refresh token (SimpleJWT refresh endpoint), or
- re-exchange the current Firebase ID token, which the app already does at
  launch.

Sign out only when that recovery fails. Make sure concurrent 401s share a
single refresh, and that a multipart body can be re-sent.

## Acceptance Criteria

- [ ] An expired access token is refreshed and the request retried, with no
      sign-out and no lost input.
- [ ] Concurrent 401s trigger one refresh.
- [ ] A failed refresh still signs out with the current message.
- [ ] Tests cover all three; the production access lifetime is recorded.
