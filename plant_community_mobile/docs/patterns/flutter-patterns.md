# Flutter/Dart Patterns

**Stack**: Flutter 3.x, Dart 3.x, Riverpod 3.x (code generation), go_router 17.0.0, Material Design 3

---

## Memory Leak Prevention — StreamSubscription Disposal

Every `StreamSubscription` declared in a Riverpod provider MUST be cancelled in `ref.onDispose()`.

```dart
@riverpod
class PlantDataNotifier extends _$PlantDataNotifier {
  StreamSubscription<QuerySnapshot>? _firestoreSubscription;

  @override
  PlantDataState build() {
    _firestoreSubscription = _firestore
        .collection('plants')
        .snapshots()
        .listen(_onSnapshot);

    // REQUIRED — missing this causes memory leaks across hot restarts
    ref.onDispose(() {
      _firestoreSubscription?.cancel();
    });

    return const PlantDataState.initial();
  }
}
```

---

## Riverpod 3.x — Notifier Pattern

Use `Notifier` class with `@riverpod` annotation. Do NOT use deprecated `StateNotifier`.

```dart
// ✅ Riverpod 3.x — code-generated
@riverpod
class AuthNotifier extends _$AuthNotifier {
  @override
  AuthState build() => const AuthState.initial();

  Future<void> signIn(String email, String password) async { ... }
}

// ❌ Deprecated
class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState.initial());
}
```

After adding/modifying `@riverpod` providers, regenerate with:
```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

---

## go_router 17.0.0

Router debug logging must use `kDebugMode`, not hardcoded `true`:

```dart
GoRouter(
  debugLogDiagnostics: kDebugMode,
  ...
)
```

---

## Material Design 3 — Correct APIs

```dart
// ✅ Material 3
CardTheme(data: CardThemeData(...))
color.withValues(alpha: 0.5)

// ❌ Deprecated
CardTheme(...)
color.withOpacity(0.5)
```

Dark mode check:
```dart
if (Theme.of(context).brightness == Brightness.dark) { ... }
```

---

## Null Safety

Prefer `?.` and `??` over `!` null-force-unwrap on values that could legitimately be null:

```dart
// ✅
final name = user?.displayName ?? 'Anonymous';

// ❌ Crash risk
final name = user!.displayName;
```

---

## Image Handling

Use `CachedNetworkImage` for network images — never `Image.network`:

```dart
CachedNetworkImage(
  imageUrl: plant.imageUrl,
  placeholder: (context, url) => const CircularProgressIndicator(),
  errorWidget: (context, url, error) => const Icon(Icons.error),
)
```

---

## Minimum Tap Target

Minimum interactive element size: 48×48 dp (Material 3 specification).

```dart
SizedBox(
  width: 48,
  height: 48,
  child: IconButton(onPressed: ..., icon: ...),
)
```
