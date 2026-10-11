---
status: completed
priority: p3
owner_decision: "F3: use a sign-out generation-counter / request-side guard, not a _signingOut flag (keeps the no-flag design). F1: keep 409 out of the sign-out path, keep state and surface unverifiedAccountConflict (2026-10-10)"
issue_id: "500"
tags: [mobile, flutter, auth, backend]
dependencies: []
triage: ready
triaged: 2026-10-10
---

# Mobile token refresh: follow-ups from PR #898's review

## Problem

PR #898 (todo 498) keeps mobile users signed in through transient refresh failures: only a refused
exchange (401/403/409, a disabled Firebase account, no user) signs out. Round 2 blocked it on a high:
the exchange's catch-all answered 401 for faults on our side. The owner approved a repair and a third
round (2026-09-29). The catch-all now answers 503 `verifier_unavailable`, and round 3 found nothing
blocking.

The findings below were rated non-blocking and still hold after the repair. Duplicates across rounds are
merged. The 401-for-our-faults findings from rounds 1 and 2 are left out, because the repair fixed them.
Paths are under `plant_community_mobile/lib/services/` unless noted. Line numbers are as of 7d2544e6.

## Findings

1. **An unverified account's 409 can be replaced by "session expired"** (medium, round 1).
   `_exchangeRefusalStatuses` includes 409. The `unverified_account` catch block deliberately keeps the
   user signed in to Firebase. A stray authenticated request while `jwtToken == null` refreshes, hits
   the 409 again, and runs `_expireSession`. That forces a full Firebase sign-out and overwrites
   `accountConflictMessage` with the generic text. Suggested: leave 409 `unverified_account` out of the
   refusal set, or keep the state in `_handleSessionExpired` when `unverifiedAccountConflict` is set.
2. **An overtaken refresh reads as a refusal and can sign out the wrong user** (medium, rounds 1–3,
   reported 5 times). `_refreshAccessToken` (`auth_service.dart:619`) returns null both for a refusal
   and when it was overtaken (`user == null`, or `_isCurrentExchange` fails on a uid mismatch).
   `currentUser.uid` changes before the `authStateChanges` listener bumps the session, so ApiService
   reads that null as `_Refused` and signs out whoever is current: the new user B, or it shows "session
   expired" during a deliberate `signOut()` (`auth_service.dart:376/383`). Suggested: return null only
   on the explicit refusal branches, and throw a superseded sentinel for the others, mapped to
   `_Superseded`. Add a test that changes `currentUser.uid` mid-refresh.
3. **A refresh during sign-out can re-register push for the user signing out** (medium, rounds 2–3,
   reported 4 times). `signOut()`'s FCM-clear PATCH can 401 and refresh, and that refresh passes the
   generation check. If `state.jwtToken` is null (after a failed launch exchange, with an old
   registration still live), `completesLogin` fires `syncAfterLogin()` mid-sign-out, and its
   `registerToken` PATCH can land after the clear (`auth_service.dart:678`). Suggested: set a
   `_signingOut` flag in `signOut()` and skip the refresh's push sync while it is set. Add a test for a
   sign-out whose clear 401s with `jwtToken` null. A related case: a 401 while the launch exchange is
   still running (`completesLogin` is also true then) syncs push twice (`auth_service.dart:731/878`),
   and no test pins that an ordinary refresh does not re-sync.
4. **The exchange's 503 catch-all is broad** (medium, round 3,
   `backend/apps/users/firebase_auth_views.py:350`). It covers the whole verification try block, so a
   bug after `verify_id_token` (a `KeyError` on `decoded_token["uid"]`) reads as an outage, and the
   client retries instead of Sentry seeing a 500. If `check_revoked` is ever enabled, `UserDisabledError`
   would also read as an outage. Suggested: narrow the 503 to
   `(firebase_auth.CertificateFetchError, ValueError)` around `verify_id_token`, and let anything else
   reach the outer 500. Also add a test that sends a garbage token through the real verifier
   (project-id-only init) and expects 401. Optionally add `Retry-After` to the 503.
5. **A refresh failure reaches the caller as the endpoint's own status** (low, rounds 1–3). `_Unavailable`
   re-raises the exchange's 429/503/400, so `diagnoseErrorMessage` shows "Too many diagnoses in a row"
   when only the exchange's 10/min per-IP limit fired (`api_service.dart:312/444`). An offline exchange
   maps to "An unexpected error occurred", not the promised "Could not renew your session"
   (`api_service.dart:762`), and the test throws a raw `SocketException` instead of going through Dio.
   Suggested: wrap it in its own `ApiException` with code `session_refresh_unavailable`, and add
   `DioExceptionType.connectionError` to `handleDioException`.
