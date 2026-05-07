# Mobile — Flutter / Firebase / Riverpod

## Commands

```bash
cd plant_community_mobile

flutter run -d ios       # iOS simulator
flutter run -d android   # Android emulator
flutter run -d macos     # macOS desktop

flutter test             # unit + widget tests
flutter test --coverage  # with coverage report

# Regenerate Riverpod providers + go_router routes after any annotation change
flutter pub run build_runner build --delete-conflicting-outputs

# Security scan (run before commits)
cd ..
source backend/venv/bin/activate
python scripts/check_flutter_security.py
```

## Conventions

- **Riverpod 3.x** — use `Notifier` class with `@riverpod` annotation. Do not use `StateNotifier`.
- **go_router** — set `debugLogDiagnostics: kDebugMode`, not `true` (would log in production).
- **Material 3** — use `CardThemeData` (not `CardTheme`), `.withValues(alpha:)` (not `.withOpacity()`).
- **Token storage** — always `flutter_secure_storage`. Never `SharedPreferences` (not encrypted).
- **Dark mode** — check `Theme.of(context).brightness == Brightness.dark` for conditional styling.

## Gotcha: StreamSubscription memory leaks

Any `StreamSubscription` opened in a Riverpod provider **must** be cancelled in `ref.onDispose()`:

```dart
StreamSubscription<User?>? _authSub;

@override
AuthState build() {
  _authSub = _firebaseAuth.authStateChanges().listen((user) async {
    if (user != null) await _exchangeToken(user);
  });
  ref.onDispose(() => _authSub?.cancel());
  return AuthState(firebaseUser: _firebaseAuth.currentUser);
}
```

See `docs/patterns/firebase-auth.md` for the full Firebase → Django JWT exchange pattern.
