import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/firebase_storage_service.dart';
import 'package:plant_community_mobile/services/plant_identification_service.dart';
import 'package:uuid/uuid.dart';

void main() {
  group('PlantIdentificationService', () {
    Future<Plant> identifyWith(Map<String, dynamic> response) {
      final container = ProviderContainer(
        overrides: [
          apiServiceProvider.overrideWith((ref) => _FakeApiService(response)),
          firebaseStorageServiceProvider.overrideWith(
            () => _MockFirebaseStorageService(),
          ),
          uuidProvider.overrideWithValue(const _MockUuid()),
        ],
      );
      addTearDown(container.dispose);
      return container
          .read(plantIdentificationServiceProvider.notifier)
          .identifyPlant('/test/image.jpg');
    }

    test('falls back to uuidProvider when API omits id', () async {
      final plant = await identifyWith(_backendResponse());

      expect(plant.id, 'mock-uuid-42');
      expect(plant.name, 'Fiddle-leaf fig');
      expect(plant.scientificName, 'Ficus lyrata');
    });

    // The shape `apps/plant_identification/api/simple_views.py`
    // identify_plant actually returns. The parser used to read `name` and a
    // care list, which the backend never sent, so every real identification
    // failed with "No plant could be identified" (2026-10-25 sim check).
    test('parses the backend identify response', () async {
      final plant = await identifyWith(_backendResponse());

      expect(plant.description, 'A tree with large violin-shaped leaves.');
      expect(plant.imageUrl, 'https://firebase.storage/mock.jpg');
      // Non-string entries (`common_issues: []`) are skipped.
      expect(plant.care, [
        'Watering: Water when the top inch is dry',
        'Light: Bright indirect light',
      ]);
    });

    // Todo 662: the backend returns `care_instructions: null` until it has
    // plant-specific care. The parser used to fill in a generic sentence,
    // which the results screen then showed as this plant's care.
    test('null care_instructions gives no care, not generic text', () async {
      final plant = await identifyWith({
        ..._backendResponse(),
        'care_instructions': null,
      });

      expect(plant.name, 'Fiddle-leaf fig');
      expect(plant.care, isEmpty);
    });

    test('surfaces the backend error from a success:false response', () {
      expect(
        identifyWith({'success': false, 'error': 'Image too blurry'}),
        throwsA(
          isA<PlantIdentificationException>().having(
            (e) => e.message,
            'message',
            'Image too blurry',
          ),
        ),
      );
    });

    test('an Unknown answer with no scientific name is not a result', () {
      expect(
        identifyWith({
          'success': true,
          'plant_name': 'Unknown',
          'scientific_name': '',
          'suggestions': <dynamic>[],
          'care_instructions': null,
        }),
        throwsA(isA<PlantIdentificationException>()),
      );
    });
  });
}

Map<String, dynamic> _backendResponse() => {
  'success': true,
  'plant_name': 'Fiddle-leaf fig',
  'scientific_name': 'Ficus lyrata',
  'confidence': 0.93,
  'suggestions': [
    {
      'plant_name': 'Fiddle-leaf fig',
      'scientific_name': 'Ficus lyrata',
      'common_names': ['Fiddle-leaf fig'],
      'description': 'A tree with large violin-shaped leaves.',
    },
  ],
  'care_instructions': {
    'watering': 'Water when the top inch is dry',
    'light': 'Bright indirect light',
    'common_issues': <dynamic>[],
  },
  'disease_detection': null,
  'degraded': false,
};

/// Fake API service whose identify upload returns [response].
class _FakeApiService extends ApiService {
  _FakeApiService(this.response)
    : super(baseUrl: 'http://localhost:8000/api/v1');

  final Map<String, dynamic> response;

  @override
  String get baseUrl => 'http://localhost:8000/api/v1';

  @override
  void setAuthToken(String? token) {}

  @override
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    String? filename,
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
    Duration? receiveTimeout,
  }) async {
    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: response,
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
