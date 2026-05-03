---
status: blocked
priority: p1
issue_id: "050"
tags: [mobile, flutter, firebase, build, onboarding, production-blocker]
dependencies: []
---

# Make Flutter App Buildable From a Fresh Checkout

## Problem

The Flutter app previously imported generated Firebase configuration while `lib/firebase_options.dart` was not present in the working tree. A fresh checkout could not compile until a developer manually regenerated Firebase options. The file now exists and reads non-secret values from `--dart-define`; final toolchain validation is still pending.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- `plant_community_mobile/lib/main.dart` imports `firebase_options.dart`.
- `plant_community_mobile/lib/firebase_options.dart` was not found in the workspace during the initial assessment; it has since been added with environment-based configuration.
- `plant_community_mobile/.gitignore` excludes generated Firebase options files.
- Historical finding: the app expected a `.env` asset in `pubspec.yaml`, but `.env` files are intentionally ignored. The current implementation uses `--dart-define` instead.

## Recommended Action

1. Decide whether `firebase_options.dart` should be committed with non-secret Firebase client config or generated locally.
2. If generated locally, add a clear setup script and README instructions.
3. Ensure `.env.example` contains all required keys and the app fails with a helpful message if required `--dart-define` values are missing.
4. Verify `flutter pub get`, code generation, `flutter analyze`, and a debug build from a clean checkout.

## Technical Details

Important files:

- `plant_community_mobile/lib/main.dart`
- `plant_community_mobile/pubspec.yaml`
- `plant_community_mobile/.gitignore`
- `plant_community_mobile/.env.example`

Potential setup command:

```bash
cd plant_community_mobile
flutterfire configure
flutter pub run build_runner build --delete-conflicting-outputs
```

## Acceptance Criteria

- [x] Fresh checkout setup steps are documented and accurate.
- [x] Missing `.env` and Firebase config failures are user-friendly.
- [ ] `flutter pub get` passes on the intended Flutter SDK version.
- [ ] `flutter analyze` passes or has a documented baseline.
- [ ] A clean debug build runs for at least one supported target.

## Work Log

### 2026-05-01 - Codebase Assessment

- Identified as P1 because a fresh mobile checkout appears non-buildable without undocumented generated files.

### 2026-05-01 - Fresh Checkout Configuration Improvements

- Added a committed `lib/firebase_options.dart` that contains no Firebase project keys and reads required values from `--dart-define`.
- Removed the ignored `.env` file from required Flutter assets so fresh checkouts are not blocked by a missing asset file.
- Added a startup configuration error screen for missing Firebase values instead of crashing during initialization.
- Updated mobile setup documentation and `.env.example` with required Firebase keys.
- Updated `apiServiceProvider` to honor `API_BASE_URL` from `--dart-define`, use a debug-only localhost fallback, and fail fast in release builds when the value is missing.
- Could not run `flutter pub get`, `flutter analyze`, or a debug build in the current GitHub cloud workspace because Flutter/Dart are not installed. Validation is intentionally deferred until a Flutter-capable local or CI environment is available.

### 2026-05-01 - Fresh Checkout Build Follow-up

- Added missing mobile `plant_identification_service.dart` and `firebase_storage_service.dart` imports required by `CameraScreen` and integration tests.
- Removed the Android Google Services Gradle plugin from the app build because the required `google-services.json` file is intentionally ignored and Firebase initialization now uses explicit `FirebaseOptions`.
- Updated API service tests to avoid loading ignored `.env` files.
- Added Mobile Fresh Checkout CI to run `flutter pub get`, code generation, `flutter analyze`, `flutter test`, and a debug Android build with placeholder `--dart-define` values in a Flutter-capable environment.
- Addressed review findings by aligning Android minSdk with FlutterFire, validating image upload size/type, cleaning up Firebase uploads when backend identification fails, and making generated-code CI fail on uncommitted changes.
- Added targeted tests for Firebase upload validation and cleanup of uploaded images when plant identification fails after upload.
