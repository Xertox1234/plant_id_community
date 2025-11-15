# Plant ID Community Mobile App

Flutter mobile application for Plant ID Community with Firebase authentication and Django backend integration.

---

## Quick Start

### Prerequisites
- Flutter 3.27+ with Dart SDK 3.9.x
- Xcode 15+ (iOS development)
- Android Studio (Android development)
- Firebase project configured

### Setup

```bash
# Install dependencies
flutter pub get

# Configure environment
cp .env.example .env
# Edit .env with your API endpoints

# Run code generation
flutter pub run build_runner build --delete-conflicting-outputs

# Run on iOS
flutter run -d ios

# Run on Android
flutter run -d android
```

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
**Flutter Version**: 3.27
**Dart SDK**: 3.9.x
