---
status: pending
priority: p2
issue_id: "704"
tags: [mobile, flutter, firebase, auth, security]
dependencies: []
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

- [ ] A widget test drives "Forgot password?" from the login screen to
      `sendPasswordResetEmail`.
- [ ] Sign in with Apple completes on a real iPhone — record the date and
      result here.
- [ ] After a forced session expiry, the push token is unregistered and the
      Firestore cache is empty (test).
- [ ] Upgrading over an installed build keeps the user signed in on iOS and
      Android — record the date and devices here.
- [ ] Firebase password policy minimum is 14 — record the date and the
      console value here.
- [ ] `flutter test` and `flutter analyze` are clean.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: H8 and M14 need a device, M17 an owner console
  change; none was safe to ship unverified.

## Notes

H7 and H8 are rated high in the audit; the todo is P2 because the mobile app
is in TestFlight only. Raise it before a store release.
