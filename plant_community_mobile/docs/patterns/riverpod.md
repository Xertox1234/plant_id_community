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
