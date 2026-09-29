import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Centralized HTTP client service for Django backend communication.
///
/// This service provides:
/// - Automatic authentication header injection
/// - Request/response logging in debug mode
/// - Comprehensive error handling (401, 429, 5xx)
/// - Retry logic with exponential backoff
/// - Timeout configuration
/// - Multipart file upload support
///
/// Usage:
/// ```dart
/// final apiService = ref.read(apiServiceProvider);
/// final response = await apiService.get('/plant-identification/');
/// ```
class ApiService {
  static const int _maxRetryAttempts = 3;
  static const String _retryAttemptKey = 'api_retry_attempt';
  static const String retryUnsafeRequestKey = 'retry_unsafe_request';

  /// Request-extra flag: a 401 on this request must NOT trigger the
  /// session-expired flow (used by sign-out's own best-effort FCM clear).
  static const String skipSessionExpiryKey = 'skip_session_expiry';

  /// Request-extra flag: a 401 on this request goes straight to the
  /// session-expired flow, with no silent token refresh first. Set on the
  /// Firebase token exchange, which IS the refresh (todo 462): refreshing a
  /// failed refresh would only repeat it.
  static const String skipAuthRefreshKey = 'skip_auth_refresh';

  /// Set on a request once it has been retried after a refresh, so a second
  /// 401 signs out instead of refreshing again.
  static const String _authRetriedKey = 'auth_retried';

  /// The [_authEpoch] the request went out under, so a 401 can tell "my
  /// token is stale, someone already refreshed it" from "the current token is
  /// rejected". An epoch, not the token: LogInterceptor prints `extra` in
  /// debug builds, and the bearer token must never reach a log.
  static const String _sentEpochKey = 'auth_epoch';

  final Dio _dio;
  final String baseUrl;
  String? _authToken;

  /// Bumped on every token change.
  int _authEpoch = 0;
  Future<void> Function()? _onSessionExpired;
  Future<String?> Function()? _onRefreshAccessToken;

  /// The one refresh every concurrent 401 waits on (todo 462).
  Future<String?>? _refreshInFlight;

