---
status: completed
priority: p1
issue_id: "717"
tags: [mobile, ios, auth, firebase, app-store, owner]
dependencies: []
triage: ready
triaged: 2026-11-19
owner_decision: "Owner 2026-11-19: build now. Owner setup is DONE 2026-11-19: Sign In with Apple capability on App ID com.plantcommunity.plantCommunityMobile (Team 3442937R38); SIWA key 4M43HB8B44; Services ID com.plantcommunity.plantCommunityMobile.signin (return URL https://plant-community-prod.firebaseapp.com/__/auth/handler); relay email sources houseplant-md.com, send.houseplant-md.com, noreply@houseplant-md.com all SPF green; Firebase plant-community-prod Apple provider Enabled with the OAuth code flow (Team ID, Key ID, private key), so revokeTokenWithAuthorizationCode works. Android: HIDE the Apple button (owner: 'hide on android'), iOS only. Privacy policy: add Apple sign-in + private relay wording, NO LEGAL_POLICY_VERSION bump (owner: opt-in, nothing changes for existing accounts). The owner TestFlight Hide-My-Email device criterion cannot run before a build ships: leave it unticked and report it as owner-only; it will be re-pointed to a follow-up todo. (2026-11-19)"
---

# Mobile: add "Continue with Apple" for App Store review

## Problem

The iOS app offers Google sign-in (`google_sign_in`, `AuthService.signInWithGoogle`
in `plant_community_mobile/lib/services/auth_service.dart`) next to email and
password. App Store Review Guideline 4.8 (Login Services): an app that uses a
third-party login such as Google must also offer an equivalent login option
that limits data collection to name and email, lets the user keep their email
private, and does not track them without consent. Sign in with Apple is the
standard way to meet this, and the owner decided to use it (2026-11-19). Without
it, App Review will reject the public release.

## Findings

- The backend is already prepared. `FIREBASE_ALLOWED_SIGN_IN_PROVIDERS`
  (`backend/apps/users/constants.py`) accepts `apple.com`, and
  `account_links.PROVIDER_NAMES` labels it "Apple". The Firebase token
  exchange (`firebase_auth_views.py`) treats Apple like Google for linking and
  verified email.
- The mobile app has no Apple sign-in code and no `sign_in_with_apple`
  dependency. Firebase Auth does Apple natively (`AppleAuthProvider` with
  `FirebaseAuth.signInWithProvider`), so a separate plugin may not be needed.
- An Apple user can hide their email. Firebase then receives a
  `@privaterelay.appleid.com` address. Apple delivers mail to that address
  only from a sender domain registered under Sign in with Apple → Email
  Communication in the Apple Developer account. Without that, the backend's
  verification, notification and digest emails (sent through Resend) are
  silently dropped.
- Apple sends the user's name only on the first sign-in. If the app does not
  pass it on that first sign-in, it is lost.
- Guideline 5.1.1(v): an app with Sign in with Apple must revoke the user's
  Apple tokens when the account is deleted (FlutterFire:
  `FirebaseAuth.revokeTokenWithAuthorizationCode`). The current deletion flow
  is `request_account_deletion` in `backend/apps/users/deletion.py` plus
  `delete_account_screen.dart` on mobile.
- Web sign-in is Django Google OAuth only (GitHub was removed on 2026-11-19).
  Guideline 4.8 applies to the iOS app. Apple on the web is optional, and out
  of scope here.

## Recommended Action

1. Owner setup:
   - In the Apple Developer account, enable the Sign in with Apple capability
     on the app ID `com.plantcommunity.plantCommunityMobile`.
   - Register the email sender domain under Sign in with Apple → Email
     Communication.
   - In Firebase Authentication (project `plant-community-prod`), enable the
     Apple provider.
2. Add the capability to the iOS Runner entitlements. Add a "Continue with
   Apple" button to the login and register screens using Apple's button style,
   placed at least as prominently as Google. It runs through the existing
   Firebase → Django exchange with the same `accepted_terms` consent gate.
3. On the first sign-in, pass Apple's given and family name to the backend
   exchange.
4. On account deletion for an Apple-linked user, revoke the Apple token
   before the account is removed.
5. Android: hide the button, or use Firebase's web flow, as the owner decides
   during triage. Guideline 4.8 is iOS-only.
6. Update the privacy policy (en/es/fr in `web/src/content/legal/`) to name
   Apple sign-in and the private relay address. Decide during triage whether
   this is a material change that needs a `LEGAL_POLICY_VERSION` bump.

## Acceptance Criteria

- [x] iOS login and register screens show "Continue with Apple" in Apple's
      button style; a widget test covers both screens.
