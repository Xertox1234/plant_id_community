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

  final Dio _dio;
  final String baseUrl;
  String? _authToken;
  Future<void> Function()? _onSessionExpired;

  ApiService({
    required this.baseUrl,
    String? authToken,
  })  : _authToken = authToken,
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
            debugPrint('[API ERROR] Status: $statusCode, Path: ${error.requestOptions.path}');
            debugPrint('[API ERROR] Message: ${error.message}');
          }

          // Handle specific error cases
          switch (statusCode) {
            case 401:
              if (kDebugMode) {
                debugPrint('[API ERROR] 401 Unauthorized - session expired');
              }
              await _handleSessionExpired();
              break;

            case 429:
              // Rate limited - extract retry-after header
              final retryAfter = error.response?.headers['retry-after']?.first;
              if (kDebugMode) {
                debugPrint('[API ERROR] 429 Rate Limited - Retry after: $retryAfter seconds');
              }
              break;

            case 500:
            case 502:
            case 503:
            case 504:
              // Server error - implement retry with backoff
              if (kDebugMode) {
                debugPrint('[API ERROR] $statusCode Server Error - Consider retry');
              }
              break;
          }

          if (_shouldRetry(error)) {
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

  bool _shouldRetry(DioException error) {
    final statusCode = error.response?.statusCode;
    final retryableStatus = statusCode == 429 ||
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
    final nextAttempt = (requestOptions.extra[_retryAttemptKey] as int? ?? 0) + 1;
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
    final retryAfterSeconds = retryAfter == null ? null : int.tryParse(retryAfter);
    if (retryAfterSeconds != null && retryAfterSeconds > 0) {
      return Duration(seconds: retryAfterSeconds.clamp(1, 30));
    }

    final baseDelayMs = 250 * (1 << (attempt - 1));
    return Duration(milliseconds: baseDelayMs.clamp(250, 2000));
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
  }

  /// Register a callback that clears local auth state after failed recovery.
  void setSessionExpiredHandler(Future<void> Function()? onSessionExpired) {
    _onSessionExpired = onSessionExpired;
  }

  /// GET request
  ///
  /// Example:
  /// ```dart
  /// final response = await apiService.get('/plant-identification/species/');
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
      throw _handleDioException(e);
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
      throw _handleDioException(e);
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
      throw _handleDioException(e);
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
      throw _handleDioException(e);
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
      throw _handleDioException(e);
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
        if (data != null) ...data,
      });

      return await _dio.post(
        path,
        data: formData,
        onSendProgress: onSendProgress,
        options: Options(
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        ),
      );
    } on DioException catch (e) {
      throw _handleDioException(e);
    }
  }

  /// Convert DioException to user-friendly error message
  Exception _handleDioException(DioException e) {
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

        // Try to extract error message from response data
        final responseData = e.response?.data;
        if (responseData is Map<String, dynamic>) {
          message = responseData['detail']?.toString() ??
              responseData['error']?.toString() ??
              e.response?.statusMessage ??
              'Request failed with status $statusCode';
        } else if (responseData is String) {
          message = responseData;
        } else {
          message = e.response?.statusMessage ??
              'Request failed with status $statusCode';
        }

        return ApiException(message, statusCode: statusCode);

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
        return ApiException(
          'An unexpected error occurred',
          statusCode: null,
        );
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

  ApiException(this.message, {this.statusCode});

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
  final baseUrl = dartDefinedBaseUrl.isNotEmpty ? dartDefinedBaseUrl : 'http://localhost:8000/api/v1';

  if (kDebugMode) {
    debugPrint('[API] Initializing ApiService with baseUrl: $baseUrl');
  }

  // Auth token will be set by AuthService after login
  return ApiService(
    baseUrl: baseUrl,
    authToken: null,
  );
});