6. **The logout FCM clear's 3s timeout may not cover a refresh** (low, rounds 1–3,
   `push_registration_service.dart:36/162/171`). PATCH, `getIdToken`, the exchange and the re-sent
   PATCH must all fit in 3s. Past that, the refresh is overtaken and the clear is never re-sent.
   Suggested: a longer bound when a refresh is needed, or document the limit. Add a test where the
   refresh outlasts the timeout.
7. **`_runRefresh` treats any error as transient** (low, round 2, `api_service.dart:372`). A `TypeError`
   or `StateError` from a refresher bug becomes a silent "check your connection" on every 401.
   Suggested: `on Exception catch`, or log `Error` distinctly. Related: no transient backoff
   (`api_service.dart:347`); each 401 during an outage runs another exchange, bounded only by the
   per-IP limit.
8. **Status-code-only refusal** (low, round 3, `auth_service.dart:580/647`). A 401 or 403 HTML page from
   a proxy or WAF would sign the user out, and a 400/404/405 from the exchange keeps them signed in with
   every request failing. Suggested: refuse only when the body has the view's JSON shape, and state in a
   comment which other statuses are deliberately transient.
9. **`_expiringSession` can stick** (low, round 1, `api_service.dart:420`). If no handler is registered
   when a session expires, `_expiringSession` is set anyway, and later 401s of that session no-op even
   after a handler is registered. Suggested: record it only when a handler exists, or reset it in
   `setSessionExpiredHandler`.
10. **Test gaps** (medium/low, rounds 1–3):
    - No test drives the real `signOut()` → clear PATCH 401 → `_refreshAccessToken` → re-sent PATCH path
      (`test/services/auth_service_test.dart:620`).
    - No AuthService-level test of the early `setAuthToken(null)` on a direct user switch A→B
      (`auth_service.dart:415`).
    - No test of the `firebaseToken == null` transient branch (`auth_service.dart:622`).
    - The push loopback handler decodes the body unguarded (`push_registration_service_test.dart:235`),
      so a bad body hangs the test to the suite timeout.
    - Three hand-rolled poll loops duplicate the new `waitUntil` helper (`auth_service_test.dart:643`).
    - `_LoopbackBackend` still 401s an exchange that carries a bearer, which the view no longer does.
    - The non-string-token test could also assert the error message.
11. **Stale docs and comments** (low, rounds 1–3):
    - The `omitAuthHeaderKey` doc (`api_service.dart:43`) and the exchange-call comment
      (`auth_service.dart:636`) still say the backend would 401 a stale bearer.
    - The README usage example still shows `setAuthToken(jwtToken)` (`README.md:121`). The `case 401:`
      comment (`README.md:213`) misses the ended-session pass-through, and the `endSession()` paragraph
      (`README.md:181`) is not wrapped.
    - `backend/apps/users/firebase_auth_views.py:142` and `:182` still say "handled 401".
      `backend/docs/FIREBASE_AUTHENTICATION.md` lists only 400/401/500.
    - The view has no `@extend_schema`, so the 503 is not in the OpenAPI schema.
    - The unreachable `_Superseded` arm (`api_service.dart:324`) needs a comment.
    - `AuthException` messages for a malformed exchange response imply a connectivity problem
      (`auth_service.dart:623/661`).
    - `authStateChanges().listen` has no `onError` (`auth_service.dart:141`, pre-existing).
    - The `_carried is ApiException` short-circuit (`api_service.dart:676`) matches any `DioException`.

## Acceptance Criteria

- [x] Findings 1–11 are fixed, or each has a line here saying why not.
- [x] Findings 1, 2, 3 and 4 each have a test that fails when the fix is removed.

## Work Log

### 2026-09-29 - Filed from PR #898's review rounds 1–3

