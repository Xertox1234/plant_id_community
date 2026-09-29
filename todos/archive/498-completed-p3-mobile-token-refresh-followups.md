---
status: completed
priority: p3
issue_id: "498"
tags: [mobile, flutter, auth]
dependencies: []
owner_decision: "Finding 1: users expect to stay signed in (it is a recipe app; signing in again is tiresome): sign out only when the server definitely refuses the session, never on a transient failure. Raised to p3 (2026-09-29). Finding 5: add manage.py flushexpiredtokens to the nightly forum-prune-cron in .railway/railway.ts; do not change the exchange (2026-09-29)"
triage: ready
triaged: 2026-09-29
---

# Mobile token refresh: follow-ups from PR #891's review

## Problem

PR #891 (todo 462) made the mobile app refresh its access token on a 401 by re-exchanging the Firebase ID
token, instead of signing the user out. Round 1 found four blocking highs, which the repair fixed: the
exchange carried the expired bearer, a stale `.g.dart`, and a request from user A being re-sent as user B.
Round 2 was clean. The findings below were rated non-blocking in either round and are still open.

## Findings

Line numbers are as of PR #891's head (681858bf).

1. **Any failed refresh signs the user out, even a transient one** (`auth_service.dart:617`–`622`).
   `_refreshAccessToken` returns `null` for every exception: offline, timeout, 5xx, a `getIdToken` network
   error, and a 429 from the exchange's 10/min-per-IP limit, which carrier NAT shares. `_runRefresh` reads
   `null` as "cannot recover" and signs out of Firebase, so the draft or photo this todo protects is
   still lost on a network blip. The launch exchange deliberately does not sign out on failure. Reported
   by four reviewers across both rounds.
   Suggested: sign out only on a definite refusal (401, 403 or 409 from the exchange, or a
   `FirebaseAuthException` such as user-disabled). On a transient failure, return the original 401 to the
   caller without signing out, so the next 401 tries the refresh again. **Owner decision (2026-09-29):
   do this.** "This is just a recipe app. Users expect to stay logged in. Logging in all the time gets
   tiresome." It replaces todo 462's criterion "a failed refresh signs out" with "only a refused refresh
   signs out".
2. **A refresh that ends while `signOut()` runs reports "session expired"** (`api_service.dart:344`–`356`).
   `signOut()` bumps `_authGeneration` first but calls `setAuthToken(null)` last, after up to 3 s of
   `clearOnLogout` and the Firebase sign-out. A refresh that ends in that window returns `null` with
   `_authSession` unchanged, so `_runRefresh` shows "Your session expired" after a deliberate sign-out.
   That contradicts `lib/services/README.md`. Neither "overtaken by sign-out" test covers the window: both
   only sign out before the gate completes. Suggested: a tri-state refresher (token / rejected /
   superseded), or a `_signingOut` flag that makes `_handleSessionExpired` a no-op. Add a test that holds
   `clearOnLogout` while the refresh finishes.
3. **The logout FCM clear never refreshes** (`push_registration_service.dart:166`, pre-existing). It
   sends `skipSessionExpiryKey`, which now also skips the refresh. After more than 15 min idle (the prod
   access lifetime), the PATCH 401s and the FCM token is never cleared, so the device keeps getting the
   signed-out user's pushes. Suggested: a flag that suppresses only the sign-out and still allows
   refresh-and-retry, set on that PATCH.
4. **`_refreshInFlight` is not scoped to the session** (`api_service.dart:323`). If A's refresh is still
   running when A signs out and B signs in, B's first 401 joins A's refresh. The session check then
   discards it, so B's request fails with no refresh attempted for B. A related symptom (round 1): waiters
   on a refresh overtaken this way each get the 401 "session expired" ApiException while the user stays
   signed in. Suggested: store the session with the in-flight future, and clear it on
   `setAuthToken(null)`.
5. **Each silent refresh mints a new 7-day refresh token** (`auth_service.dart:581`). The exchange calls
   `RefreshToken.for_user`, and with `token_blacklist` installed that is an `OutstandingToken` row. The
   mobile client never uses or blacklists them, and no `flushexpiredtokens` job runs. That is about 96 rows
   per active user per day, up from one per launch. Suggested: run `manage.py flushexpiredtokens` from the
   nightly `forum-prune-cron`, or skip minting a refresh token when the exchange is a refresh.
