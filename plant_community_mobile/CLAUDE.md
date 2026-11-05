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
- **`/Volumes/U34Bolt/plant_id_community/build/<name>`**: a worktree's (or a one-off
  build's) `build/` output, redirected by hand with a symlink,
  `plant_community_mobile/build -> /Volumes/U34Bolt/plant_id_community/build/<name>`.
  `plant_community_mobile/.gitignore` ignores the link (`/build`, no trailing slash).
  On a branch cut before that ignore, `git worktree remove` refuses the worktree because the
  link is untracked; either way it deletes only the link, never the folder. **Delete the
  `build` link first** (`rm plant_community_mobile/build`, no `-r`), then remove the
  worktree. The folder it pointed at stays behind until
  `python3 scripts/clean_build_output.py` sweeps it (todo 697): a dry run by default lists
  every entry with its size and last write, marking each one no live worktree's `build`
  link points at as an orphan; `--apply` deletes orphans older than `--min-age` days
  (default 2), never follows a symlink, and never touches an entry a live worktree uses;
  `--tmp` also reports (never deletes) `tmp/` entries older than 14 days. With the drive
  unmounted it exits 0 and does nothing. The `completing-todos` cleanup step runs it after
  `git worktree prune`. A one-off build folder that no worktree links is an orphan too:
  after 2 days without a write, the next sweep deletes it. Keep one by linking it from a
  worktree, or put it somewhere else (for example `tmp/`, which is only ever reported).
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
