# Riverpod 3.x Patterns

**Stack**: Riverpod 3.x with code generation (`@riverpod` annotation), Dart 3.x

---

## Provider Access Patterns

```dart
// Reactive read — rebuilds widget when state changes
final state = ref.watch(myProvider);

// One-time read inside callback — does not subscribe
ref.read(myProvider.notifier).doAction();

// Listening for side effects (navigation, toasts)
ref.listen(authProvider, (prev, next) {
  if (next.isAuthenticated) context.go('/home');
});
```

---

## Testable Dependency Injection (plain `Provider`)

Not every provider needs `@riverpod` codegen. For a simple injectable dependency
(a UUID generator, a clock, a random source), expose it as a plain `Provider<T>`
and read it via `ref` inside the consumer. This is the idiomatic way to make a
`Notifier` testable: a `Notifier` is built via the no-arg `.new` tear-off, so it
**cannot** take constructor params — inject through a provider instead, never a
field or constructor arg.

```dart
// lib/services/plant_identification_service.dart
/// Injectable UUID generator. Override in tests for deterministic IDs.
final uuidProvider = Provider<Uuid>((ref) => const Uuid());

class PlantIdentificationService extends Notifier<void> {
  // No `final Uuid _uuid` field — read it through ref instead.
  @override
  void build() {}

  Plant _toPlant(Map<String, dynamic> json) => Plant(
    id: _stringValue(json, ['id']) ?? ref.read(uuidProvider).v4(), // fallback ID
    // ...
  );
}
```

Override it in tests with `overrideWithValue` (works on plain `Provider`):

```dart
final container = ProviderContainer(
  overrides: [uuidProvider.overrideWithValue(const _MockUuid())], // deterministic
);
addTearDown(container.dispose);
```

Reserve `@riverpod` codegen for `Notifier`/`AsyncNotifier` state and async data
providers (see below). A trivial value provider as a generated part-file is
overkill — `apiServiceProvider` in `api_service.dart` follows this same plain-
`Provider` convention.

---

## Code Generation Workflow

1. Annotate the provider class with `@riverpod`
2. Add `part 'filename.g.dart';` directive to the source file
3. Run code generation:

```bash
flutter pub run build_runner build --delete-conflicting-outputs
# Or watch mode during development:
flutter pub run build_runner watch
```

Generated files (`*.g.dart`) must not be manually edited.

---

## Async Providers

```dart
@riverpod
Future<List<Plant>> userPlants(UserPlantsRef ref, String userId) async {
  final api = ref.watch(apiServiceProvider);
  return api.getPlantsByUser(userId);
}

// Consuming in widget
final plantsAsync = ref.watch(userPlantsProvider(userId));
return plantsAsync.when(
  data: (plants) => PlantList(plants: plants),
  loading: () => const LoadingIndicator(),
  error: (err, stack) => ErrorView(error: err),
);
```

---

## Disposal — Side Effects Cleanup

Register cleanup in `build()` using `ref.onDispose()`:

```dart
@riverpod
class LocationTracker extends _$LocationTracker {
  StreamSubscription<Position>? _positionSub;
  Timer? _refreshTimer;

  @override
  LocationState build() {
    _positionSub = Geolocator.getPositionStream().listen(_onPosition);
    _refreshTimer = Timer.periodic(const Duration(minutes: 5), (_) => _refresh());

    ref.onDispose(() {
      _positionSub?.cancel();
      _refreshTimer?.cancel();
    });

    return const LocationState.initial();
  }
}
```

---

## Provider Families

Use families for providers parameterised by an identifier:

```dart
@riverpod
Future<PlantDetail> plantDetail(PlantDetailRef ref, String plantId) async {
  return ref.watch(apiServiceProvider).getPlant(plantId);
}

// Usage
ref.watch(plantDetailProvider('abc-123'))
```

---

## Error Handling in Notifiers

Wrap async operations and expose typed error states:

