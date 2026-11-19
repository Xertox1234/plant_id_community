---
status: pending
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

- [ ] Sign in with Apple completes on a real iPhone — record the date and
      result here.
- [ ] Upgrading over an installed build keeps the user signed in on iOS and
      Android — record the date and devices here. → todo 720 (re-pointed 2026-11-19)
- [ ] Firebase password policy minimum is 14 — record the date and the
      console value here.
- [ ] `flutter test` and `flutter analyze` are clean.

## Work Log

### 2026-11-17 - Split out of todo 704

- Owner decision: the code-only items (H7, M13, L8, L9) ship in 704; these
  three wait for console setup and a device.
