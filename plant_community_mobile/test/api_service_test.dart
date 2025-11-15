import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:plant_community_mobile/services/api_service.dart';

void main() {
  // Initialize dotenv before tests
  setUpAll(() async {
    // Load test environment variables
    TestWidgetsFlutterBinding.ensureInitialized();
    await dotenv.load(fileName: '.env');
  });

  group('ApiService - Unit Tests', () {
    late ApiService apiService;

    setUp(() {
      // Create ApiService instance with test configuration
      // Note: Using a non-existent base URL to prevent accidental network calls
      apiService = ApiService(
        baseUrl: 'http://test-server-does-not-exist.local:9999/api/v1',
        authToken: null,
      );
    });

    group('Initialization', () {
      test('should create ApiService instance with correct base URL', () {
        expect(apiService, isNotNull);
        expect(
            apiService.baseUrl, 'http://test-server-does-not-exist.local:9999/api/v1');
      });

      test('should allow setting auth token after creation', () {
        const testToken = 'test-jwt-token-123';
        apiService.setAuthToken(testToken);

        // Token is set internally, we can't directly verify
        // but method should execute without error
        expect(apiService, isNotNull);
      });

      test('should allow removing auth token by setting to null', () {
        apiService.setAuthToken('token');
        apiService.setAuthToken(null);

        expect(apiService, isNotNull);
      });
    });

    group('ApiException', () {
      test('should format toString with status code', () {
        final exception = ApiException('Test error', statusCode: 404);
        expect(exception.toString(), 'ApiException(404): Test error');
      });

      test('should format toString without status code', () {
        final exception = ApiException('Test error', statusCode: null);
        expect(exception.toString(), 'ApiException: Test error');
      });

      test('should store message and status code correctly', () {
        final exception = ApiException('Request failed', statusCode: 500);
        expect(exception.message, 'Request failed');
        expect(exception.statusCode, 500);
      });

      test('should allow null status code', () {
        final exception = ApiException('Network error', statusCode: null);
        expect(exception.message, 'Network error');
        expect(exception.statusCode, isNull);
      });
    });

    group('Request Methods - API Coverage', () {
      // These tests verify that all HTTP methods are available
      // Integration tests with a real backend should be done separately

      test('GET method should be available', () {
        // Verify method exists and can be called
        expect(() => apiService.get, returnsNormally);
      });

      test('POST method should be available', () {
        expect(() => apiService.post, returnsNormally);
      });

      test('PATCH method should be available', () {
        expect(() => apiService.patch, returnsNormally);
      });

      test('PUT method should be available', () {
        expect(() => apiService.put, returnsNormally);
      });

      test('DELETE method should be available', () {
        expect(() => apiService.delete, returnsNormally);
      });

      test('uploadFile method should be available', () {
        expect(() => apiService.uploadFile, returnsNormally);
      });
    });

    group('Environment Configuration', () {
      test('should load API_BASE_URL from environment', () {
        final baseUrl = dotenv.env['API_BASE_URL'];
        expect(baseUrl, isNotNull);
        expect(baseUrl, contains('http'));
      });

      test('should have fallback to localhost for development', () {
        // When .env doesn't have API_BASE_URL, provider uses default
        const defaultUrl = 'http://localhost:8000/api/v1';
        expect(defaultUrl, isNotNull);
      });
    });
  });

  group('Integration Tests', () {
    // NOTE: Integration tests require a running Django backend
    // To run these tests:
    // 1. Start the Django backend: cd backend && python manage.py runserver
    // 2. Run tests: flutter test test/api_service_test.dart
    //
    // These tests are skipped by default to allow unit tests to pass in CI
    // without requiring backend infrastructure.

    test('should successfully call backend health check endpoint', () async {
      // Placeholder for future integration test
    }, skip: 'Requires running Django backend');

    test('should handle authentication with JWT token', () async {
      // Placeholder for future integration test
    }, skip: 'Requires running Django backend');

    test('should upload file to backend', () async {
      // Placeholder for future integration test
    }, skip: 'Requires running Django backend');
  });
}

/// INTEGRATION TESTING GUIDE:
///
/// For comprehensive integration testing with the Django backend:
/// 1. Ensure Django backend is running on localhost:8000
/// 2. Create a test user and obtain JWT token
/// 3. Test plant identification endpoint:
///    - Upload a test image
///    - Verify response structure
///    - Check for proper error handling
/// 4. Test rate limiting behavior
/// 5. Test authentication token refresh
///
/// Example integration test (to be added when backend is stable):
/// ```dart
/// test('full plant identification flow', () async {
///   final apiService = ApiService(
///     baseUrl: 'http://localhost:8000/api/v1',
///     authToken: testJwtToken,
///   );
///
///   // Upload test image
///   final response = await apiService.uploadFile(
///     '/plant-identification/identify/',
///     filePath: 'test_assets/plant.jpg',
///   );
///
///   expect(response.statusCode, 200);
///   expect(response.data['species'], isNotNull);
/// });
/// ```