Round 2 never repairs, and round 3 (the owner's call) did not either. Nothing was dismissed by the
refuters in any round.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- F1 (owner decision): 409 left `_exchangeRefusalStatuses`. A refresh's 409 keeps the user signed in to Firebase, puts the conflict on screen with `unverifiedAccountConflict` kept, and fails the request as transient. F2: the refresher throws `RefreshSupersededException` (mapped to `_Superseded`) when there is no Firebase user, a different one, or a newer generation; `null` now means only a refusal. F3 (owner decision, a generation not a flag): `signOut()` records `_signOutGeneration`, and a refresh in it only installs the token for the clear's re-send; `_completeLogin` runs push sync and the profile re-fetch once per generation, so a 401 during the launch exchange no longer syncs twice.
- F4: the 503 covers only `verify_id_token` raising `CertificateFetchError` or `ValueError`; a bug after it is a 500, and `UserDisabledError` is a 401. `@extend_schema` documents 200/400/401/403/409/503. No `Retry-After`: a 503 says nothing about when the verifier is back, and the client retries on its next 401 anyway. F5: a transient refresh failure reaches the caller as its own `ApiException` (no status, code `session_refresh_unavailable`), and `connectionError` reads as offline. F6: documented on `_logoutClearTimeout` and pinned by a test that the clear is given up at 3 s.
- F7: an `Error` from the refresher goes to `FlutterError.reportError`; the user still stays signed in. No backoff, on purpose: the owner decision on 498 is that the next 401 tries again, and the exchange's per-IP limit bounds it. F8: a 401/403 refuses only when the body was JSON (`ApiException.unstructured`), and a comment lists the statuses kept transient. F9: `_expiringSession` is recorded only when a handler exists.
- F10: tests for the real `signOut()` clear 401, refresh and re-send path, the early `setAuthToken(null)` on A to B, a null Firebase token, the guarded push loopback body, the shared `test/support/wait_until.dart`, a `_LoopbackBackend` exchange that ignores a bearer, and the non-string message. F11: the stale comments, README passages, "handled 401" notes and `FIREBASE_AUTHENTICATION.md` are updated; `_Superseded` is commented; the refresh's malformed-response message no longer implies connectivity; `authStateChanges` has an `onError`; the carried short-circuit matches only `session_refresh_unavailable`.
- Changed tests (the behaviour changed on purpose): the 409 refusal case, two refresher-returns-null cases (now `RefreshSupersededException`), two 503-passthrough expectations (now `session_refresh_unavailable`), and `test_firebase_verification_exception` (now 500). Mutation-checked: re-adding 409, returning `null` when superseded, dropping the sign-out generation check, dropping the once-per-generation guard, and widening the 503 back to `Exception` each fail a test.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `bash -c 'cd plant_community_mobile && flutter test --no-pub test/services/auth_service_test.dart test/api_service_test.dart test/services/push_registration_service_test.dart && cd backend && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest apps/users/tests/test_firebase_auth.py --create-db -p no:cacheprovider -q && grep -n -A12 "Implemented by the todo sweep (run 2026-10-11-0053)" todos/archive/500-completed-p3-mobile-token-refresh-898-followups.md'` — evidence `.sweep-evidence/g5/500-ac0.txt` (not committed), last lines:

  ```text
  126-- F7: an `Error` from the refresher goes to `FlutterError.reportError`; the user still stays signed in. No backoff, on purpose: the owner decision on 498 is that the next 401 tries again, and the exchange's per-IP limit bounds it. F8: a 401/403 refuses only when the body was JSON (`ApiException.unstructured`), and a comment lists the statuses kept transient. F9: `_expiringSession` is recorded only when a handler exists.
  127-- F10: tests for the real `signOut()` clear 401, refresh and re-send path, the early `setAuthToken(null)` on A to B, a null Firebase token, the guarded push loopback body, the shared `test/support/wait_until.dart`, a `_LoopbackBackend` exchange that ignores a bearer, and the non-string message. F11: the stale comments, README passages, "handled 401" notes and `FIREBASE_AUTHENTICATION.md` are updated; `_Superseded` is commented; the refresh's malformed-response message no longer implies connectivity; `authStateChanges` has an `onError`; the carried short-circuit matches only `session_refresh_unavailable`.
  128-- Changed tests (the behaviour changed on purpose): the 409 refusal case, two refresher-returns-null cases (now `RefreshSupersededException`), two 503-passthrough expectations (now `session_refresh_unavailable`), and `test_firebase_verification_exception` (now 500). Mutation-checked: re-adding 409, returning `null` when superseded, dropping the sign-out generation check, dropping the once-per-generation guard, and widening the 503 back to `Exception` each fail a test.

  [exit 0]
  ```

- AC 2: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/services/auth_service_test.dart --name "todo 500 F[123]" && cd backend && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest "apps/users/tests/test_firebase_auth.py::FirebaseTokenExchangeTestCase::test_firebase_verification_exception" "apps/users/tests/test_firebase_auth.py::FirebaseTokenExchangeTestCase::test_bug_after_verification_is_500_not_503" "apps/users/tests/test_firebase_auth.py::FirebaseTokenExchangeTestCase::test_disabled_firebase_account_is_a_refusal" "apps/users/tests/test_firebase_auth.py::FirebaseProjectIdOnlyInitTestCase::test_garbage_token_through_the_real_verifier_is_401" --create-db -p no:cacheprovider -v'` — evidence `.sweep-evidence/g5/500-ac1.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 4 passed, 3 warnings in 17.61s ========================

  [exit 0]
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
