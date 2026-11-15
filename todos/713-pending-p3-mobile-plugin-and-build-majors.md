---
status: pending
priority: p3
issue_id: "713"
tags: [mobile, flutter, firebase, android, dependencies, dependabot, upgrade]
dependencies: []
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

## Notes

Needs the owner's phones, so a sweep will stop at the device check.