```dart
@riverpod
class IdentificationNotifier extends _$IdentificationNotifier {
  @override
  IdentificationState build() => const IdentificationState.initial();

  Future<void> identify(File image) async {
    state = const IdentificationState.loading();
    try {
      final result = await ref.read(plantIdServiceProvider).identify(image);
      state = IdentificationState.success(result);
    } on ApiException catch (e) {
      state = IdentificationState.error(e.message);
    }
  }
}
```

## Idempotent Write Actions

Backend write endpoints that accept an `Idempotency-Key` (forum create/reply/
edit/react/report) dedupe by `(scope, user, sha256(key), payload-fingerprint)`:
a retry with the **same** key + **same** payload replays the original response
(same status, e.g. `201`); the same key with a **different** payload returns a
permanent `422` for the 24h TTL. So a mobile retry must reuse the key, but an
edit-then-retry must NOT — hold one key per compose action and rotate it when
the content changes:

```dart
class ForumComposerController {
  ForumComposerController({required ForumApi api, String? idempotencyKey})
    : _api = api, _key = idempotencyKey ?? const Uuid().v4();
  final ForumApi _api;
  String _key;
  String? _lastFingerprint;
  String get idempotencyKey => _key;

  void _refreshKeyForContent(String fingerprint) {
    if (_lastFingerprint != null && _lastFingerprint != fingerprint) {
      _key = const Uuid().v4();          // content changed → genuinely new attempt
    }
    _lastFingerprint = fingerprint;
  }

  Future<CreateReplyResult> submitReply({required int topicId, required String body}) {
    _refreshKeyForContent('reply|$topicId|${body.trim()}');
    return _api.createReply(topicId: topicId, body: buildParagraphBody(body),
        idempotencyKey: _key);
  }
}
```

Handle `409` (a twin still in flight → back off and retry the same key) and
`422` (fell through the rotation → surface a fresh-key retry) at the call site.
Reference: `lib/features/forum/services/forum_composer_controller.dart`. Note
the web client sends no key at all — do not copy that; the backend is built for
mobile retries. See `docs/rules/flutter.md`.

## Unit-testing an `@riverpod` notifier (todo 288)

Two obstacles bite every notifier harness in this repo. Neither needs a
production seam.

**1. An autoDispose provider must be held, or it rebuilds under you.**

`container.read(someProvider)` on an autoDispose provider builds the notifier
and immediately tears it down, so the *next* read builds a SECOND one. If
`build()` starts async work (`AuthService` fires an unawaited token exchange
when a user is already signed in), that work lands on a disposed `Ref` and
throws `Cannot use Ref after dispose` — from a line the test never touched.
Hold a subscription for the harness's lifetime instead:

```dart
_subscription = container.listen(
  authServiceProvider,
  (_, _) {},
  fireImmediately: true,
);
// ...and in dispose(): _subscription.close(); container.dispose();
```

One notifier instance, as in the app. Also drain `build()`'s fire-and-forget
work with `await pumpEventQueue()` before teardown, or it lands post-dispose.

**2. `flutter_secure_storage` has a built-in in-memory platform.**

A notifier that reads or writes tokens throws `MissingPluginException` under
`flutter test`. Do not add an injection seam for it and do not hand-roll a
method-channel mock — call the package's own `@visibleForTesting` static in
`setUp`:

```dart
setUp(() => FlutterSecureStorage.setMockInitialValues({}));
```

It installs `TestFlutterSecureStoragePlatform` (shipped in
flutter_secure_storage 10.x). No extra dependency: reaching for
`FlutterSecureStoragePlatform.instance` directly would require importing the
transitive `flutter_secure_storage_platform_interface` package, which trips
`depend_on_referenced_packages`.

**Assert ordering across collaborators with one shared log.** Give every fake
the same `List<String> events` and append to it. That is what makes a
cross-object constraint testable — e.g. `clearOnLogout` must run BEFORE the
Firebase sign-out that invalidates the JWT its PATCH needs:

```dart
expect(harness.events, containsAllInOrder(['clearOnLogout', 'firebase.signOut']));
```

Reference: `test/services/auth_service_test.dart`,
`test/services/push_registration_service_test.dart`.
