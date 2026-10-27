---
status: completed
priority: p2
issue_id: "660"
tags: [mobile, auth, firebase]
dependencies: []
triage: ready
triaged: 2026-10-26
owner_decision: "Owner: Option 1. Worker builds the mobile code; the main session investigates the verify-link API key restriction read-only and proposes the change, which the owner approves before it is applied (AC2 is owner/Console-side) (2026-10-26)"
---

# Mobile email sign-up can never complete: no verification mail, a broken verify link, and no retry

## Problem

A user who creates an account with email and password in the mobile app is never signed in. The backend
refuses an unverified Firebase email. The app never sends a verification mail, and the hosted verify page
can't apply a link anyway. Signing in again after verifying doesn't retry the exchange. Google sign-in is
the only mobile path that works. New users who choose email get bounced back to Profile, still signed out,
with no message.

## Findings

Found 2026-10-25 while creating a sim test account to check PR #1195 (Claude, prod API, iPhone 17 Pro sim).

- **Backend gate (intended, keep it):** `backend/apps/users/firebase_auth_views.py:464` returns 403 "Email
  address must be verified before logging in." whenever `email_verified` is false (todos 447/449).
- **No verification mail:** `rg sendEmailVerification plant_community_mobile/lib` → no hits.
  `lib/services/auth_service.dart:251` already documents that email sign-up "dead-ends at the token exchange".
  The app log after "Create account": `[AUTH] Registering new user` → 403 → `[AUTH] User registered`. The
  user lands on Profile still signed out, with no error shown.
- **The verify link fails on the hosted page:** a VERIFY_EMAIL oob code was sent twice through the Identity
  Toolkit REST API (signInWithPassword → sendOobCode, iOS key + `X-Ios-Bundle-Identifier`). Both times, opening
  the link (`https://plant-community-prod.firebaseapp.com/__/auth/action?mode=verifyEmail&…&apiKey=AIzaSyDp…`)
  showed "Your request to verify your email has expired or the link has already been used". `accounts:lookup`
  still returned `emailVerified: False`. POSTing the same oobCode to `accounts:update` with the iOS key
  returned `emailVerified: True`, so the code was valid; the page simply couldn't apply it.
  The link's `apiKey` is NOT `FIREBASE_IOS_API_KEY`, and `FIREBASE_API_KEY` is also iOS-app-restricted
  (`API_KEY_IOS_APP_BLOCKED`). **Hypothesis, not verified:** the key in the link is restricted in a way that
  blocks the `firebaseapp.com` action page (see `project_firebase_key_restriction_state` in the owner's notes:
  the keys were narrowed 2026-09-12).
- **No retry after verifying:** a failed exchange leaves the Firebase user signed in. Signing in again with
  the same account fires no `authStateChanges` event (same uid). `_exchangeFirebaseTokenForJWT` uses
  `user.getIdToken()` without `forceRefresh`, so a relaunch re-sends the cached `email_verified=false` token
  and gets 403 again, until that token expires (about 1 h). Log on the iPhone 17 Pro sim:
  `[AUTH] Firebase sign in successful` with no exchange following it. A fresh simulator signed in at once.

## Proposed Solutions

### Option 1: Send the mail, fix the link, retry on verify (recommended)

- **Implementation:**
  - After `createUserWithEmailAndPassword`, call `sendEmailVerification()` and show a "Check your email" state
    with Resend and "I've verified" buttons.
  - "I've verified" calls `user.reload()` and then `getIdToken(true)`, and re-runs the exchange.
  - In `signInWithEmailPassword`, if the user is already the current Firebase user, run the exchange
    directly instead of waiting for `authStateChanges`.
  - Fix the hosted action page: find which key the template link uses and allow `firebaseapp.com` on it.
    Alternatively, set a custom action URL on our own domain that applies the code with an allowed key.
- **Pros:** email sign-up works end to end, and the backend's security rule stays as it is.
- **Cons:** this touches Firebase key restrictions (a Console change made outside the repo).
- **Effort:** half a day, plus a device check.
- **Risk:** medium. This is auth code, and the key change must not widen access beyond the action page.

### Option 2: Hide email sign-up on mobile and offer Google only

- **Implementation:** remove "Create account" with email from the mobile login and registration screens.
- **Pros:** tiny change, and it ends the silent dead end.
- **Cons:** users without a Google account can't join; Sign in with Apple isn't wired.
- **Effort:** 1 h.
- **Risk:** low.

