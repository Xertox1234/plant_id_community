import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/firebase_storage_service.dart';
import 'package:plant_community_mobile/services/plant_identification_service.dart';
import 'package:uuid/uuid.dart';

void main() {
  group('PlantIdentificationService', () {
    test('falls back to uuidProvider when API omits id', () async {
      final container = ProviderContainer(
        overrides: [
          apiServiceProvider.overrideWith((ref) => _NoIdApiService()),
          firebaseStorageServiceProvider.overrideWith(
            () => _MockFirebaseStorageService(),
          ),
          uuidProvider.overrideWithValue(const _MockUuid()),
        ],
      );

      addTearDown(container.dispose);

      final service = container.read(
        plantIdentificationServiceProvider.notifier,
      );

      final plant = await service.identifyPlant('/test/image.jpg');

      expect(plant.id, 'mock-uuid-42');
      expect(plant.name, 'Test Plant');
      expect(plant.scientificName, 'Testus plantus');
    });
  });
}

/// Mock API service that returns a valid response without an `id` field,
/// forcing the service to fall back to uuidProvider for the plant ID.
class _NoIdApiService extends ApiService {
  _NoIdApiService() : super(baseUrl: 'http://localhost:8000/api/v1');

  @override
  String get baseUrl => 'http://localhost:8000/api/v1';

  @override
  void setAuthToken(String? token) {}

  @override
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {
        'name': 'Test Plant',
        'scientific_name': 'Testus plantus',
        'description': 'A test plant for unit testing.',
        'care_instructions': ['Water occasionally'],
      },
    );
  }

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => throw UnimplementedError();

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => throw UnimplementedError();

  @override
  Future<Response> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => throw UnimplementedError();

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => throw UnimplementedError();

  @override
  Future<Response> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) => throw UnimplementedError();
}

/// Minimal mock Firebase Storage service for unit tests.
class _MockFirebaseStorageService extends FirebaseStorageService {
  @override
  Future<String> uploadPlantImage(
    String filePath, {
    Function(double progress)? onProgress,
  }) async {
    return 'https://firebase.storage/mock.jpg';
  }

  @override
  Future<void> deletePlantImage(String imageUrl) async {}
}

/// Deterministic UUID mock that always returns the same v4 value.
class _MockUuid implements Uuid {
  const _MockUuid();

  @override
  String v4({
    @Deprecated('use config instead. Removal in 5.0.0')
    Map<String, dynamic>? options,
    dynamic config,
  }) => 'mock-uuid-42';

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
