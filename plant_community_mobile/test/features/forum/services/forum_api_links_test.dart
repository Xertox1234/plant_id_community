// HttpForumApi.resolveLink: where a link forum row opens (task 5).
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://fake.local', authToken: 'jwt');

  /// Location header to answer with; null = a 302 without the header.
  String? location;
  Object? error;

  /// When set, [get] waits for it: a server that is slow to answer.
  Completer<void>? gate;
  final List<String> paths = [];
  Options? lastOptions;

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    paths.add(path);
    lastOptions = options;
    await gate?.future;
    final err = error;
    if (err != null) throw err;
    return Response(
      statusCode: 302,
      headers: Headers.fromMap({
        if (location != null) 'location': [location!],
      }),
      requestOptions: RequestOptions(path: path),
    );
  }
}

ForumLink _link({
  String url = 'https://example.com/docs',
  bool track = false,
}) => ForumLink(
  id: 7,
  title: 'Docs',
  slug: 'docs',
  description: '',
  linkUrl: url,
  trackClicks: track,
);

void main() {
  late _FakeApiService transport;
  late HttpForumApi api;

  setUp(() {
    transport = _FakeApiService();
    api = HttpForumApi(transport);
  });

  test('untracked link resolves to link_url without a request', () async {
    final uri = await api.resolveLink(_link());
    expect(uri, Uri.parse('https://example.com/docs'));
    expect(transport.paths, isEmpty);
  });

  test('tracked link returns the Location of the 302', () async {
    transport.location = 'https://elsewhere.example/page';
    final uri = await api.resolveLink(_link(track: true));
    expect(uri, Uri.parse('https://elsewhere.example/page'));
    expect(transport.paths, ['/forum/links/7/go/']);
    expect(transport.lastOptions?.followRedirects, isFalse);
    expect(transport.lastOptions!.validateStatus!(302), isTrue);
    expect(transport.lastOptions!.validateStatus!(200), isFalse);
  });

  test('tracked link falls back to link_url when the go call fails', () async {
    transport.error = ApiException('boom');
    expect(
      await api.resolveLink(_link(track: true)),
      Uri.parse('https://example.com/docs'),
    );
  });

  test(
    'tracked link falls back to link_url when there is no Location',
    () async {
      expect(
        await api.resolveLink(_link(track: true)),
        Uri.parse('https://example.com/docs'),
      );
    },
  );

  test('a slow go call stops being waited for; link_url opens', () async {
    transport
      ..gate = Completer<void>()
      ..location = 'https://elsewhere.example/page';
    final slow = HttpForumApi(
      transport,
      linkGoTimeout: const Duration(milliseconds: 20),
    );
    expect(
      await slow.resolveLink(_link(track: true)),
      Uri.parse('https://example.com/docs'),
    );
    expect(transport.paths, ['/forum/links/7/go/']);
    transport.gate!.complete();
  });

  test('the default wait for the go call is short', () {
    expect(HttpForumApi.defaultLinkGoTimeout, const Duration(seconds: 3));
  });

  test('a relative Location falls back to link_url', () async {
    transport.location = '/somewhere';
    expect(
      await api.resolveLink(_link(track: true)),
      Uri.parse('https://example.com/docs'),
    );
  });

  test('a Location that is not http(s) falls back to link_url', () async {
    transport.location = 'javascript:alert(1)';
    expect(
      await api.resolveLink(_link(track: true)),
      Uri.parse('https://example.com/docs'),
    );
  });

  test('javascript: and empty urls resolve to null', () async {
    expect(await api.resolveLink(_link(url: 'javascript:alert(1)')), isNull);
    expect(await api.resolveLink(_link(url: '')), isNull);
    expect(await api.resolveLink(_link(url: 'file:///etc/passwd')), isNull);
    transport.location = 'javascript:alert(1)';
    expect(
      await api.resolveLink(_link(url: 'javascript:alert(1)', track: true)),
      isNull,
    );
  });
}
