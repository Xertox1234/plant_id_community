---
status: completed
priority: p3
issue_id: "713"
tags: [mobile, flutter, firebase, android, dependencies, dependabot, upgrade]
dependencies: []
triage: ready
triaged: 2026-11-22
owner_decision: "Owner: device check done on build 28 (TestFlight 28 / Android versionCode 28) (2026-11-22); criterion 3 confirmed by the owner (2026-11-22): Device check done (owner answered 'Done' on 2026-11-22; build 28: TestFlight 28 and Android versionCode 28)"
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

- [x] Each row in the table is bumped in a merged PR or declined on its
      Dependabot PR, with the PR number and reason in the Work Log.
- [x] Gradle 9 / AGP 9 is taken (and the two `ignore` entries removed) or the
      deferral is re-recorded here with its date and reason.
- [x] `flutter analyze` and `flutter test` pass; iOS and Android release
      builds succeed.
- [x] Device check on iPhone and Android with date and build number recorded:
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

### 2026-11-17 - Review round 1: non-blocking findings (PR #1359, hand-landed)

Two fresh-context reviewers (correctness, Flutter checklist); no blocking findings.

- **Recorded.** go_router 18's `isMaterialApp` looks for material_ui's `MaterialApp`, and this app uses package:flutter's `MaterialApp.router`, so every `builder:` route now gets a `NoTransitionPage`. In the app that is the `StatefulShellRoute.indexedStack` shell page, `errorBuilder` and the debug-only ThemePreview route. Every leaf route uses `pageBuilder: _buildPageWithTransition`, so the visible transitions do not change; there are no Hero widgets and no route-type checks in `lib/`. Worth watching in the device check.
- **Fixed.** `.github/workflows/mobile-ci.yml` comments still described the old Gradle 8.12 wrapper; now they name Gradle 9.3.1 / AGP 9.1.1 and the JDK 17 floor.
- **Declined.** `flutter_local_notifications` has no Dart call site in `lib/` (native registration only). Dropping it would also drop the compileSdk 37 need, but removing a dependency is out of scope for a version-bump PR; worth a look on its own.
- **Declined.** `compileSdk = 37` is hardcoded (commented with its revert condition), and `android.builtInKotlin=false` / `android.newDsl=false` are AGP 9 transitional opt-outs removed in AGP 10. Both are a deferred migration for the next AGP major, not a defect now.

### 2026-11-22 - Implemented by the todo sweep (run 2026-11-22-1957)

- No code change: every row is already on main. Row by row, with its merged PR: firebase_core 5.1.0, firebase_auth 7.0.1, cloud_firestore 7.1.0 and firebase_messaging 17.0.1 in #1331 (the Firebase group); flutter_secure_storage 11.2.0 in #1314; permission_handler 13.0.2 in #1332; cupertino_icons 2.0.0 in #1315; go_router 18.1.4, flutter_local_notifications 23.0.2, cached_network_image 4.0.7 and lucide_icons_flutter 4.0.3 in #1359. None was declined. `pubspec.lock` on main resolves each to its Latest column.
- Gradle 9 / AGP 9 taken in #1359: Gradle 9.3.1 wrapper, AGP 9.1.1, Kotlin 2.4.21; the gradle entry in `.github/dependabot.yml` has no `ignore` entries left.
- Re-ran `flutter analyze`, `flutter test`, `flutter build appbundle --release` (signed) and `flutter build ios --release --no-codesign` on Flutter 3.47.9 from this branch; build output went to the external drive.
- Device check: the owner checked build 28 (TestFlight 28 and Android versionCode 28) on iPhone and Android and answered "Done" on 2026-11-22.

