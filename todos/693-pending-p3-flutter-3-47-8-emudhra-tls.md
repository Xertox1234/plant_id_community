---
status: pending
priority: p3
issue_id: "693"
tags: [android, flutter, security, tls, mobile, release]
dependencies: []
---

# Upgrade Flutter to >= 3.47.8 before the first Android release (eMudhra CA revocation)

## Problem

Several intermediate CA certificates issued by eMudhra had their private keys
compromised and were revoked by Google on 2026-10-17. Dart's `dart:io` TLS on
**Android, Windows and Linux** ships its own trust handling, so an app built with
an affected SDK can still accept a forged certificate made with those keys,
which lets a man-in-the-middle impersonate our API
([GHSA-frr6-h895-5pxp](https://github.com/dart-lang/sdk/security/advisories/GHSA-frr6-h895-5pxp)).
Every `dio` / `http` call the app makes goes through `dart:io`.

- Affected: Flutter stable < **3.47.8** (Dart < 3.13.7). No backport to 3.41.x is listed.
- We are on **3.41.9**: locally (`/opt/homebrew/share/flutter`) and in CI
  (`.github/workflows/mobile-ci.yml`, `.github/workflows/security-scan.yml`).
- iOS, macOS and web are **not** affected; they verify certificates with the OS or browser.

Nobody is exposed today: Android has not shipped (todo 691 is blocked on the Play
launch decision). This must land before the first Play upload, or that first build
ships the vulnerable trust store.

The Firestore-on-iOS half of the same incident (the Firebase email of
2026-11-03) was fixed separately by moving `firebase_core` to 4.15.2, which pins
Firebase iOS SDK 12.19.3.

## Recommended Action

1. Upgrade the local Flutter SDK and both CI `flutter-version` pins to >= 3.47.8.
2. Fix whatever the SDK jump breaks (analyzer, codegen, tests); it spans six
   minor versions.
3. Rebuild iOS (TestFlight) as well. It is not affected by this advisory, but it
   should ship on the same SDK as Android.

## Acceptance Criteria

- [ ] `flutter --version` and both workflow pins report >= 3.47.8
- [ ] `flutter analyze` clean and `flutter test` green on the new SDK
- [ ] `flutter build apk` and `flutter build ios` succeed
- [ ] Todo 691's first Play upload is built with this SDK

## Work Log

- 2026-11-03: Filed while fixing the Firestore iOS SDK (Firebase eMudhra notice).

## Notes

- Advisory: <https://github.com/dart-lang/sdk/security/advisories/GHSA-frr6-h895-5pxp>
