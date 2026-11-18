---
status: completed
priority: p2
issue_id: "704"
tags: [mobile, flutter, firebase, auth, security]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Split (owner 2026-11-17): H7, M13, L8, L9 ship now; H8 Sign in with Apple, M14 and M17 (device/console) move to todo 715"
---

# Mobile auth: password reset, Sign in with Apple, sign-out cleanup, token storage

## Problem

The auth + legal audit of 2026-11-10 left seven mobile findings unfixed: two
block real users or a store release, the rest are cleanup that needs a device
check before it ships.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md` (rows named below).

- **H7** No password reset for email/password accounts. Sign-in checks the
  Firebase credential; the only "Forgot password?" is inside the 409 conflict
  SnackBar and resets the Django credential
  (`lib/features/auth/login_screen.dart`, `password_reset_link.dart:5-11`).
  `grep sendPasswordResetEmail lib`: 0 hits.
- **H8** Google sign-in on iOS with no Sign in with Apple
  (`login_screen.dart:179`, `register_screen.dart:209`). App Store guideline
  4.8: rejection risk at App Review.
- **M13** Session expiry and external sign-out leave the device's push token
  registered and clear nothing; plain logout does not clear the Firestore
  offline cache or sign out of Google
  (`lib/services/auth_service.dart:704-743,1267-1288`,
  `firestore_service.dart:33`).
- **M14** `FlutterSecureStorage()` with default options
  (`auth_service.dart:187,190`); the 7-day refresh token is stored and never
  read; the Android manifest does not disable backup.
- **M17** Password minimum is 6 on mobile (Firebase) and 14 on the web
  (`login_screen.dart:334`, `register_screen.dart:143`).
- **L8** Raw exception text shown to the user
  (`auth_service.dart:363,365,458,637,739`).
- **L9** Declining the terms can leave the Firebase user alive if `delete()`
  throws (`auth_service.dart:1203-1236`).

## Recommended Action

1. H7: add "Forgot password?" to the login screen calling
   `sendPasswordResetEmail`, with the same answer for known and unknown
   addresses.
2. H8: add Sign in with Apple (`sign_in_with_apple` + Firebase
   `OAuthProvider('apple.com')`), the entitlement, and the backend's accepted
   providers. Apple's private-relay addresses must pass the verified-email
   check.
3. M13: one sign-out routine used by every exit path: unregister the push
   token, clear the Firestore cache, sign out of Google.
4. M14: stop storing the unused refresh token; set
   `first_unlock_this_device`, reading the old item once and rewriting it so
   signed-in users stay signed in; set `android:allowBackup="false"`.
5. M17: owner sets the Firebase password policy to 14 in the console, then the
   app's validators follow.
6. L8, L9: map exceptions to fixed messages; retry or queue the delete.

## Technical Details

- Patterns: `plant_community_mobile/docs/patterns/firebase-auth.md`.
- Run `flutter test` and `flutter analyze` first: the audit took no mobile
  baseline because it changed no mobile code.

## Acceptance Criteria

- [x] A widget test drives "Forgot password?" from the login screen to
      `sendPasswordResetEmail`.
- [ ] Sign in with Apple completes on a real iPhone — record the date and
      result here. → todo 715 (re-pointed 2026-11-17)
- [x] After a forced session expiry, the push token is unregistered and the
      Firestore cache is empty (test).
- [ ] Upgrading over an installed build keeps the user signed in on iOS and
      Android — record the date and devices here. → todo 715 (re-pointed 2026-11-17)
- [ ] Firebase password policy minimum is 14 — record the date and the
      console value here. → todo 715 (re-pointed 2026-11-17)
- [x] L8: auth failures show fixed messages, never raw exception text (test).
- [x] L9: when the Firebase `delete()` throws after a terms decline, the
      delete is retried or queued and the user is not left signed in (test).
- [x] `flutter test` and `flutter analyze` are clean.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: H8 and M14 need a device, M17 an owner console
  change; none was safe to ship unverified.

### 2026-11-17 - Triage: split (owner decision)

- H7, M13, L8 and L9 ship in this todo. H8 (Sign in with Apple), M14
  (secure-storage options, refresh token, allowBackup) and M17 (Firebase
  password policy) move to todo 715: each needs Apple/Firebase console setup
  or a device upgrade check. Criteria for L8 and L9 added; the three
  device/console criteria re-pointed to 715.

### 2026-11-17 - Implemented by the todo sweep (run 2026-11-18-0148)

- H7: "Forgot password?" on the sign-in form opens `ForgotPasswordDialog`
  (`lib/features/auth/login_screen.dart`), which calls the new
  `AuthService.sendPasswordResetEmail`. `user-not-found` and `user-disabled`
  answer like a sent mail, so the dialog cannot tell which addresses have
  accounts. Widget test: `test/features/auth/login_screen_test.dart`.
- M13: every sign-out path (`signOut()`, session expiry, a sign-out Firebase
  reports, a declined consent) now ends with one routine,
  `AuthService._endDeviceSession`. It runs once per session and never throws.
  It deletes the device's FCM token (`PushRegistrationService.revokeDeviceToken`),
  clears the Firestore offline cache, and signs out of Google, initialising
  the plugin first for a session restored at launch. After a session expiry
  there is no JWT to call `/push-devices/unregister/` with (it needs
  `IsAuthenticated`), so "unregistered" means this: FCM refuses the deleted
  token, and `apps/core/fcm.py` prunes the row at its next send
  (`UnregisteredError`). `signOut()` still unregisters with the server first.
- L8: no unmapped failure shows exception text any more. Fixed messages
  replace it in `auth_service.dart`: sign-in, Google, register, sign-out and
  the unmapped-Firebase-code default. `profile_screen.dart`'s "Logout failed"
  SnackBar is fixed too. The text goes to the debug log only.
- L9: `declineTerms` tries `delete()` again after 0.5 s and 2 s, then signs
  out whatever happened. The client cannot delete a Firebase user once it is
  signed out, so a delete that keeps failing is left to the server's orphan
  prune (`apps/users/retention.py`). The prune is log-only while
  `ORPHAN_FIREBASE_PRUNE_ENABLED` is off.
- `deleteToken` is deprecated in firebase_messaging 17. It is kept, with an
  ignore, because `unregister()` retires the installation id, which this app
  does not register.

### 2026-11-18 - Verified by the todo sweep (run 2026-11-18-0148)

- AC 1: `/bin/sh -c 'cd plant_community_mobile && flutter test test/features/auth/login_screen_test.dart'` — evidence `.sweep-evidence/g1/704-ac0.txt` (not committed), last lines:

  ```text
  [AUTH] Password reset: user-not-found
  00:00 +2: a failure the address does not decide shows a fixed message and keeps the dialog open
  [AUTH] Password reset: internal-error
  00:01 +3: an empty address is refused before anything is sent
  00:01 +4: All tests passed!
  ```

- AC 3: `/bin/sh -c 'cd plant_community_mobile && flutter test test/services/auth_service_test.dart --plain-name "sign-out clears the device"'` — evidence `.sweep-evidence/g1/704-ac2.txt` (not committed), last lines:

  ```text
  [AUTH] Cancelling auth state subscription
  00:00 +3: sign-out clears the device (todo 704, audit M13) a launch with nobody signed in clears nothing
  [AUTH] Firebase auth state changed: ***
  [AUTH] Cancelling auth state subscription
  00:00 +4: All tests passed!
  ```

- AC 6: `/bin/sh -c 'cd plant_community_mobile && flutter test test/services/auth_service_test.dart --plain-name "fixed error messages"'` — evidence `.sweep-evidence/g1/704-ac5.txt` (not committed), last lines:

  ```text
  [AUTH] JWT token exchange successful
  [AUTH] Signing out user
  [AUTH ERROR] Sign out failed: Bad state: keychain error -34018
  [AUTH] Cancelling auth state subscription
  00:01 +5: All tests passed!
  ```

- AC 7: `/bin/sh -c 'cd plant_community_mobile && flutter test test/services/auth_service_consent_test.dart --plain-name "declineTerms"'` — evidence `.sweep-evidence/g1/704-ac6.txt` (not committed), last lines:

  ```text
  [AUTH] Consent declined; delete try 1 failed: [firebase_auth/network-request-failed] null
  [AUTH] Consent declined; delete try 2 failed: [firebase_auth/network-request-failed] null
  [AUTH] Consent declined; delete try 3 failed: [firebase_auth/network-request-failed] null
  [PUSH] FCM token delete failed: [core/no-app] No Firebase App '[DEFAULT]' has been created - call Firebase.initializeApp()
  00:00 +5: All tests passed!
  ```

- AC 8: `/bin/sh -c 'cd plant_community_mobile && flutter analyze && flutter test'` — evidence `.sweep-evidence/g1/704-ac7.txt` (not committed), last lines:

  ```text
  02:12 +2023 ~11: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases a moderation_decided-shaped payload (no post_id key) routes to the topic without a postId query param
  02:13 +2024 ~11: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases an unparseable topic_id does not navigate at all (silent no-op, not a crash)
  02:13 +2025 ~11: plant_community_mobile/test/services/push_message_router_service_test.dart: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  02:13 +2026 ~11: All tests passed!
  ```

### 2026-11-18 - Completed by the todo sweep (run 2026-11-18-0148)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-18 - Repaired by the todo sweep (run 2026-11-18-0148)

- Review round 1 (medium, regression): clearing the Firestore cache on every sign-out also deleted queued writes that main keeps and syncs at the next sign-in.
- `signOut()` and the session expiry now wait for `waitForPendingWrites()` (bounded, 5 s) before `_firebaseAuth.signOut()`, while the user is still signed in; the queue is per user. `_endDeviceSession` clears the cache only after a confirmed flush, or after a declined consent (that account is deleted).
- A sign-out Firebase reports (a revoked token) cannot flush, so it now keeps the cache, as main did; the PR's test for that path was changed to say so. The push token is still deleted on every path.
- New tests in `plant_community_mobile/test/services/auth_service_test.dart`: the flush runs before `firebase.signOut` on both paths (checked by moving it after the sign-out, which fails the test), and a flush that never completes keeps the cache.

## Notes

H7 and H8 are rated high in the audit; the todo is P2 because the mobile app
is in TestFlight only. Raise it before a store release.
