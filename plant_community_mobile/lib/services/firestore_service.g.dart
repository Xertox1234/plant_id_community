// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'firestore_service.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Firestore service for offline data persistence and cross-device sync
///
/// This service provides:
/// - Offline data persistence (automatic with Firestore)
/// - Real-time synchronization across devices
/// - User-scoped data isolation
///
/// Collections structure:
/// ```
/// /users/{userId}/
///   ├─ identified_plants/
///   │   ├─ {plantId}/
///   │   │   ├─ id: string
///   │   │   ├─ name: string
///   │   │   ├─ scientificName: string
///   │   │   ├─ imageUrl: string
///   │   │   ├─ timestamp: timestamp
///   │   │   └─ care: array
/// ```
///
/// Usage:
/// ```dart
/// final firestoreService = ref.read(firestoreServiceProvider);
///
/// // Save plant (syncs automatically)
/// await firestoreService.savePlant('userId', plant);
///
/// // Stream plants (works offline with cached data)
/// ref.watch(plantsStreamProvider('userId')).when(
///   data: (plants) => PlantsList(plants: plants),
///   loading: () => LoadingIndicator(),
///   error: (error, stack) => ErrorWidget(error),
/// );
/// ```

@ProviderFor(FirestoreService)
const firestoreServiceProvider = FirestoreServiceProvider._();

/// Firestore service for offline data persistence and cross-device sync
///
/// This service provides:
/// - Offline data persistence (automatic with Firestore)
/// - Real-time synchronization across devices
/// - User-scoped data isolation
///
/// Collections structure:
/// ```
/// /users/{userId}/
///   ├─ identified_plants/
///   │   ├─ {plantId}/
///   │   │   ├─ id: string
///   │   │   ├─ name: string
///   │   │   ├─ scientificName: string
///   │   │   ├─ imageUrl: string
///   │   │   ├─ timestamp: timestamp
///   │   │   └─ care: array
/// ```
///
/// Usage:
/// ```dart
/// final firestoreService = ref.read(firestoreServiceProvider);
///
/// // Save plant (syncs automatically)
/// await firestoreService.savePlant('userId', plant);
///
/// // Stream plants (works offline with cached data)
/// ref.watch(plantsStreamProvider('userId')).when(
///   data: (plants) => PlantsList(plants: plants),
///   loading: () => LoadingIndicator(),
///   error: (error, stack) => ErrorWidget(error),
/// );
/// ```
final class FirestoreServiceProvider
    extends $NotifierProvider<FirestoreService, void> {
  /// Firestore service for offline data persistence and cross-device sync
  ///
  /// This service provides:
  /// - Offline data persistence (automatic with Firestore)
  /// - Real-time synchronization across devices
  /// - User-scoped data isolation
  ///
  /// Collections structure:
  /// ```
  /// /users/{userId}/
  ///   ├─ identified_plants/
  ///   │   ├─ {plantId}/
  ///   │   │   ├─ id: string
  ///   │   │   ├─ name: string
  ///   │   │   ├─ scientificName: string
  ///   │   │   ├─ imageUrl: string
  ///   │   │   ├─ timestamp: timestamp
  ///   │   │   └─ care: array
  /// ```
  ///
  /// Usage:
  /// ```dart
  /// final firestoreService = ref.read(firestoreServiceProvider);
  ///
  /// // Save plant (syncs automatically)
  /// await firestoreService.savePlant('userId', plant);
  ///
  /// // Stream plants (works offline with cached data)
  /// ref.watch(plantsStreamProvider('userId')).when(
  ///   data: (plants) => PlantsList(plants: plants),
  ///   loading: () => LoadingIndicator(),
  ///   error: (error, stack) => ErrorWidget(error),
  /// );
  /// ```
  const FirestoreServiceProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'firestoreServiceProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$firestoreServiceHash();

  @$internal
  @override
  FirestoreService create() => FirestoreService();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(void value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<void>(value),
    );
  }
}

String _$firestoreServiceHash() => r'c7a82a21052f533f9286079176604272b0e1173c';

/// Firestore service for offline data persistence and cross-device sync
///
/// This service provides:
/// - Offline data persistence (automatic with Firestore)
/// - Real-time synchronization across devices
/// - User-scoped data isolation
///
/// Collections structure:
/// ```
/// /users/{userId}/
///   ├─ identified_plants/
///   │   ├─ {plantId}/
///   │   │   ├─ id: string
///   │   │   ├─ name: string
///   │   │   ├─ scientificName: string
///   │   │   ├─ imageUrl: string
///   │   │   ├─ timestamp: timestamp
///   │   │   └─ care: array
/// ```
///
/// Usage:
/// ```dart
/// final firestoreService = ref.read(firestoreServiceProvider);
///
/// // Save plant (syncs automatically)
/// await firestoreService.savePlant('userId', plant);
///
/// // Stream plants (works offline with cached data)
/// ref.watch(plantsStreamProvider('userId')).when(
///   data: (plants) => PlantsList(plants: plants),
///   loading: () => LoadingIndicator(),
///   error: (error, stack) => ErrorWidget(error),
/// );
/// ```

abstract class _$FirestoreService extends $Notifier<void> {
  void build();
  @$mustCallSuper
  @override
  void runBuild() {
    build();
    final ref = this.ref as $Ref<void, void>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<void, void>,
              void,
              Object?,
              Object?
            >;
    element.handleValue(ref, null);
  }
}

/// Provider for plants stream by user ID
///
/// This provider automatically handles offline/online transitions

@ProviderFor(plantsStream)
const plantsStreamProvider = PlantsStreamFamily._();

/// Provider for plants stream by user ID
///
/// This provider automatically handles offline/online transitions

final class PlantsStreamProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<Plant>>,
          List<Plant>,
          Stream<List<Plant>>
        >
    with $FutureModifier<List<Plant>>, $StreamProvider<List<Plant>> {
  /// Provider for plants stream by user ID
  ///
  /// This provider automatically handles offline/online transitions
  const PlantsStreamProvider._({
    required PlantsStreamFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'plantsStreamProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$plantsStreamHash();

  @override
  String toString() {
    return r'plantsStreamProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $StreamProviderElement<List<Plant>> $createElement(
    $ProviderPointer pointer,
  ) => $StreamProviderElement(pointer);

  @override
  Stream<List<Plant>> create(Ref ref) {
    final argument = this.argument as String;
    return plantsStream(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is PlantsStreamProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$plantsStreamHash() => r'953c4ca087d53060c50f5acab4ab2ef241240251';

/// Provider for plants stream by user ID
///
/// This provider automatically handles offline/online transitions

final class PlantsStreamFamily extends $Family
    with $FunctionalFamilyOverride<Stream<List<Plant>>, String> {
  const PlantsStreamFamily._()
    : super(
        retry: null,
        name: r'plantsStreamProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Provider for plants stream by user ID
  ///
  /// This provider automatically handles offline/online transitions

  PlantsStreamProvider call(String userId) =>
      PlantsStreamProvider._(argument: userId, from: this);

  @override
  String toString() => r'plantsStreamProvider';
}