6. **A refresh that turns a failed launch into a login skips push registration**
   (`auth_service.dart:615`). If the launch exchange failed (Firebase user, no JWT), a later refresh sets
   the JWT, but `syncAfterLogin` never runs. Suggested: call it when `state.jwtToken` was null before the
   refresh.
7. **Concurrent session-expiry sign-outs are not deduplicated** (`api_service.dart:284`, pre-existing).
   The second-401 and no-refresher paths each call `_handleSessionExpired`, and `AuthService` awaits
   `_clearJWT` before `setAuthToken(null)`, so concurrent 401s each run a full sign-out. Suggested: bump the
   session synchronously before the first await, or share one in-flight expiry future.
8. **The concurrency tests poll with no bound** (`test/api_service_test.dart:353`, `:415`).
   `while (server.requests.length < N) await Future.delayed(...)` hangs until the suite timeout if a
   regression stops a request from arriving. Add an iteration cap with a clear failure.
9. **Defense in depth on the backend** (repair note). `firebase_token_exchange` still runs DRF's default
   authentication classes, so any client that sends a stale bearer to it gets a 401 before the view runs.
   The mobile fix omits the header. Suggested: `@authentication_classes([])` on the view, since it
   verifies only the body token.
10. **Nothing enforces the session guard's precondition** (`api_service.dart:66`, `:379`; kimi WARNING on
    681858bf). The guard assumes every sign-in passes through `setAuthToken(null)` before it sets a new
    token, because only that bumps `_authSession`. It holds today: the one non-null sign-in call
    (`auth_service.dart:469`) clears first at `:409`, and the other two (`auth_service.dart:614`,
    `api_service.dart:350`) are the same-session refresh. But a future sign-in path that sets the token
    directly would let user A's request be re-sent as user B again. Suggested: have `setAuthToken` bump
    the session itself whenever the token is not a refresh of the current one (for example, a separate
    `replaceAuthToken` for the refresh), or add a test that drives each sign-in path and asserts the
    session changed.

## Acceptance Criteria

- [x] Findings 1–10 are fixed, or each has a line in this todo saying why not.
- [x] A transient refresh failure (offline, timeout, 5xx, 429) leaves the user signed in and their
      request fails with a retryable error; only a refused refresh signs out (finding 1, owner decision).
- [x] Findings 1, 2, 3, 4 and 10 each have a test that fails when the fix is removed.

## Work Log

### 2026-09-29 - Filed from PR #891 review rounds 1 and 2

Round 2 never repairs, and all nine were rated non-blocking. Round 1's other non-blocking findings (a
401 after a clean sign-out still refreshing, a second 401 after a sign-out during the retry, and the
missing real-HTTP exchange test) were fixed by the round-1 repair's session guard and loopback tests.

### 2026-09-29 - Owner decision on finding 1; raised to p3

