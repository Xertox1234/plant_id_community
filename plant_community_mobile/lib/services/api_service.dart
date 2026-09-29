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

  /// Request-extra flag: a 401 on this request never signs the user out, not
  /// even after a refused refresh. It still refreshes the token and re-sends
  /// the request once, unless [skipAuthRefreshKey] is also set (todo 498).
  /// Set on sign-out's own best-effort FCM clear, which must still reach the
  /// server when the access token expired while the app sat idle.
  static const String skipSessionExpiryKey = 'skip_session_expiry';

  /// Request-extra flag: a 401 on this request gets no silent token refresh.
  /// Set on the Firebase token exchange, which IS the refresh (todo 462):
  /// refreshing a failed refresh would only repeat it. On its own it goes
  /// straight to the session-expired flow; with [skipSessionExpiryKey] the
  /// 401 is only passed to the caller.
  static const String skipAuthRefreshKey = 'skip_auth_refresh';

  /// Request-extra flag: send this request with no `Authorization` header,
  /// even while a bearer token is set. Set on the refresh's token exchange:
  /// the backend authenticates any bearer before the view runs, so the expired
  /// token it would otherwise carry turns the exchange into a 401 (todo 462).
  static const String omitAuthHeaderKey = 'omit_auth_header';

  /// Set on a request once it has been retried after a refresh, so a second
  /// 401 signs out instead of refreshing again.
  static const String _authRetriedKey = 'auth_retried';

  /// The [_authEpoch] the request went out under, so a 401 can tell "my
  /// token is stale, someone already refreshed it" from "the current token is
  /// rejected". An epoch, not the token: LogInterceptor prints `extra` in
  /// debug builds, and the bearer token must never reach a log.
  static const String _sentEpochKey = 'auth_epoch';

  /// The [_authSession] the request went out under. A 401 for a request from
  /// an ended session (sign-out, user switch) is never retried under the new
  /// session's token, and never refreshes or signs anyone out.
  static const String _sentSessionKey = 'auth_session';

  final Dio _dio;
  final String baseUrl;
  String? _authToken;

  /// Bumped on every token change.
  int _authEpoch = 0;

  /// One session is one signed-in user. Every [setAuthToken] call starts a
  /// new one, whether it clears the token or sets it, so a sign-in path that
  /// sets a token without clearing first still cannot inherit the last
  /// user's requests (todo 498). Only [replaceAuthToken] (a refresh, or the
  /// JWT of a sign-in that cleared first) keeps the session, and [endSession]
  /// ends it while the token stays set.
  int _authSession = 0;

  /// True only inside [replaceAuthToken], so its call to [setAuthToken] (the
  /// one place the token changes, and what test fakes override) keeps the
  /// session.
  bool _replacingToken = false;

  Future<void> Function()? _onSessionExpired;
  Future<String?> Function()? _onRefreshAccessToken;

  /// The one refresh every concurrent 401 of the current session waits on
  /// (todo 462). Forgotten when the session ends, so the next user's first
  /// 401 starts a refresh of its own instead of joining the last user's
  /// (todo 498).
  Future<_RefreshOutcome>? _refreshInFlight;

  /// The session [_expiryInFlight] signs out, so every 401 of one session
  /// shares a single sign-out (todo 498).
  int? _expiringSession;
  Future<void>? _expiryInFlight;

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
          options.extra[_sentSessionKey] = _authSession;
          if (options.extra[omitAuthHeaderKey] == true) {
            options.headers.remove('Authorization');
          } else if (_authToken != null) {
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
  /// re-send the request once, with its body intact (todo 462). Only a
  /// refused refresh, or a second 401 on the re-sent request, signs the user
  /// out. A refresh that fails for a transient reason (offline, timeout, 5xx,
  /// 429) leaves them signed in and fails the request with that reason, so
  /// the next 401 tries again (todo 498, owner decision).
  Future<void> _recoverFromUnauthorized(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final options = error.requestOptions;
    // Sent under a session that has since ended: re-sending it would act as
    // whoever is signed in now, and its 401 says nothing about their token.
    if (options.extra[_sentSessionKey] != _authSession) {
      if (kDebugMode) {
        debugPrint('[API AUTH] 401 from an ended session; not retried');
      }
      return handler.next(error);
    }
    if (_onRefreshAccessToken == null ||
        options.extra[skipAuthRefreshKey] == true ||
        options.extra[_authRetriedKey] == true) {
      await _expireSession(options);
      return handler.next(error);
    }

    // A request that went out with a token which has since been replaced
    // (a concurrent 401 already refreshed it) retries with the new one
    // rather than refreshing again.
    final tokenReplacedSinceSent =
        options.extra[_sentEpochKey] != _authEpoch && _authToken != null;
    if (!tokenReplacedSinceSent) {
      final outcome = await _refreshAccessTokenOnce();
      // A sign-out or user switch overtook the refresh: nothing to retry, and
      // nobody to sign out.
      if (options.extra[_sentSessionKey] != _authSession) {
        return handler.next(error);
      }
      switch (outcome) {
        case _Refreshed():
          break;
        case _Refused():
          await _expireSession(options);
          return handler.next(error);
        case _Unavailable(:final reason):
          // Surfaced as the refresh's own failure (a 503, a 429, no
          // network), which handleDioException passes through as is, not as
          // the 401's "Your session has expired".
          return handler.next(
            DioException(
              requestOptions: options,
              type: DioExceptionType.unknown,
              error: reason,
              message: reason.message,
            ),
          );
        case _Superseded():
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

  /// Every 401 of the current session that arrives while a refresh is
  /// running waits on that same refresh, so N concurrent 401s cost one token
  /// exchange.
  Future<_RefreshOutcome> _refreshAccessTokenOnce() {
    final running = _refreshInFlight;
    if (running != null) {
      return running;
    }
    late final Future<_RefreshOutcome> refresh;
    refresh = _runRefresh(_authSession).whenComplete(() {
      // A session change may already have replaced it with the next user's.
      if (identical(_refreshInFlight, refresh)) {
        _refreshInFlight = null;
      }
    });
    return _refreshInFlight = refresh;
  }

  Future<_RefreshOutcome> _runRefresh(int session) async {
    String? token;
    try {
      token = await _onRefreshAccessToken?.call();
    } catch (error) {
      if (kDebugMode) {
        debugPrint('[API AUTH] Token refresh failed, not refused: $error');
      }
      // An explicit sign-out or a user switch while the refresh ran is not a
      // failure the user needs to hear about.
      if (_authSession != session) {
        return const _Superseded();
      }
      return _Unavailable(
        error is ApiException
            ? error
            : ApiException(
                'Could not renew your session right now. Please check your '
                'connection and try again.',
              ),
      );
    }

    // A token refreshed for the old user must not be installed for the new
    // one.
    if (_authSession != session) {
      return const _Superseded();
    }

    if (token == null) {
      return const _Refused();
    }
    if (token != _authToken) {
      replaceAuthToken(token);
    }
    return const _Refreshed();
  }

  /// Sign out after an unrecoverable 401 on a request sent under the current
  /// session. Every 401 of one session shares one sign-out, however many
  /// arrive at once (todo 498). A request marked [skipSessionExpiryKey]
  /// never signs out.
  Future<void> _expireSession(RequestOptions options) async {
    if (options.extra[skipSessionExpiryKey] == true) {
      if (kDebugMode) {
        debugPrint(
          '[API AUTH] 401 on a sign-out-exempt request; not signed out',
        );
      }
      return;
    }
    final session = options.extra[_sentSessionKey] as int?;
    if (session == _expiringSession) {
      return _expiryInFlight ?? Future<void>.value();
    }
    if (kDebugMode) {
      debugPrint('[API ERROR] 401 Unauthorized - session expired');
    }
    _expiringSession = session;
    final expiry = _handleSessionExpired();
    _expiryInFlight = expiry;
    await expiry;
    if (identical(_expiryInFlight, expiry)) {
      _expiryInFlight = null;
    }
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

  /// Set or clear the bearer token for a sign-in or sign-out.
  ///
  /// Either way this starts a new session (todo 498): a 401 on a request sent
  /// before it is never refreshed, re-sent with this token, or turned into a
  /// sign-out. A refreshed token for the same user goes through
  /// [replaceAuthToken] instead.
  void setAuthToken(String? token) {
    _authToken = token;
    _authEpoch++;
    if (!_replacingToken) {
      _startNewSession();
    }
  }

  /// Install a token for the session already under way, keeping it: a
  /// refreshed token for the same user, so the 401s waiting on the refresh
  /// re-send their requests with it, or the JWT of a sign-in that opened its
  /// session with `setAuthToken(null)` first.
  void replaceAuthToken(String token) {
    _replacingToken = true;
    try {
      setAuthToken(token);
    } finally {
      _replacingToken = false;
    }
  }

  /// End the signed-in session but keep the token for now. `signOut()` calls
  /// this first: its FCM clear still needs the bearer, but from here on a
  /// refresh that was running, or a 401 on a request already sent, is
  /// overtaken by the sign-out and never reports an expired session (todo
  /// 498).
  void endSession() => _startNewSession();

  void _startNewSession() {
    _authSession++;
    _refreshInFlight = null;
  }

  /// Register a callback that clears local auth state after failed recovery.
  void setSessionExpiredHandler(Future<void> Function()? onSessionExpired) {
    _onSessionExpired = onSessionExpired;
  }

  /// Register the callback that gets a fresh access token after a 401.
  ///
  /// It returns the new token, or `null` only when the server definitely
  /// refused the session, which signs the user out. It THROWS for anything
  /// transient (offline, timeout, 5xx, 429): the user stays signed in, the
  /// request fails with that error, and the next 401 tries again (todo 498).
  /// Unset, a 401 signs out directly.
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
    // A 401 whose refresh failed for a transient reason carries that
    // failure, already in its final form (todo 498).
    final carried = e.error;
    if (carried is ApiException) {
      return carried;
    }
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

/// What one token refresh came to, for every 401 waiting on it (todo 498).
sealed class _RefreshOutcome {
  const _RefreshOutcome();
}

/// A new token is installed: re-send the request.
final class _Refreshed extends _RefreshOutcome {
  const _Refreshed();
}

/// The server definitely refused the session: sign out.
final class _Refused extends _RefreshOutcome {
  const _Refused();
}

/// The refresh failed for a reason that may pass (offline, timeout, 5xx,
/// 429): stay signed in and fail the request with [reason].
final class _Unavailable extends _RefreshOutcome {
  const _Unavailable(this.reason);

  final ApiException reason;
}

/// A sign-out or user switch overtook the refresh: neither.
final class _Superseded extends _RefreshOutcome {
  const _Superseded();
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
