# Plant ID Community Mobile App

Flutter mobile application for Plant ID Community with Firebase authentication and Django backend integration.

---

## Quick Start

### Prerequisites

- Flutter 3.35+ with Dart SDK 3.9.x
- Xcode 15+ (iOS development)
- Android Studio (Android development; Android minSdk 23)
- Firebase project configured

### Setup

```bash
# Install dependencies
flutter pub get

# Review required environment keys in .env.example.
# Pass those values to Flutter with --dart-define when running/building.

# Run code generation
flutter pub run build_runner build --delete-conflicting-outputs

# Run on iOS with local configuration values
flutter run -d ios \
  --dart-define=API_BASE_URL=http://localhost:8000/api/v1 \
  --dart-define=FIREBASE_API_KEY=your-firebase-api-key \
  --dart-define=FIREBASE_IOS_APP_ID=your-ios-app-id \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=your-sender-id \
  --dart-define=FIREBASE_PROJECT_ID=your-project-id \
  --dart-define=FIREBASE_STORAGE_BUCKET=your-storage-bucket

# Run on Android with local configuration values
flutter run -d android \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1 \
  --dart-define=FIREBASE_API_KEY=your-firebase-api-key \
  --dart-define=FIREBASE_ANDROID_APP_ID=your-android-app-id \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=your-sender-id \
  --dart-define=FIREBASE_PROJECT_ID=your-project-id \
  --dart-define=FIREBASE_STORAGE_BUCKET=your-storage-bucket

# Or pass the same values in CI/release builds with --dart-define.
```

Use `http://10.0.2.2:8000` for the Android emulator to reach a backend running
on the host machine. Use the host LAN IP for physical Android devices. iOS
simulator and local desktop/web runs can use `http://localhost:8000`.

The committed `lib/firebase_options.dart` intentionally contains no Firebase
project keys. It reads values from `--dart-define`, allowing a fresh checkout to
compile without generated secret/config files. If required Firebase values are
missing at runtime, the app shows an actionable configuration screen instead of
crashing during startup.

Android builds intentionally do not apply the Gradle Google Services plugin in
this repository because `android/app/google-services.json` is ignored and not
required when Firebase is initialized with explicit `FirebaseOptions`. Keep local
native Firebase files out of git; use `--dart-define` values for CI and release
builds.

### Validation Checklist

Run these checks from `plant_community_mobile/` in a Flutter-capable local or CI
environment before merging mobile reliability changes:

```bash
flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter analyze
flutter test
flutter test test/integration/offline_sync_test.dart
flutter test test/integration/plant_identification_flow_test.dart
flutter build apk --debug \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1 \
  --dart-define=FIREBASE_API_KEY=your-firebase-api-key \
  --dart-define=FIREBASE_ANDROID_APP_ID=your-android-app-id \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=your-sender-id \
  --dart-define=FIREBASE_PROJECT_ID=your-project-id \
  --dart-define=FIREBASE_STORAGE_BUCKET=your-storage-bucket
```

Manual iOS/Android smoke checklist:

- [ ] Missing Firebase `--dart-define` values show the configuration error screen.
- [ ] Home screen opens, settings can be opened, and theme mode persists after restart.
- [ ] Login stores JWT access/refresh tokens and logout clears them.
- [ ] An expired access token signs the user out with a clear message. Recoverable bearer-token refresh requires backend support for JSON mobile refresh responses.
- [ ] Camera permission prompt appears and denied permission is handled gracefully.
- [ ] Gallery/photo picker permission prompt appears and denied permission is handled gracefully.
- [ ] Plant identification upload shows progress, handles `429`/`5xx` retryable errors, and displays results on success.
- [ ] Android emulator uses `http://10.0.2.2:8000/api/v1`; iOS simulator uses `http://localhost:8000/api/v1`.

---

## Development Patterns

**All mobile development patterns are documented in:**

**📚 [FLUTTER_PATTERNS_CODIFIED.md](./FLUTTER_PATTERNS_CODIFIED.md)**

This comprehensive guide includes:

1. API Service Layer Patterns
2. Firebase Authentication Patterns
3. Riverpod State Management Patterns
4. Memory Leak Prevention Patterns
5. Secure Storage Patterns
6. Error Handling Patterns
7. Code Generation Patterns
8. File Organization Patterns
9. Material Design 3 Patterns
10. Null Safety Patterns

**Read this before writing any Flutter code.**

---

## Resources

### Documentation

- [Flutter Patterns (Mobile)](./FLUTTER_PATTERNS_CODIFIED.md) - **START HERE**
- [Backend Firebase Auth](../backend/docs/FIREBASE_AUTHENTICATION.md)
- [Web Patterns (TypeScript)](../web/TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md)
- [Backend Patterns](../backend/docs/patterns/)

---

**Last Updated**: November 15, 2025
**Status**: Active Development
**Flutter Version**: 3.35+
**Dart SDK**: 3.9.x
