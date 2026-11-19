---
status: completed
priority: p2
issue_id: "715"
tags: [mobile, flutter, firebase, auth, security, device-check, owner]
dependencies: []
triage: ready
triaged: 2026-11-19
owner_decision: "Owner 2026-11-19: H8 already done (717/719), record it confirmed; upgrade check moves to a separate p1 owner device todo 720; owner sets the Firebase password policy to 14 now and the app's validators follow in this PR; criterion 0 confirmed by the owner (2026-11-19): It asked me to sign in with apple first, then continued successfully (build 26, todo 719); criterion 2 confirmed by the owner (2026-11-19): Firebase console 2026-11-19, reloaded and still set: Password policy = Require enforcement, minimum length 14, maximum 4096, Force upgrade on sign-in off, no character-class requirements"
---

# Mobile: Sign in with Apple, secure-storage options, password policy

## Problem

Split out of todo 704 on 2026-11-17. These three findings from the
2026-11-10 auth + legal audit cannot be finished in code alone.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md`; detail in todo 704.

- **H8** Google sign-in on iOS with no Sign in with Apple
  (`login_screen.dart:179`, `register_screen.dart:209`). App Store guideline
  4.8: rejection risk at App Review.
- **M14** `FlutterSecureStorage()` with default options
  (`auth_service.dart:187,190`); the 7-day refresh token is stored and never
  read; the Android manifest does not disable backup.
- **M17** Password minimum is 6 on mobile (Firebase) and 14 on the web
  (`login_screen.dart:334`, `register_screen.dart:143`).

## Recommended Action

1. Owner: enable the Sign in with Apple capability for the app ID in Apple
   Developer, and the Apple provider in Firebase Auth.
2. H8: add Sign in with Apple (`sign_in_with_apple` + Firebase
   `OAuthProvider('apple.com')`) and the entitlement. The backend already
   accepts `apple.com`. Apple's private-relay addresses must pass the
   verified-email check.
3. M14: stop storing the unused refresh token; set
   `first_unlock_this_device`, reading the old item once and rewriting it so
   signed-in users stay signed in; set `android:allowBackup="false"`.
4. M17: owner sets the Firebase password policy to 14, then the app's
   validators follow.
5. The device check can share a run with todo 713's.

## Acceptance Criteria

- [x] Sign in with Apple completes on a real iPhone — record the date and
      result here.
- [ ] Upgrading over an installed build keeps the user signed in on iOS and
      Android — record the date and devices here. → todo 720 (re-pointed 2026-11-19)
- [x] Firebase password policy minimum is 14 — record the date and the
      console value here.
- [x] `flutter test` and `flutter analyze` are clean.

## Work Log

### 2026-11-17 - Split out of todo 704

- Owner decision: the code-only items (H7, M13, L8, L9) ship in 704; these
  three wait for console setup and a device.

### 2026-11-19 - Implemented by the todo sweep (run 2026-11-19-2027)

- H8 needed no code here: Sign in with Apple shipped in todos 717/719; the owner confirmed criterion 0 on build 26.
- M14: the auth token store (`AuthService.authTokenStorage`) uses iOS `first_unlock_this_device`; the unused Django refresh token is no longer stored, and an older build's copy is deleted at launch and on every clear. The plugin (darwin 0.4.3) reads and deletes across accessibility levels and the next exchange rewrites the access token under the new level; Firebase holds the sign-in itself, so the change cannot sign anyone out.
- M14: `android:allowBackup="false"` in the Android manifest.
- M17: sign-up `validatePassword` and its helper text follow the owner's Firebase policy of 14 (`minPasswordLength`); the sign-in form keeps its empty-only check, since the policy does not force an upgrade on sign-in. Two register-form test fixtures moved from 7- to 14-character passwords.

### 2026-11-19 - Verified by the todo sweep (run 2026-11-19-2027)

- AC 4: `cd plant_community_mobile && flutter analyze && flutter test` — evidence `.sweep-evidence/g1/715-ac3.txt` (not committed), last lines:

  ```text
  02:53 +2189 ~11: plant_community_mobile/test/services/api_service_forum_unlock_test.dart: neither a token nor the password is ever logged
  02:53 +2189 ~11: plant_community_mobile/test/services/push_foreground_presenter_test.dart: scan_job_finished foreground message shows a banner and calls tracker.onPush
  [PUSH] Foreground presentation not set: [core/no-app] No Firebase App '[DEFAULT]' has been created - call Firebase.initializeApp()
  02:53 +2190 ~11: plant_community_mobile/test/services/api_service_forum_unlock_test.dart: neither a token nor the password is ever logged
  02:53 +2191 ~11: All tests passed!
  ```

### 2026-11-19 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-19-2027)

- AC 1: confirmed by the owner on 2026-11-19: "It asked me to sign in with apple first, then continued successfully (build 26, todo 719)" (`state.py confirm`; no command or evidence)
- AC 3: confirmed by the owner on 2026-11-19: "Firebase console 2026-11-19, reloaded and still set: Password policy = Require enforcement, minimum length 14, maximum 4096, Force upgrade on sign-in off, no character-class requirements" (`state.py confirm`; no command or evidence)

### 2026-11-19 - Completed by the todo sweep (run 2026-11-19-2027)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-19 - Review round 1 (PR #1389): clean, lows handled by hand

Round 1 found no blocking finding. Of its lows:

- Fixed: the console policy (Require enforcement) rejects a short password
  with `password-does-not-meet-requirements`, which fell through to the
  generic message. It now maps to the same text as `weak-password`, built
  from `minPasswordLength`. The constant moved from `login_screen.dart` to
  `auth_service.dart`, so the service no longer hardcodes 14. New tests
  cover both codes.
- Fixed: the storage doc comment said `allowBackup="false"` stops every
  restore. On Android 12+ it does not stop a device-to-device transfer. That
  case is harmless, because the plugin's default `resetOnError: true` wipes
  a store the new key cannot open and the next launch's exchange writes it
  again. The comment now says so.
- Fixed: the `forum_unlock_store.dart` comment still described the auth
  tokens' storage options as the plain default.
- Declined: the launch-time `_deleteLegacyRefreshToken` duplicates
  `_clearJWT` on the usual paths. It is kept on purpose, so an old build's
  refresh token goes even when no exchange or sign-out runs.
- Declined: the todo 587/607 race tests still plant a refresh token. They
  still pin the order of the deletes they were written for.

### 2026-11-19 - Review round 2 (PR #1389): clean

No blocking finding. Two lows, both declined:

- `android:dataExtractionRules`, to exclude the secure store from Android 12+
  device transfer as well. Declined: a transferred store cannot be opened with
  the new device's key, and the plugin resets it (round 1 above).
- The legacy-refresh-token test passes without `_deleteLegacyRefreshToken`,
  because the signed-in launch exchange clears the key too. Declined, as in
  round 1: the call stays as a belt-and-braces cleanup.