The owner chose to keep users signed in through transient failures ("This is just a recipe app. Users
expect to stay logged in."), and raised this todo to p3. Finding 10 was added from the kimi gate's
WARNING on the round-1 repair commit, which was checked by hand and holds today.

### 2026-09-29 - Implemented by the todo sweep (run 2026-09-29-1857)

- Findings 1, 4, 7, 10 (`api_service.dart`): a refresh now ends refreshed, refused (the refresher returns `null`: exchange 401/403/409, a dead-account Firebase code, no Firebase user) or transient (the refresher throws). Only refused signs out; a transient failure fails the request with its own error (503, 429, or a status-less "Could not renew your session") and the next 401 refreshes again. `getIdToken()` returning `null` counts as transient: it is not a server refusal, and the owner chose staying signed in. The in-flight refresh is per session, every 401 of one session shares one sign-out, and `setAuthToken` starts a new session on every call. The refresh uses `replaceAuthToken`, which keeps it, and so does the launch exchange's JWT, which completes the session its own `setAuthToken(null)` opened; otherwise a request sent while the exchange ran would fail as "session expired" on a signed-in user.
- Finding 2: `signOut()` calls the new `ApiService.endSession()` right after its generation bump, so a refresh that lands during `clearOnLogout` is overtaken, not refused. This is a session bump, not a `_signingOut` flag. Finding 3: `skipSessionExpiryKey` now suppresses only the sign-out and still refreshes and re-sends, so the logout FCM clear survives an expired token. Finding 6: a refresh that turns a failed launch into a login runs `syncAfterLogin`.
- Finding 5: `manage.py flushexpiredtokens` added to the nightly `forum-prune-cron` in `.railway/railway.ts`, before `expire_unverified_accounts`; the exchange is unchanged (owner decision). Finding 9: `@authentication_classes([])` on `firebase_token_exchange`. Finding 8: the loopback tests poll through a bounded `waitUntil`.
- Mutation-checked by hand, each restored from a copy: reverting each of findings 1 (both halves), 2, 3, 4, 6, 7, 10 (both halves) and 9 turns its new test red. Flutter: 918 pass, analyze clean, `auth_service.g.dart` regenerated (its source hash changed). Backend: `apps/users` + `apps/core/tests` 1832 pass.

### 2026-09-29 - Verified by the todo sweep (run 2026-09-29-1857)

- AC 1: `/bin/sh -c 'cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/plant_community_mobile && flutter test test/api_service_test.dart test/services/auth_service_test.dart test/services/push_registration_service_test.dart && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/backend && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest apps/users/tests/test_firebase_auth.py --create-db -q -p no:cacheprovider && grep -n -e flushexpiredtokens -e "authentication_classes(\[\])" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/.railway/railway.ts /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/backend/apps/users/firebase_auth_views.py'` — evidence `.sweep-evidence/g1/498-ac0.txt`, last lines:

  ```text
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 37 passed, 3 warnings in 27.77s ========================
  /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/.railway/railway.ts:56:    // flushexpiredtokens (simplejwt's token_blacklist, todo 498) deletes
  /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/.railway/railway.ts:64:    start: "/bin/sh -c \"python manage.py prune_forum_tombstones && python manage.py prune_link_preview_images && python manage.py flushexpiredtokens && python manage.py expire_unverified_accounts --dry-run\"",
  /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/backend/apps/users/firebase_auth_views.py:226:@authentication_classes([])
  ```

- AC 2: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/plant_community_mobile && flutter test test/api_service_test.dart test/services/auth_service_test.dart --name "todo 498"` — evidence `.sweep-evidence/g1/498-ac1.txt`, last lines:

  ```text

  [API] *** Response ***
  00:00 +20: /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/plant_community_mobile/test/services/auth_service_test.dart: refused vs transient refresh failures (todo 498) over real HTTP, a request sent while the launch exchange runs is re-sent with the JWT it installs, not failed as expired
  00:00 +21: /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/plant_community_mobile/test/services/auth_service_test.dart: refused vs transient refresh failures (todo 498) a refresh that completes a login the launch exchange failed registers push
  00:00 +22: All tests passed!
  ```

- AC 3: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_a7249680-b5c-1/.sweep-evidence/g1/mutations_498.py` — evidence `.sweep-evidence/g1/498-ac2.txt`, last lines:

  ```text
      00:00 +100 ~3 -1: Some tests failed.
  === F9-exchange-runs-authenticators: rc=1
      FAILED apps/users/tests/test_firebase_auth.py::FirebaseTokenExchangeTestCase::test_stale_bearer_does_not_block_the_exchange
      ================== 1 failed, 36 passed, 3 warnings in 27.44s ===================
  restored all
  ```

### 2026-09-29 - Completed by the todo sweep (run 2026-09-29-1857)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-09-29 - Owner-approved repair after review round 2 (PR #898)

- Round 2 blocked on a high: the exchange's catch-all answered 401 for faults on our side (Google cert fetch,
  Firebase Admin not set up), and the client now signs out on an exchange 401, so an outage like 2026-09-13
  would sign every refreshing user out. The owner chose to fix it here and run one more full-depth round.
- `firebase_auth_views.py`: the catch-all now answers 503 `code: verifier_unavailable`, which the client
  already waits out; 401 stays for Expired/InvalidIdTokenError only. A non-string `firebase_token` is a 400,
  so a malformed body never reads as an outage.
- Tests: `test_firebase_verification_exception` and `test_bad_credentials_path_yields_503_not_500` (was
  `…_401_not_500`) now expect 503; new CertificateFetchError, uninitialized-app and non-string cases.
  Mutation-checked: restoring the 401 turns 4 tests red, dropping the string guard turns 1 red.
  `pytest apps/users apps/core/tests`: 1835 passed.
