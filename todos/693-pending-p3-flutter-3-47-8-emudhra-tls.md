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
- [x] `flutter analyze` clean and `flutter test` green on the new SDK
- [x] `flutter build apk` and `flutter build ios` succeed
- [ ] Todo 691's first Play upload is built with this SDK → todo 691 (re-pointed 2026-11-04; owner: "Move it to todo 691")

## Work Log

- 2026-11-03: Filed while fixing the Firestore iOS SDK (Firebase eMudhra notice).
- 2026-11-04: Upgrade on Flutter 3.47.9 (Dart 3.13.7), newest stable on 2026-10-29.
  - Owner chose side-by-side: 3.47.9 installed on the external drive for this work;
    the shared `/opt/homebrew/share/flutter` stays 3.41.9 until this PR merges, because
    two peer worktrees have uncommitted Flutter work. AC 1 is ticked when it moves
    (owner 2026-11-04: "we will upgrade the SDK after merge").
  - CI pins `mobile-ci.yml` and `security-scan.yml`: 3.41.9 -> 3.47.9.
  - 3.47.9 refuses Gradle < 8.14.0 and AGP < 8.11.1 (`DependencyVersionChecker.kt`):
    wrapper 8.12 -> 8.14.6, AGP 8.9.1 -> 8.11.2. Kotlin 2.2.21 has no floor. Flutter now
    WARNS for Gradle < 9.1.0, AGP < 9.0.1, Kotlin < 2.3.20 (new apps get Gradle 9.3.1 /
    AGP 9.1.0): a major move, deferred to its own change. The Flutter migrator added
    `android.builtInKotlin=false` / `android.newDsl=false` to `gradle.properties` (it
    re-applies them per build). minSdk stays 24 (`flutter.minSdkVersion`).
  - `SizeTransition.axisAlignment` is deprecated on 3.47 but its replacement does not exist
    on 3.41.9, so both uses keep it under `// ignore: deprecated_member_use`.
  - `flutter analyze` added the build/android/ios excludes to `analysis_options.yaml` itself.
  - iOS: 3.47 migrates plugins to Swift Package Manager, which failed on a fresh checkout
    ("Xcode workspace not found") and, after `pod install`, moved Firebase out of the tracked
    `Podfile.lock` into a gitignored `Package.resolved`. Turned off in `pubspec.yaml`
    (`enable-swift-package-manager: false`) to keep this a minimal upgrade; Firebase iOS SDK
    stays 12.19.3 (#1262's eMudhra fix). Flutter warns the switch goes away later.
  - `flutter pub get` (not upgrade): only SDK-pinned packages moved in `pubspec.lock`
    (`meta` 1.17.0 -> 1.19.0 etc.); codegen regenerated with no diff.
  - Results: `flutter analyze` no issues; `flutter test` 1581 passed, 11 skipped;
    `flutter build apk` -> app-release.apk 69.7 MB; `flutter build ios --no-codesign` from a
    fresh state (generated iOS dirs moved aside, no manual `pod install`) -> Runner.app 62.5 MB.
  - AC 4 re-pointed to todo 691 (owner: "Move it to todo 691").

## Notes

- Advisory: <https://github.com/dart-lang/sdk/security/advisories/GHSA-frr6-h895-5pxp>