## Recommended Action

1. Owner: confirm Option 1.
2. Find the key the verification-email template link carries, check its restrictions, and allow the
   `plant-community-prod.firebaseapp.com` action page (or use a custom action URL). Record the change and its
   date here.
3. Mobile: add `sendEmailVerification`, the "Check your email" state, reload with a forced token refresh,
   and the same-user exchange retry.
4. Surface the 403 `Email address must be verified` as a user-facing message instead of a silent return to
   Profile.
5. Tests: unit tests for the retry and forced refresh; a widget test for the "Check your email" state.

## Technical Details

- `plant_community_mobile/lib/services/auth_service.dart`: listener ~L155, `signInWithEmailPassword` ~L216,
  doc comment ~L251, `_exchangeFirebaseTokenForJWT` ~L447 (`getIdToken()` without force).
- `backend/apps/users/firebase_auth_views.py:452-472`: the verified-email gate (do not loosen).
- The sim test account `william.tower+simtest@gmail.com` (now verified) can serve as a regression account.
  Its credentials are in the main checkout's gitignored `plant_community_mobile/.env.simtest`.

## Acceptance Criteria

- [x] A fresh email sign-up on a device or simulator receives a verification mail.
- [x] Opening the mailed link on the hosted page shows success. Record the date and the `accounts:lookup`
      `emailVerified: true` result here.
- [x] After verifying, "I've verified" (or signing in again) completes the token exchange without a relaunch
      and without waiting for the token to expire.
- [x] An unverified sign-in shows a user-facing message, not a silent signed-out Profile.
- [x] `flutter test` passes in full.

## Work Log

### 2026-10-25 - Found during the PR #1195 sim check

- Created the sim test account in the app. The token exchange returned 403. The hosted verify page failed twice.
  Verified the account by POSTing the oobCode to `accounts:update`. A fresh simulator then signed in and the
  exchange succeeded.

### 2026-10-26 - Implemented by the todo sweep (run 2026-10-26-2213)

- `plant_community_mobile/lib/services/auth_service.dart`: registration now calls `sendEmailVerification()`
  (a failed send does not fail the registration), and both email methods return whether the email still
  needs verifying. New `resendVerificationEmail()` and `confirmEmailVerified()` ("I've verified": `reload()`,
  then the exchange with `getIdToken(true)`; nothing goes to the backend while Firebase still says unverified).
- The exchange forces a token refresh for a caller-requested retry and whenever the user reads as unverified,
  so a relaunch after verifying no longer re-sends the cached `email_verified=false` token. Signing in again
  as the same Firebase uid (no `authStateChanges` event) runs the exchange directly.
- The view's JSON 403 now maps to `emailNotVerifiedMessage` with `AuthState.emailVerificationRequired`,
  instead of "Failed to connect to server"; a proxy's HTML 403 is left as before.
