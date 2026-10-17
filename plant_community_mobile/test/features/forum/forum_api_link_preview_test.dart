// HttpForumApi.fetchLinkPreview maps the preview endpoint's reply into the
// card model (todo 654), and turns every failure into "no card".
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// An [ApiService] answering every GET with [result] (thrown when it is an
/// exception), recording the path and query it was asked for.
class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://fake.local', authToken: 'jwt');

  Object? result;
  String? lastPath;
  Map<String, dynamic>? lastQuery;

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    lastPath = path;
    lastQuery = queryParameters;
    final result = this.result;
    if (result is Exception) throw result;
    return Response(
      data: result,
      statusCode: 200,
      requestOptions: RequestOptions(path: path),
    );
  }
}

void main() {
  const url = 'https://en.wikipedia.org/wiki/Monstera';
  late _FakeApiService transport;
  late HttpForumApi api;

  setUp(() {
    transport = _FakeApiService();
    api = HttpForumApi(transport);
  });

  Map<String, dynamic> reply({
    bool available = true,
    Object? imageUrl = 'https://upload.example/og.png',
  }) => {
    'url': url,
    'title': 'Monstera',
    'description': 'A genus of flowering plants.',
    'image_url': imageUrl,
    'site_name': 'Wikipedia',
    'domain': 'en.wikipedia.org',
    'available': available,
  };

  test('asks the preview endpoint for the URL and maps the reply', () async {
    transport.result = reply();

    final card = await api.fetchLinkPreview(url);

    expect(transport.lastPath, '/forum/link-preview/');
    expect(transport.lastQuery, {'url': url});
    expect(card, isNotNull);
    expect(card!.url, url);
    expect(card.title, 'Monstera');
    expect(card.description, 'A genus of flowering plants.');
    expect(card.siteName, 'Wikipedia');
    expect(card.domain, 'en.wikipedia.org');
    expect(card.imageUrl, 'https://upload.example/og.png');
  });

  test('keeps only an https image', () async {
    for (final image in [
      'http://upload.example/og.png',
      'javascript:x',
      null,
    ]) {
      transport.result = reply(imageUrl: image);
      final card = await api.fetchLinkPreview(url);
      expect(card, isNotNull);
      expect(card!.imageUrl, isEmpty, reason: '$image');
    }
  });

  test('available: false is no card', () async {
    transport.result = reply(available: false);

    expect(await api.fetchLinkPreview(url), isNull);
  });

  test('a throttled or failed request is no card, never an error', () async {
    for (final failure in [
      ApiException('Too many requests', statusCode: 429),
      ApiException('Server error', statusCode: 500),
      ApiException('No connection', statusCode: null),
    ]) {
      transport.result = failure;
      expect(await api.fetchLinkPreview(url), isNull);
    }
    transport.result = 'not json';
    expect(await api.fetchLinkPreview(url), isNull);
  });
}