### 2026-11-22 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `bash -c 'W=.; for p in firebase_core firebase_auth cloud_firestore firebase_messaging go_router flutter_local_notifications flutter_secure_storage cached_network_image permission_handler lucide_icons_flutter cupertino_icons; do awk -v p="  $p:" "\$0==p{f=1;next} f&&/version:/{print p, \$2; exit}" $W/plant_community_mobile/pubspec.lock; done; /usr/bin/git -C $W log origin/main --oneline -E --grep="#(1331|1314|1332|1315|1359)\)"; grep -n -E "#(1331|1314|1332|1315|1359)" $W/todos/713-pending-p3-mobile-plugin-and-build-majors.md'` — evidence `.sweep-evidence/g3/713-ac0.txt` (not committed), last lines:

  ```text
  139:  is 2.2.0"). #1319 brings Kotlin 2.4.21. Merge #1319, then rebase #1331.
  145:- Rows already merged on main: Firebase set #1331, flutter_secure_storage #1314, permission_handler #1332, cupertino_icons #1315 (AGP 8.13.2 / Kotlin 2.4.21 came in #1319). This PR bumps the other four, as the owner decided on 2026-11-17: go_router 18.1.4, flutter_local_notifications 23.0.2, cached_network_image 4.0.7, lucide_icons_flutter 4.0.3. Nothing else moved in `pubspec.lock` except their own transitive packages (octo_image 2.1.5 among them).
  151:### 2026-11-17 - Review round 1: non-blocking findings (PR #1359, hand-landed)
  162:- No code change: every row is already on main. Row by row, with its merged PR: firebase_core 5.1.0, firebase_auth 7.0.1, cloud_firestore 7.1.0 and firebase_messaging 17.0.1 in #1331 (the Firebase group); flutter_secure_storage 11.2.0 in #1314; permission_handler 13.0.2 in #1332; cupertino_icons 2.0.0 in #1315; go_router 18.1.4, flutter_local_notifications 23.0.2, cached_network_image 4.0.7 and lucide_icons_flutter 4.0.3 in #1359. None was declined. `pubspec.lock` on main resolves each to its Latest column.
  163:- Gradle 9 / AGP 9 taken in #1359: Gradle 9.3.1 wrapper, AGP 9.1.1, Kotlin 2.4.21; the gradle entry in `.github/dependabot.yml` has no `ignore` entries left.
  ```

- AC 2: `bash -c 'W=.; grep -n distributionUrl $W/plant_community_mobile/android/gradle/wrapper/gradle-wrapper.properties; grep -n -E "com.android.application|kotlin.android" $W/plant_community_mobile/android/settings.gradle.kts; echo "--- gradle entry in dependabot.yml:"; awk "/package-ecosystem: \"gradle\"/{f=1} f&&/package-ecosystem: \"github-actions\"/{exit} f" $W/.github/dependabot.yml; echo "ignore entries in gradle block: $(awk "/package-ecosystem: \"gradle\"/{f=1} f&&/package-ecosystem: \"github-actions\"/{exit} f" $W/.github/dependabot.yml | grep -c ignore)"'` — evidence `.sweep-evidence/g3/713-ac1.txt` (not committed), last lines:

  ```text
          patterns: ["*"]
          update-types: ["minor", "patch"]

    # Workflow actions: one PR for all of them, majors included.
  ignore entries in gradle block: 0
  ```

- AC 3: `bash -c 'cd plant_community_mobile && export TMPDIR=/Volumes/U34Bolt/plant_id_community/tmp && flutter analyze && flutter test && flutter build appbundle --release && flutter build ios --release --no-codesign && echo AC2_ALL_PASSED'` — evidence `.sweep-evidence/g3/713-ac2.txt` (not committed), last lines:

  ```text
  Running pod install...                                             18.3s
  Running Xcode build...
  Xcode build done.                                           319.4s
  ✓ Built build/ios/iphoneos/Runner.app (62.0MB)
  AC2_ALL_PASSED
  ```

### 2026-11-22 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-22-1957)

- AC 4: confirmed by the owner on 2026-11-22: "Device check done (owner answered 'Done' on 2026-11-22; build 28: TestFlight 28 and Android versionCode 28)" (`state.py confirm`; no command or evidence)

### 2026-11-22 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

Needs the owner's phones, so a sweep will stop at the device check.