  ApiService({required this.baseUrl, String? authToken})
    : _authToken = authToken,
      _dio = Dio(
        BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          sendTimeout: const Duration(seconds: 30),
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        ),
      ) {
    _setupInterceptors();
  }

  /// Configure Dio interceptors for logging and error handling
  void _setupInterceptors() {
    // Add auth token to all requests if available
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          options.extra[_sentEpochKey] = _authEpoch;
          if (_authToken != null) {
            options.headers['Authorization'] = 'Bearer $_authToken';
          }
          return handler.next(options);
        },
      ),
    );

    // Add logging interceptor in debug mode only
    if (kDebugMode) {
      _dio.interceptors.add(
        LogInterceptor(
          requestBody: false,
          responseBody: false,
          requestHeader: false,
          responseHeader: false,
          error: true,
          logPrint: (obj) => debugPrint('[API] $obj'),
        ),
      );
    }

    // Add error handling interceptor
    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;

          if (kDebugMode) {
            debugPrint(
              '[API ERROR] Status: $statusCode, Path: ${error.requestOptions.path}',
            );
            debugPrint('[API ERROR] Message: ${error.message}');
          }

          // Handle specific error cases
          switch (statusCode) {
            case 401:
              // Requests that opt out (e.g. sign-out's own best-effort FCM
              // clear on an already-expired JWT) must not convert an
              // intentional sign-out into a "session expired" flow — the
              // opt-out rides the REQUEST, so it also covers a response
              // arriving after the caller's timeout abandoned it (todo 253
              // slice 6 review sweep).
              if (error.requestOptions.extra[skipSessionExpiryKey] == true) {
                if (kDebugMode) {
                  debugPrint(
                    '[API ERROR] 401 on session-expiry-exempt request - ignored',
                  );
                }
                break;
              }
              return _recoverFromUnauthorized(error, handler);

            case 429:
              // Rate limited - extract retry-after header
              final retryAfter = error.response?.headers['retry-after']?.first;
              if (kDebugMode) {
                debugPrint(
                  '[API ERROR] 429 Rate Limited - Retry after: $retryAfter seconds',
                );
              }
              break;

            case 500:
            case 502:
            case 503:
            case 504:
              // Server error - implement retry with backoff
              if (kDebugMode) {
                debugPrint(
                  '[API ERROR] $statusCode Server Error - Consider retry',
                );
              }
              break;
          }

          if (shouldRetry(error)) {
            try {
              final response = await _retry(error);
              return handler.resolve(response);
            } on DioException catch (retryError) {
              return handler.next(retryError);
            }
          }

          return handler.next(error);
        },
      ),
    );
  }

  @visibleForTesting
  bool shouldRetry(DioException error) {
    final statusCode = error.response?.statusCode;
    // 429 is intentionally excluded from retry: the server has explicitly asked
    // the client to back off. Retrying a non-idempotent mutation (create post /
    // topic, image upload) on a 429 can create duplicate records (todo 110). The
    // 429 is surfaced to the caller instead; manual retry after the rate window
    // resets is the correct UX.
    final retryableStatus =
        statusCode == 500 ||
        statusCode == 502 ||
        statusCode == 503 ||
        statusCode == 504;

    if (!retryableStatus) {
      return false;
    }

    final requestOptions = error.requestOptions;
    final attempt = requestOptions.extra[_retryAttemptKey] as int? ?? 0;
    if (attempt >= _maxRetryAttempts) {
      return false;
    }

    return _isSafelyRetryable(requestOptions);
  }

  bool _isSafelyRetryable(RequestOptions requestOptions) {
    final method = requestOptions.method.toUpperCase();
    if (method == 'GET' || method == 'HEAD' || method == 'OPTIONS') {
      return true;
    }

    return requestOptions.extra[retryUnsafeRequestKey] == true;
  }

  Future<Response<dynamic>> _retry(DioException error) async {
    final requestOptions = error.requestOptions;
    final nextAttempt =
        (requestOptions.extra[_retryAttemptKey] as int? ?? 0) + 1;
    requestOptions.extra[_retryAttemptKey] = nextAttempt;

    final delay = _retryDelay(error, nextAttempt);
    if (kDebugMode) {
      debugPrint(
        '[API RETRY] Attempt $nextAttempt/$_maxRetryAttempts for '
        '${requestOptions.method} ${requestOptions.path} after ${delay.inMilliseconds}ms',
      );
    }

    await Future<void>.delayed(delay);
    return _dio.fetch<dynamic>(requestOptions);
  }

  Duration _retryDelay(DioException error, int attempt) {
    final retryAfter = error.response?.headers['retry-after']?.first;
    final retryAfterSeconds = retryAfter == null
        ? null
        : int.tryParse(retryAfter);
    if (retryAfterSeconds != null && retryAfterSeconds > 0) {
      return Duration(seconds: retryAfterSeconds.clamp(1, 30));
    }

    final baseDelayMs = 250 * (1 << (attempt - 1));
    return Duration(milliseconds: baseDelayMs.clamp(250, 2000));
  }

  /// A 401 first tries to recover silently: refresh the access token, then
  /// re-send the request once, with its body intact. Only a failed refresh (or
  /// a second 401 on the re-sent request) signs the user out (todo 462).
  Future<void> _recoverFromUnauthorized(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final options = error.requestOptions;
    if (_onRefreshAccessToken == null ||
        options.extra[skipAuthRefreshKey] == true ||
        options.extra[_authRetriedKey] == true) {
      if (kDebugMode) {
        debugPrint('[API ERROR] 401 Unauthorized - session expired');
      }
      await _handleSessionExpired();
      return handler.next(error);
    }

    // A request that went out with a token which has since been replaced
    // (a concurrent 401 already refreshed it) retries with the new one
    // rather than refreshing again.
    final tokenReplacedSinceSent =
        options.extra[_sentEpochKey] != _authEpoch && _authToken != null;
    if (!tokenReplacedSinceSent) {
      final token = await _refreshAccessTokenOnce();
      if (token == null) {
        return handler.next(error);
      }
    }

    options.extra[_authRetriedKey] = true;
    // A multipart body is a one-shot stream: Dio refuses to send the same
    // FormData twice, so re-send a clone (the photo, not a lost input).
    final data = options.data;
    if (data is FormData) {
      options.data = data.clone();
    }
    if (kDebugMode) {
      debugPrint(
        '[API AUTH] Retrying ${options.method} ${options.path} after refresh',
      );
    }
    try {
      // fetch() re-runs onRequest, which attaches the fresh bearer token.
      final response = await _dio.fetch<dynamic>(options);
      return handler.resolve(response);
    } on DioException catch (retryError) {
      return handler.next(retryError);
    }
  }

  /// Every 401 that arrives while a refresh is running waits on that same
  /// refresh, so N concurrent 401s cost one token exchange.
  Future<String?> _refreshAccessTokenOnce() {
    return _refreshInFlight ??= _runRefresh().whenComplete(() {
      _refreshInFlight = null;
    });
  }

  Future<String?> _runRefresh() async {
    final epochBefore = _authEpoch;
    String? token;
    try {
      token = await _onRefreshAccessToken?.call();
    } catch (error) {
      if (kDebugMode) {
        debugPrint('[API AUTH] Token refresh failed: $error');
      }
      token = null;
    }

    if (token != null) {
      setAuthToken(token);
      return token;
    }

    // Signed out once, here, for every waiter. And only when the auth state
    // did not move while the refresh ran: an explicit sign-out or a user
    // switch meanwhile is not an expired session.
    if (_authEpoch == epochBefore) {
      await _handleSessionExpired();
    }
    return null;
  }

  Future<void> _handleSessionExpired() async {
    final onSessionExpired = _onSessionExpired;
    if (onSessionExpired == null) {
      return;
    }

    try {
      await onSessionExpired();
    } catch (error) {
      if (kDebugMode) {
        debugPrint('[API AUTH] Session-expired handler failed: $error');
      }
    }
  }

  /// Update the authentication token
  ///
  /// Call this method after user login to inject JWT token
  /// into all subsequent requests.
  void setAuthToken(String? token) {
    _authToken = token;
    _authEpoch++;
  }

  /// Register a callback that clears local auth state after failed recovery.
  void setSessionExpiredHandler(Future<void> Function()? onSessionExpired) {
    _onSessionExpired = onSessionExpired;
  }

  /// Register the callback that gets a fresh access token after a 401: it
  /// returns the new token, or `null` when the session cannot be recovered
  /// (which signs the user out). Unset, a 401 signs out directly.
  void setAccessTokenRefresher(Future<String?> Function()? refresher) {
    _onRefreshAccessToken = refresher;
  }

  /// GET request
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.get('/plant-identification/plants/');
  /// ```
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.get(
        path,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw handleDioException(e);
    }
  }

  /// POST request
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.post(
  ///   '/plant-identification/identify/',
  ///   data: {'image_url': imageUrl},
  /// );
  /// ```
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw handleDioException(e);
    }
  }

  /// PATCH request
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.patch(
  ///   '/users/profile/',
  ///   data: {'display_name': 'New Name'},
  /// );
  /// ```
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.patch(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw handleDioException(e);
    }
  }

  /// DELETE request
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.delete('/calendar/api/plants/$plantId/');
  /// ```
  Future<Response> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.delete(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw handleDioException(e);
    }
  }

  /// PUT request
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.put(
  ///   '/calendar/api/care-tasks/$taskId/',
  ///   data: {'completed': true},
  /// );
  /// ```
  Future<Response> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.put(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw handleDioException(e);
    }
  }

  /// Upload file using multipart form data
  ///
  /// This is specifically designed for image uploads to Django backend.
  /// The Django backend expects a field named 'image' for plant identification.
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.uploadFile(
  ///   '/plant-identification/identify/',
  ///   filePath: '/path/to/image.jpg',
  ///   data: {'latitude': 37.7749, 'longitude': -122.4194},
  /// );
  /// ```
  Future<Response> uploadFile(
    String path, {
    required String filePath,
    String fieldName = 'image',
    Map<String, dynamic>? data,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    try {
      final formData = FormData.fromMap({
        fieldName: await MultipartFile.fromFile(
          filePath,
          filename: filePath.split('/').last,
        ),
        ...?data,
      });

      return await _dio.post(
        path,
        data: formData,
        onSendProgress: onSendProgress,
        options: Options(headers: {'Content-Type': 'multipart/form-data'}),
      );
    } on DioException catch (e) {
      throw handleDioException(e);
    }
  }

  /// Convert DioException to user-friendly error message
  @visibleForTesting
  Exception handleDioException(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return ApiException(
          'Connection timeout. Please check your internet connection.',
          statusCode: null,
        );

      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        String message;

        if (statusCode == 401) {
          return ApiException(
            'Your session has expired. Please sign in again.',
            statusCode: statusCode,
          );
        }

        if (statusCode == 429) {
          return ApiException(
            'Too many requests. Please wait a moment and try again.',
            statusCode: statusCode,
          );
        }

        if (statusCode != null && statusCode >= 500) {
          return ApiException(
            'The server is temporarily unavailable. Please try again shortly.',
            statusCode: statusCode,
          );
        }

        // Try to extract error message from response data.
        // Canonical shape: {error: true, message: "...", code: "...", status_code: N}
        // Legacy DRF shape: {detail: "..."}
        // message wins over detail to match the canonical contract; detail is fallback for
        // plain DRF responses that have no message field.
        final responseData = e.response?.data;
        if (responseData is Map<String, dynamic>) {
          message =
              responseData['message']?.toString() ??
              responseData['detail']?.toString() ??
              (responseData['error'] is String
                  ? responseData['error'] as String
                  : null) ??
              e.response?.statusMessage ??
              'Request failed with status $statusCode';
        } else if (responseData is String) {
          message = responseData;
        } else {
          message =
              e.response?.statusMessage ??
              'Request failed with status $statusCode';
        }

        final code = responseData is Map<String, dynamic>
            ? responseData['code']
            : null;
        return ApiException(
          message,
          statusCode: statusCode,
          code: code is String ? code : null,
        );

      case DioExceptionType.cancel:
        return ApiException('Request was cancelled', statusCode: null);

      case DioExceptionType.unknown:
        if (e.error.toString().contains('SocketException')) {
          return ApiException(
            'No internet connection. Please check your network.',
            statusCode: null,
          );
        }
        return ApiException(
          e.message ?? 'An unknown error occurred',
          statusCode: null,
        );

      default:
        return ApiException('An unexpected error occurred', statusCode: null);
    }
  }
}

