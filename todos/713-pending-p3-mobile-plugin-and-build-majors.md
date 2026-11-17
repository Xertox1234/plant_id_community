---
status: pending
priority: p3
issue_id: "713"
tags: [mobile, flutter, firebase, android, dependencies, dependabot, upgrade]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Bump all: go_router 18, flutter_local_notifications 23, cached_network_image 4, lucide 4, Gradle 9/AGP 9; owner does one combined iPhone+Android device check afterwards (2026-11-17)"
---

# Mobile majors: FlutterFire set, plugin majors, Gradle 9 / AGP 9

## Problem

The Flutter app is a major behind on the Firebase plugins and on six other
plugins, and the Android build is a major behind on Gradle and AGP. Every one
touches native code, so each needs a device check, and they are cheapest
taken together in one TestFlight build.

## Findings

Source: `flutter pub outdated` in `plant_community_mobile/` on Flutter 3.47.9,
2026-11-15.

| Package | Resolved | Latest |
|---|---|---|
| firebase_core | 4.15.2 | 5.1.0 |
| firebase_auth | 6.7.1 | 7.0.1 |
| cloud_firestore | 6.10.2 | 7.1.0 |
| firebase_messaging | 16.7.1 | 17.0.1 |
| go_router | 17.2.3 | 18.1.4 |
| flutter_local_notifications | 21.0.0 | 23.0.2 |
| flutter_secure_storage | 10.0.0 | 11.2.0 |
| cached_network_image | 3.4.1 | 4.0.7 |
| permission_handler | 12.0.1 | 13.0.2 |
| lucide_icons_flutter | 3.1.19 | 4.0.3 |
| cupertino_icons | 1.0.9 | 2.0.0 |

- The four Firebase rows share `firebase_core` and only resolve together.
  `.github/dependabot.yml` groups them into one PR (`firebase-majors`).
- `firebase_core: ^4.15.2` carries a comment: it pins the Firebase iOS SDK
  that has the Firestore eMudhra CA fix. Confirm firebase_core 5 keeps that
  fix before bumping.
- `fake_cloud_firestore` 4.4.0 (tests) must support cloud_firestore 7.
- Android: Gradle wrapper 8.14.6, AGP 8.11.2, Kotlin 2.2.21,
  google-services 4.4.2, Java target 11. Flutter 3.47.9 warns below Gradle
  9.1.0 / AGP 9.0.1 / Kotlin 2.3.20; the move was deferred on 2026-11-04
  (archived todo 693). `.github/dependabot.yml` ignores the AGP and Gradle
  wrapper majors until this todo takes them.
- Swift Package Manager is off (`enable-swift-package-manager: false`); a
  plugin major may assume it.
- Changelogs were not read for this todo.

## Recommended Action

1. Firebase set in one PR (take Dependabot's grouped PR or bump by hand).
   Sign-in, token exchange, a Firestore read and a push on a real iPhone and
   a real Android phone.
2. Plugin majors in one or two PRs: secure storage (stored JWTs must survive
   the upgrade, or the app must recover cleanly), local notifications and
   permission_handler (scheduled reminders, permission prompts), go_router
   (deep links, redirects), cached_network_image (private scan-photo cache is
   still emptied on sign-out).
3. lucide and cupertino icon majors: check for renamed or removed icons.
4. Gradle 9 / AGP 9 / Kotlin as its own PR. Remove the two `ignore` entries
   under the gradle entry in `.github/dependabot.yml` in that PR. Run
   `./gradlew --stop` first if the Gradle cache is on the external drive.
5. Ship the lot as one TestFlight build and one Android build; device-check
   once.
6. Decline anything not taken on its Dependabot PR, with the reason.

## Technical Details

- `plant_community_mobile/pubspec.yaml`, `pubspec.lock`
- `plant_community_mobile/android/settings.gradle.kts`,
  `android/gradle/wrapper/gradle-wrapper.properties`,
  `android/app/build.gradle.kts`, `android/gradle.properties`
- `plant_community_mobile/ios/Podfile` (iOS 16.0 floor)
- `plant_community_mobile/docs/patterns/firebase-auth.md`, `riverpod.md`
- `.github/dependabot.yml` (pub and gradle entries)

## Acceptance Criteria

- [ ] Each row in the table is bumped in a merged PR or declined on its
      Dependabot PR, with the PR number and reason in the Work Log.
- [ ] Gradle 9 / AGP 9 is taken (and the two `ignore` entries removed) or the
      deferral is re-recorded here with its date and reason.
- [ ] `flutter analyze` and `flutter test` pass; iOS and Android release
      builds succeed.
- [ ] Device check on iPhone and Android with date and build number recorded:
      sign-in, a scan, a push received, a reminder fired, a deep link opened,
      and a user signed in before the upgrade is still signed in after it.

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit.

### 2026-11-15 - Minors merged; four device-gated PRs open

- #1325 (merged): pub minor/patch, 14 updates, with regenerated providers
  and 19 `ref.exists(p)` -> `ref.read(p.exists)` rewrites for Riverpod 3.5.
- #1315 (merged): cupertino_icons 1.0.9 -> 2.0.0. Analyzer and tests pass;
  icons not looked at on a device.
- Open, waiting for the owner's phones: #1319 (AGP 8.13.2, Kotlin 2.4.21,
  google-services 4.5.0; CI green after moving jvmTarget to
  `kotlin { compilerOptions }`), #1314 (flutter_secure_storage 11.2.0, CI
  green), #1332 (permission_handler 13.0.2, CI green).
