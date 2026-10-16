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

## Build caches on the external drive (U34Bolt)

Native build caches live on the shared SSD at `/Volumes/U34Bolt` (rules: its `README.md`).
The repo, `backend/venv`, `node_modules`, `.dart_tool`, `build/` and the database stay on
the laptop.

- **Gradle**: `GRADLE_USER_HOME=/Volumes/U34Bolt/_shared/caches/gradle`, set by a
  mount-checked `~/.zshenv` block (marker `U34Bolt gradle`). It is shared with OCRecipes and
  flutter_chat. With the drive unplugged, a NEW shell falls back to `~/.gradle`, and the first
  build there downloads everything again. Android Studio started from the Dock does not read
  `.zshenv`, so it uses `~/.gradle`.
- **Xcode DerivedData** (including `flutter build ios`): `_shared/caches/DerivedData`, set by
  the laptop-wide `defaults` key. With the drive unplugged, iOS builds fail fast with "You
  don't have permission".
- **`/Volumes/U34Bolt/plant_id_community/tmp/`**: set `TMPDIR` to it for a single big build
  (for example `TMPDIR=/Volumes/U34Bolt/plant_id_community/tmp ./run_archive.sh`). Never set
  it globally.
- **Before ejecting**, run `./gradlew --stop` (from `android/`). Gradle and Kotlin daemons keep
  jars open on the drive. Also quit Docker Desktop: its disk image (shared by every project) lives at
  `_shared/docker/`. `lsof +f -- /Volumes/U34Bolt` shows what is holding it.
- Not moved on purpose: the Android SDK (no fallback when unplugged), `~/.pub-cache`
  (`.dart_tool/package_config.json` stores absolute paths into it) and `.claude/worktrees`
  (the hooks are wired to that path).

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
