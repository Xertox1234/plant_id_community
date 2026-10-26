---
status: pending
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

- [ ] A fresh email sign-up on a device or simulator receives a verification mail.
- [ ] Opening the mailed link on the hosted page shows success. Record the date and the `accounts:lookup`
      `emailVerified: true` result here.
- [ ] After verifying, "I've verified" (or signing in again) completes the token exchange without a relaunch
      and without waiting for the token to expire.
- [ ] An unverified sign-in shows a user-facing message, not a silent signed-out Profile.
- [ ] `flutter test` passes in full.

## Work Log

### 2026-10-25 - Found during the PR #1195 sim check

- Created the sim test account in the app. The token exchange returned 403. The hosted verify page failed twice.
  Verified the account by POSTing the oobCode to `accounts:update`. A fresh simulator then signed in and the
  exchange succeeded.

## Notes

- p2: every mobile email sign-up silently fails; only Google works.
- Not covered here, and resolved 2026-10-25: the same sim run hit `Quota for bucket
  plant-community-prod.firebasestorage.app exceeded` on upload. The prod project was linked to a closed
  free-trial billing account; the owner relinked it to the active one, and a probe upload then returned 200.
