import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// Answers every request from memory and records the headers it was sent
/// with. [statuses] are answered in order (the last one repeats).
class _RecordingAdapter implements HttpClientAdapter {
  _RecordingAdapter({this.statuses = const [200], this.body});

  final List<int> statuses;

  /// Answered instead of `{"ok": ...}` when set.
  final Map<String, dynamic>? body;
  final List<RequestOptions> sent = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    // A snapshot: the same options object is reused by a re-send.
    sent.add(options.copyWith(headers: Map.of(options.headers)));
    final status = statuses[(sent.length - 1).clamp(0, statuses.length - 1)];
    return ResponseBody.fromString(
      jsonEncode(body ?? {'ok': status == 200}),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

const _base = 'http://api.test/api/v1';

String? _unlock(RequestOptions o) => o.headers[ApiService.forumUnlockHeader];

void main() {
  late ApiService api;
  late _RecordingAdapter adapter;

  setUp(() {
    api = ApiService(baseUrl: _base, authToken: 'jwt');
    adapter = _RecordingAdapter();
    api.dioForTesting.httpClientAdapter = adapter;
    api.setForumUnlockTokens(['t1', 't2']);
  });

  test('header is sent on /forum/ calls with auth', () async {
    await api.get('/forum/categories/');
    expect(_unlock(adapter.sent.single), 't1,t2');
  });

  test('header is not sent on /forum/sync/', () async {
    await api.get('/forum/sync/');
    expect(_unlock(adapter.sent.single), isNull);
  });

  test('header is not sent without an Authorization header', () async {
    api.setAuthToken(null);
    await api.get('/forum/categories/');
    expect(adapter.sent.single.headers['Authorization'], isNull);
    expect(_unlock(adapter.sent.single), isNull);
  });

  test('header is not sent on a request that omits its bearer', () async {
    await api.get(
      '/forum/categories/',
      options: Options(extra: {ApiService.omitAuthHeaderKey: true}),
    );
    expect(_unlock(adapter.sent.single), isNull);
  });

  test('header is not sent to non-forum paths', () async {
    await api.get('/garden/beds/');
    await api.get('/auth/user/');
    expect(adapter.sent.map(_unlock), [null, null]);
  });

  test('cursor urls (absolute) under /forum/ carry the header', () async {
    await api.get('$_base/forum/boards/care/topics/?cursor=abc');
    expect(_unlock(adapter.sent.single), 't1,t2');
  });

  test('no tokens, no header', () async {
    api.setForumUnlockTokens(const []);
    await api.get('/forum/categories/');
    expect(_unlock(adapter.sent.single), isNull);
  });

  test('at most 20 tokens are sent', () async {
    api.setForumUnlockTokens([for (var i = 0; i < 25; i++) 't$i']);
    await api.get('/forum/categories/');
    final sent = _unlock(adapter.sent.single)!.split(',');
    expect(sent, [for (var i = 0; i < 20; i++) 't$i']);
  });

  test('a reused request that carries a stale header goes out without it '
      'once the tokens are cleared', () async {
    // Retries and the 401 re-send pass the SAME RequestOptions back through
    // the interceptor: it must remove the header, not only add it.
    final options = RequestOptions(
      path: '/forum/categories/',
      baseUrl: _base,
      headers: {ApiService.forumUnlockHeader: 'stale'},
    );
    api.setForumUnlockTokens(const []);
    await api.dioForTesting.fetch<dynamic>(options);
    expect(_unlock(adapter.sent.single), isNull);
  });

  test('the 401 re-send drops a header cleared during the refresh', () async {
    adapter = _RecordingAdapter(statuses: [401, 200]);
    api.dioForTesting.httpClientAdapter = adapter;
    api.setAccessTokenRefresher(() async {
      // A sign-out-like change while the refresh runs.
      api.setForumUnlockTokens(const []);
      return 'fresh';
    });
    final response = await api.get('/forum/categories/');
    expect(response.statusCode, 200);
    expect(adapter.sent.map(_unlock), ['t1,t2', null]);
    expect(adapter.sent.last.headers['Authorization'], 'Bearer fresh');
  });

  group('HttpForumApi.unlockBoard', () {
    Future<String?> unlockWith(Map<String, dynamic> body) async {
      adapter = _RecordingAdapter(body: body);
      api.dioForTesting.httpClientAdapter = adapter;
      return HttpForumApi(api).unlockBoard('secret', 'pw');
    }

    test('returns the token', () async {
      expect(
        await unlockWith({'unlocked': true, 'unlock_token': 'tok'}),
        'tok',
      );
      expect(
        adapter.sent.single.path,
        endsWith('/forum/boards/secret/unlock/'),
      );
      expect(adapter.sent.single.method, 'POST');
    });

    test('null, empty or missing means nothing to unlock', () async {
      expect(
        await unlockWith({'unlocked': true, 'unlock_token': null}),
        isNull,
      );
      expect(await unlockWith({'unlocked': true, 'unlock_token': ''}), isNull);
      expect(await unlockWith({'unlocked': true}), isNull);
    });
  });

  test('neither a token nor the password is ever logged', () async {
    // Debug builds log every request (LogInterceptor) and many failures.
    const token = 'tok-SECRET-123';
    const password = 'pw-SECRET-456'; // pragma: allowlist secret
    final logs = <String>[];
    final previous = debugPrint;
    debugPrint = (String? message, {int? wrapWidth}) => logs.add('$message');
    addTearDown(() => debugPrint = previous);

    api.setForumUnlockTokens([token]);
    // A plain forum GET, a 401 then the re-send, and a server error.
    adapter = _RecordingAdapter(statuses: [200, 401, 200, 500]);
    api.dioForTesting.httpClientAdapter = adapter;
    api.setAccessTokenRefresher(() async => 'fresh');
    await api.get('/forum/categories/');
    await api.get('/forum/boards/care/topics/');
    await expectLater(
      api.get('/forum/categories/'),
      throwsA(isA<ApiException>()),
    );
    // A refused password.
    adapter = _RecordingAdapter(
      statuses: [400],
      body: {'error': 'Incorrect password.', 'code': 'bad_password'},
    );
    api.dioForTesting.httpClientAdapter = adapter;
    Object? refused;
    try {
      await HttpForumApi(api).unlockBoard('secret', password);
    } catch (e) {
      refused = e;
    }

    expect(adapter.sent, isNotEmpty);
    expect(logs, isNotEmpty, reason: 'the requests were logged');
    expect(refused, isNotNull);
    for (final line in [...logs, '$refused']) {
      expect(line, isNot(contains('SECRET')), reason: line);
    }
  });
}