/// Custom exception for API errors
///
/// This exception includes both a user-friendly message and
/// the HTTP status code for programmatic error handling.
class ApiException implements Exception {
  final String message;
  final int? statusCode;

  /// The response body's machine-readable `code`, when it has one (e.g. the
  /// token exchange's 409 `unverified_account`).
  final String? code;

  ApiException(this.message, {this.statusCode, this.code});

  @override
  String toString() => statusCode != null
      ? 'ApiException($statusCode): $message'
      : 'ApiException: $message';
}

/// Riverpod provider for ApiService
///
/// This provider creates a singleton instance of ApiService
/// that can be injected into any widget or service.
///
/// The base URL is loaded from --dart-define for environment-specific
/// configuration.
final apiServiceProvider = Provider<ApiService>((ref) {
  // Load base URL from --dart-define.
  // Default to localhost for development if not set.
  const dartDefinedBaseUrl = String.fromEnvironment('API_BASE_URL');
  if (dartDefinedBaseUrl.isEmpty && kReleaseMode) {
    throw StateError(
      'Missing API_BASE_URL. Pass --dart-define=API_BASE_URL=... for release builds.',
    );
  }
  final baseUrl = dartDefinedBaseUrl.isNotEmpty
      ? dartDefinedBaseUrl
      : 'http://localhost:8000/api/v1';

  if (kDebugMode) {
    debugPrint('[API] Initializing ApiService with baseUrl: $baseUrl');
  }

  // Auth token will be set by AuthService after login
  return ApiService(baseUrl: baseUrl, authToken: null);
});
