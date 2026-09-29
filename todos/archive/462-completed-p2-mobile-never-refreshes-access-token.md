---
status: completed
priority: p2
issue_id: "462"
tags: [mobile, flutter, auth, bug]
dependencies: []
source_review: "todos/archive/444-completed-p3-mobile-diagnose-missing.md"
triage: ready
triaged: 2026-09-29
blocked_on: "Owner picks the recovery path (Firebase re-exchange vs a bearer-friendly refresh endpoint) and supplies the prod JWT_ACCESS_TOKEN_LIFETIME."
owner_decision: "Recover a 401 by re-exchanging the Firebase ID token (mobile only, reuses the launch path); prod JWT_ACCESS_TOKEN_LIFETIME not supplied, so read it from settings (2026-09-28)"
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

- [x] An expired access token is refreshed and the request retried, with no
      sign-out and no lost input.
- [x] Concurrent 401s trigger one refresh.
- [x] A failed refresh still signs out with the current message.
- [x] Tests cover all three; the production access lifetime is recorded.

## Work Log

### 2026-09-29 - Implemented by the todo sweep (run 2026-09-29-1202)

- `ApiService` now recovers a 401 before signing out: it calls a refresher
  `AuthService` registers, re-sends the request once with the new token, and
  signs out only when the refresh fails or the re-sent request 401s again.
  The refresh re-exchanges the Firebase ID token (owner decision); the stored
  Django refresh token stays unused.
- Concurrent 401s share one in-flight refresh; a 401 for a request sent under
  a token that has since been replaced retries without refreshing. A multipart
  `FormData` is cloned before the re-send, since Dio will not send one twice.
- The refresh's own exchange carries `skipAuthRefreshKey` and
  `skipSessionExpiryKey`, so it cannot recurse or sign out on its own; the
  launch exchange carries `skipAuthRefreshKey`, so its 401 still signs out
  directly. A refresh overtaken by sign-out or a user switch reports no expiry.
- Production access lifetime recorded in `plant_community_mobile/lib/services/README.md`:
  15 minutes, the `settings.py` default, because the production variable set in
  `.railway/railway.ts` has no `JWT_ACCESS_TOKEN_LIFETIME`.
- Tests: 9 loopback-HTTP cases in `test/api_service_test.dart` and 6 in
  `test/services/auth_service_test.dart`; the clone and the single-flight were
  each mutation-checked (removing either fails its test).

### 2026-09-29 - Verified by the todo sweep (run 2026-09-29-1202)

- AC 1: `cd plant_community_mobile && flutter test test/api_service_test.dart test/services/auth_service_test.dart --reporter expanded --name "refreshed and the JSON request retried|multipart upload is re-sent in full|registers a refresher that re-exchanges"` — evidence `.sweep-evidence/g1/462-ac0.txt`, last lines:

  ```text
  [API]
  00:00 +3: /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_460cd0cc-609-1/plant_community_mobile/test/api_service_test.dart: (tearDownAll)
  00:00 +3: All tests passed!

  [exit code 0]
  ```

- AC 2: `cd plant_community_mobile && flutter test test/api_service_test.dart test/services/auth_service_test.dart --reporter expanded --name "concurrent 401s share one refresh|arriving after the refresh finished|concurrent 401s with a failed refresh"` — evidence `.sweep-evidence/g1/462-ac1.txt`, last lines:

  ```text

  00:00 +3: /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_460cd0cc-609-1/plant_community_mobile/test/api_service_test.dart: (tearDownAll)
  00:00 +3: All tests passed!

  [exit code 0]
  ```

- AC 3: `cd plant_community_mobile && flutter test test/api_service_test.dart test/services/auth_service_test.dart --reporter expanded --name "failed refresh signs out once|failed re-exchange returns null|second 401 on the retried request|skipAuthRefreshKey signs out|launch exchange 401 goes straight"` — evidence `.sweep-evidence/g1/462-ac2.txt`, last lines:

  ```text
  [API ERROR] 401 Unauthorized - session expired
  00:00 +5: /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_460cd0cc-609-1/plant_community_mobile/test/api_service_test.dart: (tearDownAll)
  00:00 +5: All tests passed!

  [exit code 0]
  ```

- AC 4: `cd plant_community_mobile && flutter test test/api_service_test.dart test/services/auth_service_test.dart --reporter expanded && grep -n "Production access lifetime" -A 6 lib/services/README.md && grep -n "JWT_ACCESS_TOKEN_LIFETIME" ../backend/plant_community_backend/settings.py && echo "JWT_ACCESS_TOKEN_LIFETIME occurrences in .railway/railway.ts: $(grep -c JWT_ACCESS_TOKEN_LIFETIME ../.railway/railway.ts)"` — evidence `.sweep-evidence/g1/462-ac3.txt`, last lines:

  ```text
  760:        minutes=config("JWT_ACCESS_TOKEN_LIFETIME", default=15, cast=int)
  767:            minutes=config("JWT_ACCESS_TOKEN_LIFETIME_DEBUG", default=120, cast=int)
  JWT_ACCESS_TOKEN_LIFETIME occurrences in .railway/railway.ts: 0

  [exit code 0]
  ```

### 2026-09-29 - Completed by the todo sweep (run 2026-09-29-1202)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-09-29 - Repaired by the todo sweep (run 2026-09-29-1202)

- The refresh's token exchange now goes out with no bearer (new request flag
  `ApiService.omitAuthHeaderKey`). It used to carry the expired token, which
  DRF's default `JWTAuthentication` rejects before the `AllowAny` view runs,
  so every real expiry still signed the user out. New loopback tests in both
  test files run a real exchange against a server that 401s any bearer.
- A 401 for a request sent before a sign-out or user switch is no longer
  retried under the new user's token. `ApiService` stamps each request with a
  session id that `setAuthToken(null)` bumps, and every sign-in clears the
  token first. Such a 401 also skips the refresh and the sign-out, because
  refreshing would still re-send the request as the new user.
- A refresh that finishes after the session changed installs nothing.
- Regenerated `auth_service.g.dart` (riverpod source hash) for CI's
  generated-code gate. Mutation-checked: removing the header omission or the
  session guard fails the new tests.