- [x] A new Apple sign-up goes through the consent step and creates one
      Django account; a returning Apple sign-in reaches the same account.
      Backend tests cover an `apple.com` exchange with a
      `privaterelay.appleid.com` email.
- [x] Apple's name from the first sign-in is stored on the new account
      (test).
- [x] Deleting an Apple-linked account revokes the Apple token (test with
      the revoke call mocked).
- [ ] Owner: on a real iPhone (TestFlight), sign up with Apple using "Hide My → todo 718 (re-pointed 2026-11-19)
      Email", receive the verification or welcome email at the relay address,
      then delete the account — record the date and build number.
- [x] Privacy policy (en/es/fr) mentions Apple sign-in.

## Work Log

### 2026-11-19 - Filed

- Owner: "create a todo to add continue with apple as it is required by
  Apple". Filed alongside the GitHub sign-in removal PR.

### 2026-11-19 - Implemented by the todo sweep (run 2026-11-19-1634)

- iOS only (`appleSignInSupported`, hidden on Android per the owner): an
  `AppleSignInButton` (Apple logo, "Continue with Apple", black on light and
  white on dark, above Google) on the sign-in and register screens; the
  register one waits for the consent box like Google. `AuthService.signInWithApple`
  uses firebase_auth's native `signInWithProvider(AppleAuthProvider)` with
  the `email` and `name` scopes, so no new dependency and no pubspec change.
  The Sign in with Apple entitlement is in both Runner entitlements files.
- Name: the plugin hands Apple's first-sign-in name to Firebase with the
  credential, and the exchange during or right after an Apple sign-in forces
  a token refresh so the `name` claim is there. The backend keeps reading the
  name only from the verified token (audit C8), so `firebase_auth_views.py`
  needed no change; `backend/apps/users/tests/test_firebase_auth.py`
  (`FirebaseAppleSignInTestCase`) covers a relay-address `apple.com` sign-up
  (428, then one account), the returning sign-in and the stored name.
- Deletion: `ReauthMethod.apple` (wins wherever Apple sign-in is offered)
  re-authenticates with `reauthenticateWithProvider` and keeps Apple's
  authorization code; the delete screen calls `revokeAppleSignIn`
  (`revokeTokenWithAuthorizationCode`, best-effort, 5 s bound) after the
  server accepts the deletion and before signing out, so a refused deletion
  keeps a working Apple sign-in.
- Privacy policy en/es/fr names Apple sign-in, the private relay address and
  the revocation; no `LEGAL_POLICY_VERSION` bump (owner decision).
- The owner's TestFlight Hide-My-Email check needs a shipped build: left
  open for the follow-up todo.

### 2026-11-19 - Verified by the todo sweep (run 2026-11-19-1634)

- AC 1: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/auth/apple_sign_in_button_test.dart test/features/auth/login_screen_test.dart test/features/auth/register_screen_test.dart test/features/auth/google_sign_in_button_test.dart'` — evidence `.sweep-evidence/g1/717-ac0.txt` (not committed), last lines:

  ```text
  00:02 +18: plant_community_mobile/test/features/auth/register_screen_test.dart: keyboard submit with the box unticked registers nobody
  00:02 +19: plant_community_mobile/test/features/auth/register_screen_test.dart: keyboard submit with the box unticked registers nobody
  00:02 +20: plant_community_mobile/test/features/auth/register_screen_test.dart: keyboard submit with the box unticked registers nobody
  00:02 +21: plant_community_mobile/test/features/auth/register_screen_test.dart: keyboard submit with the box unticked registers nobody
  00:02 +22: All tests passed!
  ```

- AC 2: `bash -c 'set -e; cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest -p no:cacheprovider -v --create-db apps/users/tests/test_firebase_auth.py::FirebaseAppleSignInTestCase::test_new_apple_relay_user_needs_consent_then_gets_one_account apps/users/tests/test_firebase_auth.py::FirebaseAppleSignInTestCase::test_returning_apple_sign_in_reaches_the_same_account; cd plant_community_mobile && flutter test --no-pub -r expanded test/services/auth_service_consent_test.dart --plain-name "Apple sign-in (todo 717)"'` — evidence `.sweep-evidence/g1/717-ac1.txt` (not committed), last lines:

  ```text
  ======================== 2 passed, 3 warnings in 23.58s ========================
  …
  00:00 +6: Apple sign-in (todo 717) an Apple failure throws a fixed message
  [AUTH ERROR] Apple sign in failed: failed
  [AUTH ERROR] Unmapped Firebase code: failed
  [AUTH] Cancelling auth state subscription
  00:00 +7: All tests passed!
  ```