- New `lib/features/auth/verify_email_screen.dart` (`VerifyEmailPanel`: "Check your email", Resend, "I've
  verified", "Use a different account") replaces the form inline on the sign-in and register screens, not as
  a route, because a pushed sign-in screen keeps the location at `/profile`.
- Tests: a `todo 660` group in `test/services/auth_service_test.dart` (fakes gained `emailVerified`,
  `reload`, `sendEmailVerification` and the email sign-in methods) and
  `test/features/auth/verify_email_screen_test.dart`. AC 1 and 2 (the real mail, the hosted link and its
  API key restriction) stay with the owner and the main session.

### 2026-10-27 - Verified by the todo sweep (run 2026-10-26-2213)

- AC 3: `sh -c "cd plant_community_mobile && flutter test --no-pub test/services/auth_service_test.dart --plain-name 'todo 660'"` — evidence `.sweep-evidence/g1/660-ac2.txt` (not committed), last lines:

  ```text
  00:00 +9: email verification (todo 660) Resend sends the verification mail to the current user
  [AUTH] Exchanging Firebase token for Django JWT
  [AUTH] JWT token exchange successful
  [AUTH] Cancelling auth state subscription
  00:00 +10: All tests passed!
  ```

- AC 4: `sh -c "cd plant_community_mobile && flutter test --no-pub test/features/auth/verify_email_screen_test.dart"` — evidence `.sweep-evidence/g1/660-ac3.txt` (not committed), last lines:

  ```text
  00:00 +2: Resend sends the mail again and says so
  00:00 +3: "I've verified" before the link is opened keeps the panel and says why
  00:00 +4: "I've verified" once the link is opened signs in and leaves for Profile
  00:00 +5: "Use a different account" signs out and shows the form again
  00:00 +6: All tests passed!
  ```

- AC 5: `sh -c 'cd plant_community_mobile && flutter test'` — evidence `.sweep-evidence/g1/660-ac4.txt` (not committed), last lines:

  ```text
  01:11 +1385 ~9: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases a moderation_decided-shaped payload (no post_id key) routes to the topic without a postId query param
  01:11 +1386 ~9: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases an unparseable topic_id does not navigate at all (silent no-op, not a crash)
  01:11 +1387 ~9: plant_community_mobile/test/services/push_message_router_service_test.dart: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  01:11 +1388 ~9: All tests passed!
  ```

### 2026-10-27 - Confirmed by the owner, ticked by the todo sweep (run 2026-10-26-2213)

- AC 1: confirmed by the owner on 2026-10-27: "Owner: "My email was verified." (2026-10-27) — simtest2 fresh in-app sign-up on the iPhone 17 Pro sim; the verification mail arrived (Resend also delivered) and its link was opened" (`state.py confirm`; no command or evidence)
- AC 2: confirmed by the owner on 2026-10-27: "Owner: "My email was verified." (2026-10-27) — hosted action page succeeded after the auth-action page got its own referrer-locked browser key; accounts:lookup for simtest2 returned emailVerified: true on 2026-10-27" (`state.py confirm`; no command or evidence)

### 2026-10-27 - Completed by the todo sweep (run 2026-10-26-2213)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-27 - Review round 1 (PR #1205): no blocking findings; mediums and lows handled by hand

- Fixed, with tests (mutation-checked: removing the guard fails both new tests): when a same-uid
  sign-in's direct exchange fails, `signInWithEmailPassword` now throws `AuthException(state.error)`
  or returns `true` when the 403 still says unverified. Before, it returned `false` and the login
  screen dismissed onto a signed-out Profile with the failure unseen.
- Fixed: `emailNotVerifiedMessage` now ends "then sign in again" instead of "tap I've verified".
  The launch exchange shows it in the global SnackBar, where no such button exists. The
  `AuthState.emailVerificationRequired` doc no longer claims that screens watch the flag.
- Fixed: the test "an unverified sign-in reports it and does not exchange" was renamed to say what
  it proves (no direct same-uid exchange).
- Declined: "any JSON 403 is read as unverified email" (two reviewers). The exchange view has one
  403, the unverified-email one, and its OpenAPI schema documents 403 only as "The token's email
  is not verified" (`backend/apps/users/firebase_auth_views.py`). Rate limits are mapped to 429.
- Declined, low: offline launch for a saved unverified user shows the generic error rather than
  the connectivity one (forced refresh only while unverified; rare and harmless); the still-unverified
  message appears inline and in the SnackBar (same double display every other auth error already
  has); there's no busy flag on "Use a different account" (`signOut` is idempotent and `onCancel` pops once).

### 2026-10-27 - Review round 2 (PR #1205): clean; non-blocking findings

- Fixed (a conflict the round-1 wording introduced): after register, the SnackBar said "then sign in
  again" while the panel said "tap I've verified". `emailNotVerifiedMessage` now reads "Verify your
  email to finish signing in: open the link in the email we sent you.", which fits the panel, the
  SnackBar and the launch path alike. The tests assert the constant, not its wording.
- Declined, low: same-uid sign-in where Firebase says verified but the backend still 403s loops on the
  panel. The exchange forces a token refresh, so the token carries `email_verified: true` and the view
  accepts it; the loop needs the backend and Firebase to disagree about one token.
- Declined, low: `confirmEmailVerified` overtaken by a concurrent exchange or sign-out falls back to
  "not verified yet". It needs a sign-out or user switch during the tap; the next tap recovers.
- Declined, low: no widget test for the panel's auto-dismiss on an authentication that arrives some
  other way. The "I've verified" path is tested end to end, and the listener is three lines that
  call the same `_dismiss`.
- Declined, low: the "Use a different account" busy flag, as in round 1.

## Notes

- p2: every mobile email sign-up silently fails; only Google works.
- Not covered here, and resolved 2026-10-25: the same sim run hit `Quota for bucket
  plant-community-prod.firebasestorage.app exceeded` on upload. The prod project was linked to a closed
  free-trial billing account; the owner relinked it to the active one, and a probe upload then returned 200.
