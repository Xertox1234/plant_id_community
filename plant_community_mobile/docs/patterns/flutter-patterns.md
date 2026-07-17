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

## Epoch-Guarded Async Lifecycle Services

**Context** (todo 253 slice 6, races confirmed empirically in review): a
service whose async work must stop at sign-out (`PushRegistrationService`)
cannot rely on cancelling subscriptions alone — a continuation already parked
on an `await` (permission dialog, `getToken()`, an in-flight PATCH) resumes
AFTER the cleanup ran and re-registers state for a signed-out session.

**The pattern** (mirrors `AuthService._authGeneration`):

```dart
int _epoch = 0;

Future<void> syncAfterLogin() async {
  final epoch = _epoch;                      // capture at entry
  final settings = await messaging.requestPermission();
  if (epoch != _epoch) return;               // re-check after EVERY await…
  await _refreshSubscription?.cancel();
  if (epoch != _epoch) return;               // …including cancel() itself
  // attach listeners / register …
}

void detach() {
  _epoch++;                                  // invalidates all parked work
  _refreshSubscription?.cancel();
  _refreshSubscription = null;
  _lastSyncedToken = null;                   // full local reset — the next
}                                            // account must not be deduped
                                             // against the previous one
```

Rules that fell out of the confirmed bugs:

- **Re-check after EVERY await** — the one that was missed in review was
  `subscription.cancel()`, which is an async gap like any other.
- **`detach()` is a FULL local reset** (epoch, subscriptions, markers). A
  session-expiry sign-out runs only `detach()`, and the next user on the same
  device must not inherit dedupe markers.
- **Attach healing listeners BEFORE the fallible first attempt** — the
  `onTokenRefresh` listener goes up before `getToken()`/first PATCH, so a
  null token (iOS APNS warm-up) or transient failure self-heals on the next
  event instead of silencing the whole session. Always pass `onError:` — a
  platform error event on the stream is otherwise an unhandled zone error.
- **Interceptor side effects are suppressed per-REQUEST, not per-flag.** A
  boolean flag around `await patch(...).timeout(3s)` fails: the timeout
  abandons the Future but Dio keeps the request alive (~receiveTimeout), and
  its late 401 fires the session-expired handler after the flag reset. Put
  the opt-out on the request (`Options(extra: {ApiService.skipSessionExpiryKey:
  true})`) and check `requestOptions.extra` in the interceptor.

Reference: `lib/services/push_registration_service.dart` (+ its unit tests:
epoch-parked-sync, listener-survives-failed-PATCH, detach-clears-marker).
