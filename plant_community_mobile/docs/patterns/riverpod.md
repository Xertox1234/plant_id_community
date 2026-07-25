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