- AC 3: `bash -c 'set -e; cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest -p no:cacheprovider -v --create-db apps/users/tests/test_firebase_auth.py::FirebaseAppleSignInTestCase::test_apple_name_from_the_first_sign_in_is_stored apps/users/tests/test_firebase_auth.py::FirebaseAppleSignInTestCase::test_apple_name_is_read_from_the_token_not_the_request; cd plant_community_mobile && flutter test --no-pub -r expanded test/services/auth_service_consent_test.dart --plain-name "forces a token refresh"'` — evidence `.sweep-evidence/g1/717-ac2.txt` (not committed), last lines:

  ```text
  ======================== 2 passed, 3 warnings in 22.62s ========================
  …
  [AUTH] Exchanging Firebase token for Django JWT
  [AUTH] JWT token exchange successful
  [AUTH] Apple sign in successful: **@example.com
  [AUTH] Cancelling auth state subscription
  00:00 +1: All tests passed!
  ```

- AC 4: `bash -c 'set -e; cd plant_community_mobile && flutter test --no-pub -r expanded test/services/auth_service_consent_test.dart --plain-name "deleting an Apple-linked account" && flutter test --no-pub -r expanded test/features/settings/delete_account_screen_test.dart && flutter test --no-pub -r expanded test/services/auth_service_test.dart --plain-name "re-authentication for account deletion"'` — evidence `.sweep-evidence/g1/717-ac3.txt` (not committed), last lines:

  ```text
  [AUTH] Re-auth refused: invalid-credential
  [AUTH] Cancelling auth state subscription
  00:00 +8: re-authentication for account deletion (Plan B task 10) with no Firebase user it throws a readable AuthException
  [AUTH] Cancelling auth state subscription
  00:00 +9: All tests passed!
  ```

- AC 6: `bash -c 'set -e; cd web/src/content/legal && grep -n -i -E "sign in with apple|con apple|avec apple|privaterelay" privacy.en.md privacy.es.md privacy.fr.md && head -1 privacy.en.md privacy.es.md privacy.fr.md'` — evidence `.sweep-evidence/g1/717-ac5.txt` (not committed), last lines:

  ```text
  ==> privacy.es.md <==
  <!-- version: 2026-11-10 -->

  ==> privacy.fr.md <==
  <!-- version: 2026-11-10 -->
  ```

### 2026-11-19 - Completed by the todo sweep (run 2026-11-19-1634)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-19 - Review round 1: non-blocking findings

Round 1 was clean (nothing blocking). Each non-blocking finding was fixed by
hand or declined:

- **Fixed (medium, raised twice):** `delete_account_screen.dart` revoked the
  Apple token only after the 202. The server queues `delete_account_task` on
  commit, and its `erase_firebase_data` step deletes the Firebase user that
  `revokeTokenWithAuthorizationCode` needs, so the revoke could fail without
  anyone noticing. The revoke now runs right after the Apple re-auth, before the
  deletion request. That is the reauthenticate → revoke → delete order used in
  community Firebase guides. A refused deletion now leaves the Apple grant
  revoked, and the next Apple sign-in asks for consent again. Tests: the
  order `reauth, revokeApple, delete, signOut, clearCache`; a refused
  deletion `reauth, revokeApple, delete`; a cancelled Apple re-auth revokes
  nothing. The real device check is todo 718 (Settings → Sign in with Apple
  no longer lists the app).
- **Fixed (low):** `signOut()` now clears `_appleRefreshUid` and the unused
  `_appleRevocation` code.
- **Declined (medium):** `LEGAL_POLICY_VERSION` not bumped for the new privacy
  wording. The owner decided this on 2026-11-19: Apple sign-in is opt-in, so
  nothing changes for existing accounts.
- **Declined (low, three phrasings):** a stale `_appleRefreshUid` forces at most
  one extra ID-token refresh. That is harmless, and it is now cleared on sign-out.
- **Declined (low):** re-tapping Apple while a Firebase user with the same uid
  remains after a failed exchange. Google has the same gap today; a fix
  belongs to both buttons, not only to this PR.
- **Declined (low):** no Apple revoke when a new Apple user declines the
  consent sheet. No Django account was ever created, and Guideline
  5.1.1(v) applies to account deletion.
- **Declined (low):** `debugDefaultTargetPlatformOverride` reset at the end of
  each test rather than in a tear-down. That only matters once a test is
  already failing.
- **Declined (low):** two doc-comment lines over 80 columns. `dart format`
  reports no changes.
- **Declined (low):** the backend Apple tests mainly pin current behaviour.
  The backend logic is shared with Google on purpose, and the tests cover
  the relay email, the 428 consent step, and a returning sign-in.
