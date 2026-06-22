import 'package:dio/dio.dart';
import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

/// Integration tests for offline persistence and data synchronization.
///
/// The Firestore tests run the REAL [FirestoreService] against an in-memory
/// [FakeFirebaseFirestore] (injected via [firebaseFirestoreProvider]), so the
/// actual save / read / parse / ordering / streaming logic is exercised — not a
/// hand-rolled mock of the service.
///
/// On the offline→online *transition*: Firestore performs reconnect sync
/// natively. A `set()` issued while offline lands in the SDK's local write queue
/// and flushes to the server automatically when connectivity returns; the local
/// cache write is immediate, so the data is readable the whole time. That
/// queue-flush round-trip is internal to the SDK and not reproducible in-process
/// (the fake is always an in-memory store with no network), so these tests cover
/// the contract the UI actually depends on: **a saved plant is immediately and
/// continuously readable from the local store**. A literal network round-trip
/// would require the Firebase emulator.
void main() {
  group('Offline persistence (real FirestoreService + fake Firestore)', () {
    late FakeFirebaseFirestore fake;
    late ProviderContainer container;
    late FirestoreService firestore;

    const userId = 'test-user-id';

    setUp(() {
      fake = FakeFirebaseFirestore();
      container = ProviderContainer(
        overrides: [firebaseFirestoreProvider.overrideWithValue(fake)],
      );
      firestore = container.read(firestoreServiceProvider.notifier);
    });

    tearDown(() => container.dispose());

    test('a saved plant is immediately readable from the local store', () async {
      final plant = Plant(
        id: 'offline-1',
        name: 'Monstera Deliciosa',
        scientificName: 'Monstera deliciosa',
        description: 'Swiss Cheese Plant',
        care: const ['Water weekly', 'Bright indirect light'],
        imageUrl: 'https://example.com/monstera.jpg',
        timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
      );

      await firestore.savePlant(userId, plant);

      final snapshot = await firestore.getPlantsStream(userId).first;
      expect(snapshot.plants, hasLength(1));
      expect(snapshot.plants.first.id, 'offline-1');
      expect(snapshot.plants.first.name, 'Monstera Deliciosa');
    });

    test('multiple plants saved while offline all read back, newest first', () async {
      await firestore.savePlant(
        userId,
        _plant('1', DateTime.parse('2026-01-01T00:00:00Z')),
      );
      await firestore.savePlant(
        userId,
        _plant('2', DateTime.parse('2026-02-01T00:00:00Z')),
      );

      final snapshot = await firestore.getPlantsStream(userId).first;
      expect(snapshot.plants.map((p) => p.id).toList(), ['2', '1']);
    });

    test('data persisted before reconnect is still present afterward', () async {
      // Stand-in for the offline→online transition: the write lands in the local
      // store first (offline) and remains readable after the SDK would have
      // synced it (online). With no network in the fake, "before" and "after"
      // read from the same persisted store — exactly the continuity guarantee
      // the collection UI relies on across a reconnect.
      await firestore.savePlant(
        userId,
        _plant('transition', DateTime.parse('2026-01-01T00:00:00Z')),
      );

      final before = await firestore.getPlantsStream(userId).first;
      expect(before.plants, hasLength(1));

      final after = await firestore.getPlantsStream(userId).first;
      expect(after.plants, hasLength(1));
      expect(after.plants.first.id, 'transition');
    });

    test('the stream reflects a plant saved after subscribing', () async {
      // Real-time reactivity: the collection screen watches this stream, so a
      // save must produce a fresh emission carrying the new plant. Resolves
      // deterministically on the matching emission rather than on a fixed delay.
      final stream = firestore.getPlantsStream(userId);
      await firestore.savePlant(
        userId,
        _plant('live', DateTime.parse('2026-01-01T00:00:00Z')),
      );

      final emission = await stream.firstWhere(
        (s) => s.plants.any((p) => p.id == 'live'),
      );

      expect(emission.plants.map((p) => p.id), contains('live'));
    });
  });

  group('API offline/online behavior (mocked ApiService)', () {
    test('offline API calls throw ApiException', () async {
      final container = ProviderContainer(
        overrides: [apiServiceProvider.overrideWith((ref) => OfflineApiService())],
      );
      addTearDown(container.dispose);
      final api = container.read(apiServiceProvider);

      await expectLater(
        () => api.uploadFile(
          '/plant-identification/identify/',
          filePath: '/path/to/image.jpg',
          fieldName: 'image',
        ),
        throwsA(isA<ApiException>()),
      );
    });

    test('online API upload returns identification data', () async {
      final container = ProviderContainer(
        overrides: [apiServiceProvider.overrideWith((ref) => OnlineApiService())],
      );
      addTearDown(container.dispose);
      final api = container.read(apiServiceProvider);

      final response = await api.uploadFile(
        '/plant-identification/identify/',
        filePath: '/path/to/image.jpg',
        fieldName: 'image',
      );

      expect(response.statusCode, 200);
      expect(response.data, isA<Map<String, dynamic>>());
      expect(response.data['name'], isNotNull);
    });
  });
}

Plant _plant(String id, DateTime timestamp) => Plant(
  id: id,
  name: 'Plant $id',
  scientificName: 'Plantus $id',
  description: 'desc',
  care: const [],
  timestamp: timestamp,
);

/// Mock API service that simulates offline state (no connectivity).
class OfflineApiService extends ApiService {
  OfflineApiService() : super(baseUrl: 'http://localhost:8000/api/v1');

  @override
  String get baseUrl => 'http://localhost:8000/api/v1';

  @override
  void setAuthToken(String? token) {
    // No-op for mock
  }

  @override
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    await Future.delayed(const Duration(milliseconds: 100));
    throw ApiException('No internet connection');
  }

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 100));
    throw ApiException('No internet connection');
  }

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 100));
    throw ApiException('No internet connection');
  }

  @override
  Future<Response> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 100));
    throw ApiException('No internet connection');
  }

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 100));
    throw ApiException('No internet connection');
  }

  @override
  Future<Response> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 100));
    throw ApiException('No internet connection');
  }
}

/// Mock API service that simulates online state (successful connectivity).
class OnlineApiService extends ApiService {
  OnlineApiService() : super(baseUrl: 'http://localhost:8000/api/v1');

  @override
  String get baseUrl => 'http://localhost:8000/api/v1';

  @override
  void setAuthToken(String? token) {
    // No-op for mock
  }

  @override
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    await Future.delayed(const Duration(milliseconds: 500));

    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {
        'name': 'Test Plant',
        'scientific_name': 'Testus plantus',
        'description': 'A test plant identified online',
        'care_instructions': ['Water regularly'],
        'confidence': 0.85,
        'source': 'plant_id',
        'cached': false,
      },
    );
  }

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 200));

    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {'success': true},
    );
  }

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 200));

    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 201,
      data: {'success': true},
    );
  }

  @override
  Future<Response> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 200));

    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {'success': true},
    );
  }

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 200));

    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {'success': true},
    );
  }

  @override
  Future<Response> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    await Future.delayed(const Duration(milliseconds: 200));

    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 204,
      data: null,
    );
  }
}
