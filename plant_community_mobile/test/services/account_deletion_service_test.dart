import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/account_deletion_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// Answers `post` with [response] or throws [error], and records each call.
class _FakeApi extends ApiService {
  _FakeApi() : super(baseUrl: 'http://fake.local');

  Exception? error;
  int status = 202;
  final List<({String path, Object? data, Options? options})> posts = [];

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    void Function(int sent, int total)? onSendProgress,
    Duration? receiveTimeout,
  }) async {
    posts.add((path: path, data: data, options: options));
    final e = error;
    if (e != null) throw e;
    return Response<dynamic>(
      requestOptions: RequestOptions(path: path),
      statusCode: status,
      data: {'status': 'scheduled'},
    );
  }
}

void main() {
  late _FakeApi api;
  late AccountDeletionService service;

  setUp(() {
    api = _FakeApi();
    service = AccountDeletionService(api);
  });

  test('posts the fresh Firebase token to account/delete/', () async {
    await service.deleteAccount('fresh-id-token');

    expect(api.posts, hasLength(1));
    expect(api.posts.single.path, '/auth/account/delete/');
    expect(api.posts.single.data, {'firebase_token': 'fresh-id-token'});
  });

  test('a refused 401 is not turned into "Your session expired": the '
      'screen signs out itself, so the expiry flow is skipped, but the token '
      'refresh still runs', () async {
    await service.deleteAccount('t');

    final extra = api.posts.single.options?.extra ?? const {};
    expect(extra[ApiService.skipSessionExpiryKey], isTrue);
    expect(extra[ApiService.skipAuthRefreshKey], isNot(isTrue));
  });

  test('202 is scheduled', () async {
    final result = await service.deleteAccount('t');

    expect(result, isA<AccountDeletionScheduled>());
  });

  test('403 reauth_required asks the user to confirm again', () async {
    api.error = ApiException(
      'Sign in again to delete your account.',
      statusCode: 403,
      code: 'reauth_required',
    );

    final result = await service.deleteAccount('t');

    expect(result, isA<AccountDeletionFailed>());
    expect((result as AccountDeletionFailed).message, reauthAgainMessage);
  });

  test('409 contact_support shows the server message', () async {
    api.error = ApiException(
      'Your account has an open moderation case. Contact support.',
      statusCode: 409,
      code: 'contact_support',
    );

    final result = await service.deleteAccount('t');

    expect(
      (result as AccountDeletionFailed).message,
      'Your account has an open moderation case. Contact support.',
    );
  });

  test('a 409 page that is not our JSON gets the fallback, not its text', () {
    api.error = ApiException(
      '<html>Conflict</html>',
      statusCode: 409,
      unstructured: true,
    );

    expect(
      service.deleteAccount('t'),
      completion(
        isA<AccountDeletionFailed>().having(
          (f) => f.message,
          'message',
          contactSupportFallbackMessage,
        ),
      ),
    );
  });

  test('503 verifier_unavailable says to try again in a few minutes', () async {
    api.error = ApiException(
      'The server is temporarily unavailable. Please try again shortly.',
      statusCode: 503,
      code: 'verifier_unavailable',
    );

    final result = await service.deleteAccount('t');

    expect((result as AccountDeletionFailed).message, tryAgainLaterMessage);
  });

  test('401 is signed out, not an error', () async {
    // Ruling R15: once a deletion is scheduled the account is inactive, so a
    // second device's JWT is refused.
    api.error = ApiException(
      'Your session has expired. Please sign in again.',
      statusCode: 401,
    );

    final result = await service.deleteAccount('t');

    expect(result, isA<AccountDeletionSignedOut>());
  });

  test('a network failure says the user is offline', () async {
    api.error = ApiException(
      'No internet connection. Please check your network.',
      connectivity: true,
    );

    final result = await service.deleteAccount('t');

    expect((result as AccountDeletionFailed).message, offlineMessage);
  });

  for (final (name, error) in [
    (
      'a refresh that could not run (session_refresh_unavailable)',
      ApiException('Could not renew', code: sessionRefreshUnavailableCode),
    ),
    ('a cancelled request', ApiException('Request was cancelled')),
  ]) {
    test('$name is not "offline"', () async {
      api.error = error;

      final result = await service.deleteAccount('t');

      expect((result as AccountDeletionFailed).message, tryAgainLaterMessage);
    });
  }

  test('any other failure is the generic try-later line', () async {
    api.error = ApiException('Bad request', statusCode: 400);

    final result = await service.deleteAccount('t');

    expect((result as AccountDeletionFailed).message, tryAgainLaterMessage);
  });
}