- #1331 (Firebase group, 6 updates): CI red. firebase_messaging 17
  deprecates `getToken` and `onTokenRefresh` in
  `lib/services/push_registration_service.dart` (use `register()` /
  `onRegistered`); that migration is not written.
- `.github/dependabot.yml` now puts every FlutterFire package in one
  `firebase` group of any update size (#1323), replacing `firebase-majors`.

### 2026-11-16 - #1331: the push "migration" is not a rename

- `register()` / `onRegistered` in firebase_messaging 17.0.1 hand out a
  Firebase installation ID (FID), not a registration token (package source,
  `lib/src/messaging.dart`). The backend stores tokens and sends with
  `messaging.Message(token=...)`; firebase-admin 7.7.0 takes a FID in a
  separate `fid=` field. Moving the app alone would register FIDs as tokens
  and every push to them would fail.
- #1331 therefore keeps `getToken` / `onTokenRefresh` (still in the package,
  deprecated) with two `// ignore: deprecated_member_use` lines in
  `lib/services/push_registration_service.dart`. `flutter analyze` clean,
  `flutter test` 1839 passed. No device check done.
- A real move needs both sides: a device row that says whether it holds a
  token or a FID, `fid=` on send, and builds already installed keep sending
  tokens. Not started; needs an owner decision before the package removes
  the token API.
- `pubspec.lock`: `test_api` back to 0.7.12 (the Flutter SDK pins it;
  Dependabot's lock had 0.7.14).
- #1331 cannot build for Android until #1319 is merged: firebase-auth
  25.0.0 is compiled with Kotlin 2.4 and main is on Kotlin 2.2
  (`:firebase_auth:compileDebugKotlin`, "metadata is 2.4.0, expected version
  is 2.2.0"). #1319 brings Kotlin 2.4.21. Merge #1319, then rebase #1331.
- firebase_messaging 17 also moves to Firebase iOS SDK 13 and Android BoM 35
  with minSdk 24 (the app is already on 24; iOS floor 16.0).

### 2026-11-17 - Implemented by the todo sweep (run 2026-11-17-1802)

- Rows already merged on main: Firebase set #1331, flutter_secure_storage #1314, permission_handler #1332, cupertino_icons #1315 (AGP 8.13.2 / Kotlin 2.4.21 came in #1319). This PR bumps the other four, as the owner decided on 2026-11-17: go_router 18.1.4, flutter_local_notifications 23.0.2, cached_network_image 4.0.7, lucide_icons_flutter 4.0.3. Nothing else moved in `pubspec.lock` except their own transitive packages (octo_image 2.1.5 among them).
- Changelogs read from the pub cache. go_router 18 and cached_network_image 4 move to `material_ui`. go_router 18 checks for material_ui's `MaterialApp`, not package:flutter's, so in this app any `builder:` route gets a `NoTransitionPage`. The app's own routes all use `pageBuilder` (`_buildPageWithTransition`), so they keep their fade. Only `errorBuilder` and the debug-only theme preview lose the Material slide, and there are no `Hero` widgets. One test, `scan_result_screen_test.dart` "a double tap retries once (L10)", relied on the animated pop. Its pushed `/scans/:id` route is now a `MaterialPage`, as in the app; the assertions are unchanged.
- flutter_local_notifications 23 needs compileSdk 37 and AGP 9.1.1 or newer. `android/app/build.gradle.kts` sets `compileSdk = 37` (Flutter 3.47.9's default is 36); targetSdk stays on the Flutter default. Lucide 4 renamed no icon the app uses, and the analyzer is clean.
- Gradle 9 / AGP 9 taken: AGP 9.1.1 and the Gradle 9.3.1 wrapper, the newest pair Flutter 3.47.9 lists as supported (`maxKnownAndSupportedGradleVersion`). The `android.builtInKotlin=false` / `android.newDsl=false` flags stay, because they are Flutter's own AGP 9 migration. The build warns that the app and five plugins (firebase_auth, firebase_core, google_sign_in_android, image_picker_android, url_launcher_android) still apply KGP, so the move to Built-in Kotlin is left for later. Both gradle `ignore` entries are gone from `.github/dependabot.yml`. CI's Java 17 meets AGP 9's floor.
- `flutter analyze` is clean, `flutter test` passes, and `flutter build appbundle --release` (signed) and `flutter build ios --release --no-codesign` both succeed. `ios/Podfile.lock` did not change. Still owed: the owner's combined iPhone + Android device check.

## Notes

Needs the owner's phones, so a sweep will stop at the device check.
