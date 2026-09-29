import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/services/api_service.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
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
          apiService.baseUrl,
          'http://test-server-does-not-exist.local:9999/api/v1',
        );
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

    group('handleDioException - canonical flat error shape', () {
      DioException makeBadResponse(Map<String, dynamic> data, int statusCode) {
        final requestOptions = RequestOptions(path: '/test');
        final response = Response<dynamic>(
          requestOptions: requestOptions,
          data: data,
          statusCode: statusCode,
        );
        return DioException(
          requestOptions: requestOptions,
          response: response,
          type: DioExceptionType.badResponse,
        );
      }

      test('reads top-level message from canonical shape', () {
        final e = makeBadResponse({
          'error': true,
          'message': 'Invalid credentials',
          'code': 'auth_failed',
          'status_code': 400,
        }, 400);
        final result = apiService.handleDioException(e) as ApiException;
        expect(result.message, 'Invalid credentials');
        expect(result.message, isNot('true'));
      });

      test('never surfaces boolean true as the error string', () {
        final e = makeBadResponse({
          'error': true,
          'message': 'Account locked',
          'code': 'account_locked',
          'status_code': 403,
        }, 403);
        final result = apiService.handleDioException(e) as ApiException;
        expect(result.message, isNot('true'));
      });

      test('does not surface boolean error field when message is absent', () {
        // Regression guard: a payload with only {error: true} (no message, no detail)
        // under the old code returned 'true'; correct code must not.
        final e = makeBadResponse({'error': true}, 400);
        final result = apiService.handleDioException(e) as ApiException;
        expect(result.message, isNot('true'));
        expect(result.message, isNotEmpty);
      });

      test('carries the body code, e.g. the 409 unverified_account', () {
        final e = makeBadResponse({
          'error': 'Account linking conflict',
          'code': 'unverified_account',
        }, 409);
        final result = apiService.handleDioException(e) as ApiException;
        expect(result.code, 'unverified_account');
        expect(result.statusCode, 409);
      });

      test('a body without a string code has none', () {
        final e = makeBadResponse({'error': 'x', 'code': 7}, 409);
        final result = apiService.handleDioException(e) as ApiException;
        expect(result.code, isNull);
      });

      test('still reads legacy DRF detail field when message is absent', () {
        final e = makeBadResponse({'detail': 'Not found.'}, 404);
        final result = apiService.handleDioException(e) as ApiException;
        expect(result.message, 'Not found.');
      });
    });

    group('shouldRetry & 429 handling (todo 110)', () {
      DioException makeError({
        required int statusCode,
        String method = 'POST',
        bool retryUnsafe = false,
      }) {
        final requestOptions = RequestOptions(
          path: '/test',
          method: method,
          extra: retryUnsafe ? {ApiService.retryUnsafeRequestKey: true} : {},
        );
        final response = Response<dynamic>(
          requestOptions: requestOptions,
          statusCode: statusCode,
        );
        return DioException(
          requestOptions: requestOptions,
          response: response,
          type: DioExceptionType.badResponse,
        );
      }

      test(
        'does NOT retry 429 even when the request is marked retry-unsafe',
        () {
          // The core fix: a rate-limited non-idempotent mutation must not be
          // resubmitted, or it can create duplicate records.
          final e = makeError(
            statusCode: 429,
            method: 'POST',
            retryUnsafe: true,
          );
          expect(apiService.shouldRetry(e), isFalse);
        },
      );

      test('does NOT retry 429 on an otherwise-safe GET', () {
        final e = makeError(statusCode: 429, method: 'GET');
        expect(apiService.shouldRetry(e), isFalse);
      });

      test(
        'still retries 500 for a retry-unsafe request (regression guard)',
        () {
          final e = makeError(
            statusCode: 500,
            method: 'POST',
            retryUnsafe: true,
          );
          expect(apiService.shouldRetry(e), isTrue);
        },
      );

      test('does not retry 500 for an unmarked mutation', () {
        final e = makeError(statusCode: 500, method: 'POST');
        expect(apiService.shouldRetry(e), isFalse);
      });

      test('429 is surfaced to the caller as a rate-limit ApiException', () {
        // Verifies AC2: handleDioException maps a 429 to a rate-limit
        // ApiException. The interceptor propagates 429 (shouldRetry returns
        // false, proven by the tests above), so the caller receives this shape.
        final result =
            apiService.handleDioException(makeError(statusCode: 429))
                as ApiException;
        expect(result.statusCode, 429);
        expect(result.message, contains('Too many requests'));
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
      test('should have fallback to localhost for development', () {
        final container = ProviderContainer();
        addTearDown(container.dispose);

        final service = container.read(apiServiceProvider);

        expect(service.baseUrl, 'http://localhost:8000/api/v1');
      });
    });
  });

  group('401 recovery: refresh once, retry, sign out only on failure '
      '(todo 462)', () {
    late _AuthServer server;
    late ApiService api;
    late int refreshCalls;
    late int sessionExpiredCalls;
    HttpOverrides? savedOverrides;

    setUp(() async {
      // TestWidgetsFlutterBinding (setUpAll above) swaps in a mock HttpClient
      // that answers 400 to everything; these tests need real loopback HTTP.
      savedOverrides = HttpOverrides.current;
      HttpOverrides.global = null;
      server = await _AuthServer.start();
      api = ApiService(baseUrl: server.baseUrl, authToken: 'stale');
      refreshCalls = 0;
      sessionExpiredCalls = 0;
      api.setSessionExpiredHandler(() async => sessionExpiredCalls++);
    });

    tearDown(() async {
      await server.close();
      HttpOverrides.global = savedOverrides;
    });

    void refreshTo(String? token, {Future<void>? gate}) {
      api.setAccessTokenRefresher(() async {
        refreshCalls++;
        if (gate != null) await gate;
        return token;
      });
    }

    test('an expired token is refreshed and the JSON request retried with '
        'the same body, without signing out', () async {
      refreshTo('fresh');

      final response = await api.post(
        '/forum/topics/',
        data: {'title': 'Yellow leaves', 'body': 'my unsaved draft'},
      );

      expect(response.statusCode, 200);
      expect(refreshCalls, 1);
      expect(sessionExpiredCalls, 0, reason: 'recovered 401 signed out');
      expect(server.requests.map((r) => r.auth), [
        'Bearer stale',
        'Bearer fresh',
      ]);
      expect(server.requests[1].body, server.requests[0].body);
      expect(
        utf8.decode(server.requests[1].body),
        contains('my unsaved draft'),
      );
    });

    test('a multipart upload is re-sent in full after the refresh', () async {
      // Dio refuses to send a finalized FormData twice; without the clone the
      // retry throws and the diagnosis photo is lost.
      refreshTo('fresh');
      final dir = await Directory.systemTemp.createTemp('todo462');
      addTearDown(() => dir.delete(recursive: true));
      final photo = File('${dir.path}/leaf.jpg');
      await photo.writeAsBytes(List<int>.generate(4096, (i) => i % 251));

      final response = await api.uploadFile(
        '/diagnosis/requests/',
        filePath: photo.path,
        data: {'symptoms': 'brown spots on the leaves'},
      );

      expect(response.statusCode, 200);
      expect(refreshCalls, 1);
      expect(sessionExpiredCalls, 0);
      expect(server.requests, hasLength(2));
      final resent = server.requests[1];
      expect(resent.auth, 'Bearer fresh');
      expect(resent.body, server.requests[0].body);
      expect(resent.body.length, greaterThan(4096));
      expect(latin1.decode(resent.body), contains('brown spots on the leaves'));
    });

    test(
      'concurrent 401s share one refresh and every request succeeds',
      () async {
        final gate = Completer<void>();
        refreshTo('fresh', gate: gate.future);

        final calls = [
          api.get('/forum/topics/'),
          api.post('/forum/posts/', data: {'body': 'reply'}),
          api.get('/garden/beds/'),
        ];
        // Hold the refresh open until all three 401s have landed on it.
        while (server.requests.length < 3) {
          await Future<void>.delayed(const Duration(milliseconds: 5));
        }
        await Future<void>.delayed(const Duration(milliseconds: 20));
        gate.complete();
        final responses = await Future.wait(calls);

        expect(refreshCalls, 1, reason: 'each 401 ran its own refresh');
        expect(responses.map((r) => r.statusCode), [200, 200, 200]);
        expect(sessionExpiredCalls, 0);
      },
    );

    test('a 401 arriving after the refresh finished retries with the new '
        'token instead of refreshing again', () async {
      refreshTo('fresh');
      final slowGate = Completer<void>();
      server.hold('/slow/', slowGate.future);

      final slow = api.get('/slow/'); // goes out with the stale token
      while (server.requests.isEmpty) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      expect((await api.get('/fast/')).statusCode, 200);
      expect(refreshCalls, 1);

      slowGate.complete(); // now its stale-token 401 comes back
      expect((await slow).statusCode, 200);
      expect(refreshCalls, 1, reason: 'a stale 401 refreshed a second time');
      expect(sessionExpiredCalls, 0);
    });

    test(
      'a failed refresh signs out once, with the session-expired error',
      () async {
        refreshTo(null);

        await expectLater(
          api.post('/forum/topics/', data: {'title': 'x'}),
          throwsA(
            isA<ApiException>()
                .having((e) => e.statusCode, 'statusCode', 401)
                .having(
                  (e) => e.message,
                  'message',
                  'Your session has expired. Please sign in again.',
                ),
          ),
        );
        expect(refreshCalls, 1);
        expect(sessionExpiredCalls, 1);
      },
    );

    test('concurrent 401s with a failed refresh sign out once', () async {
      final gate = Completer<void>();
      refreshTo(null, gate: gate.future);

      final calls = [
        for (var i = 0; i < 3; i++)
          api.get('/forum/topics/').then<Object?>((r) => r, onError: (e) => e),
      ];
      while (server.requests.length < 3) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      await Future<void>.delayed(const Duration(milliseconds: 20));
      gate.complete();
      final results = await Future.wait(calls);

      expect(results, everyElement(isA<ApiException>()));
      expect(refreshCalls, 1);
      expect(sessionExpiredCalls, 1);
    });

    test(
      'a second 401 on the retried request signs out; no refresh loop',
      () async {
        server.acceptedToken = 'never';
        refreshTo('fresh');

        await expectLater(
          api.get('/forum/topics/'),
          throwsA(isA<ApiException>()),
        );
        expect(refreshCalls, 1);
        expect(sessionExpiredCalls, 1);
        expect(server.requests, hasLength(2));
      },
    );

    test(
      'a request marked skipAuthRefreshKey signs out without refreshing',
      () async {
        refreshTo('fresh');

        await expectLater(
          api.post(
            '/auth/firebase-token-exchange/',
            data: {'firebase_token': 'x'},
            options: Options(extra: {ApiService.skipAuthRefreshKey: true}),
          ),
          throwsA(isA<ApiException>()),
        );
        expect(refreshCalls, 0);
        expect(sessionExpiredCalls, 1);
      },
    );

    test('a refresh overtaken by a sign-out does not report an expired '
        'session', () async {
      api.setAccessTokenRefresher(() async {
        refreshCalls++;
        api.setAuthToken(null); // the user signed out meanwhile
        return null;
      });

      await expectLater(
        api.get('/forum/topics/'),
        throwsA(isA<ApiException>()),
      );
      expect(refreshCalls, 1);
      expect(sessionExpiredCalls, 0);
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

    test(
      'should successfully call backend health check endpoint',
      () async {
        // Placeholder for future integration test
      },
      skip: 'Requires running Django backend',
    );

    test(
      'should handle authentication with JWT token',
      () async {
        // Placeholder for future integration test
      },
      skip: 'Requires running Django backend',
    );

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

class _SeenRequest {
  _SeenRequest(this.method, this.path, this.auth, this.body);

  final String method;
  final String path;
  final String? auth;
  final List<int> body;
}

/// A loopback backend that 401s any bearer token but [acceptedToken], and
/// records every request (auth header and raw body bytes) so a test can prove
/// the retry re-sent the same input.
class _AuthServer {
  _AuthServer._(this._server) {
    _server.listen(_handle);
  }

  static Future<_AuthServer> start() async =>
      _AuthServer._(await HttpServer.bind(InternetAddress.loopbackIPv4, 0));

  final HttpServer _server;
  final List<_SeenRequest> requests = [];
  final Map<String, Future<void>> _holds = {};
  String acceptedToken = 'fresh';

  String get baseUrl => 'http://${_server.address.host}:${_server.port}';

  /// Delay the first response on [path] until [until] completes.
  void hold(String path, Future<void> until) => _holds[path] = until;

  Future<void> _handle(HttpRequest request) async {
    final body = await request.fold<List<int>>(
      <int>[],
      (acc, chunk) => acc..addAll(chunk),
    );
    final auth = request.headers.value(HttpHeaders.authorizationHeader);
    requests.add(_SeenRequest(request.method, request.uri.path, auth, body));

    final hold = _holds.remove(request.uri.path);
    if (hold != null) await hold;

    final ok = auth == 'Bearer $acceptedToken';
    request.response.statusCode = ok ? HttpStatus.ok : HttpStatus.unauthorized;
    request.response.headers.contentType = ContentType.json;
    request.response.write(
      jsonEncode(ok ? {'ok': true} : {'detail': 'Token is expired'}),
    );
    await request.response.close();
  }

  Future<void> close() => _server.close(force: true);
}
