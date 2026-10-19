// The REST reads live forum replies need (slice 4): the topic peek read and
// the single-post refetch an event triggers.
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
  late _FakeApiService transport;
  late HttpForumApi api;

  setUp(() {
    transport = _FakeApiService();
    api = HttpForumApi(transport);
  });

  test('fetchTopicDetail(peek: true) sends peek=1', () async {
    transport.result = <String, dynamic>{'id': 12, 'reply_count': 4};

    final detail = await api.fetchTopicDetail(12, peek: true);

    expect(transport.lastPath, '/forum/topics/12/');
    expect(transport.lastQuery, {'peek': '1'});
    expect(detail.replyCount, 4);

    await api.fetchTopicDetail(12);
    expect(transport.lastQuery, isNull);
  });

  test('fetchPost maps the post', () async {
    transport.result = <String, dynamic>{
      'id': 55,
      'topic_id': 12,
      'body': [
        {'type': 'paragraph', 'value': 'Hi'},
      ],
    };

    final post = await api.fetchPost(55);

    expect(transport.lastPath, '/forum/posts/55/');
    expect(post, isNotNull);
    expect(post!.id, 55);
    expect(post.topicId, 12);
  });

  test('fetchPost returns null on 404', () async {
    transport.result = ApiException('Not found.', statusCode: 404);

    expect(await api.fetchPost(55), isNull);
  });

  test('fetchPost rethrows a 500', () async {
    transport.result = ApiException('Server error', statusCode: 500);

    expect(api.fetchPost(55), throwsA(isA<ApiException>()));
  });
}
