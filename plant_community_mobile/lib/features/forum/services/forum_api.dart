import 'package:dio/dio.dart' show Options;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../services/api_service.dart';
import '../models/models.dart';

/// HTTP contract for the Wagtail forum REST API (`/api/v1/forum/...`).
///
/// Defined as an interface so tests can inject a fake (the app's convention is
/// to override the provider, not mock the transport). [HttpForumApi] is the
/// dio-backed production implementation.
abstract class ForumApi {
  Future<List<ForumBoard>> fetchBoards();

  /// First page (when [cursorUrl] is null) or a subsequent page (pass the
  /// absolute `next` URL from a prior [CursorPage]).
  Future<CursorPage<ForumTopicListItem>> fetchTopics({
    required String boardSlug,
    String? sort,
    String? cursorUrl,
  });

  Future<ForumTopicDetail> fetchTopicDetail(int topicId);

  Future<CursorPage<ForumPost>> fetchPosts({
    required int topicId,
    String? cursorUrl,
  });

  /// One page of the `/sync/` delta feed. First call: omit [since]/[sinceId].
  Future<ForumSyncPage> sync({
    DateTime? since,
    int? sinceId,
    String? boardSlug,
  });

  Future<CreateTopicResult> createTopic({
    required String boardSlug,
    required String title,
    required String slug,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  });

  Future<CreateReplyResult> createReply({
    required int topicId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  });

  Future<ReactionToggleResult> toggleReaction({
    required int postId,
    required String type,
    required String idempotencyKey,
  });

  /// Subscribe/unsubscribe the authenticated user to a topic. Both are
  /// idempotent server-side; returns the resulting `subscribed` state.
  Future<bool> subscribeToTopic(int topicId);
  Future<bool> unsubscribeFromTopic(int topicId);

  /// First page (when [cursorUrl] is null) or a subsequent page (pass the
  /// absolute `next` URL from a prior [CursorPage]) of the user's
  /// notifications, newest first.
  Future<CursorPage<ForumNotification>> fetchNotifications({String? cursorUrl});

  Future<int> fetchUnreadNotificationCount();

  /// Mark notifications read. Omitting [ids] marks ALL unread notifications
  /// read; an empty list marks none. Returns the number of rows updated.
  Future<int> markNotificationsRead({List<int>? ids});
}

/// The reaction types the backend accepts (`Reaction.REACTION_CHOICES`). MUST
/// stay in sync with the server; a backend drift-guard test enforces the same
/// on the web client.
const List<String> forumReactionTypes = ['like', 'love', 'helpful', 'thanks'];

/// dio-backed [ForumApi]. All read GETs are public; writes attach the
/// `Idempotency-Key` header so a mobile retry cannot create a duplicate.
class HttpForumApi implements ForumApi {
  HttpForumApi(this._api);

  final ApiService _api;

  static const String _idempotencyHeader = 'Idempotency-Key';

  Options _idempotent(String key) =>
      Options(headers: {_idempotencyHeader: key});

  @override
  Future<List<ForumBoard>> fetchBoards() async {
    final resp = await _api.get('/forum/boards/');
    final data = resp.data as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ForumBoard.fromJson)
        .toList(growable: false);
  }

  @override
  Future<CursorPage<ForumTopicListItem>> fetchTopics({
    required String boardSlug,
    String? sort,
    String? cursorUrl,
  }) async {
    final resp = cursorUrl != null
        ? await _api.get(cursorUrl)
        : await _api.get(
            '/forum/boards/$boardSlug/topics/',
            queryParameters: sort != null ? {'sort': sort} : null,
          );
    return CursorPage.fromJson(
      resp.data as Map<String, dynamic>,
      ForumTopicListItem.fromJson,
    );
  }

  @override
  Future<ForumTopicDetail> fetchTopicDetail(int topicId) async {
    final resp = await _api.get('/forum/topics/$topicId/');
    return ForumTopicDetail.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<CursorPage<ForumPost>> fetchPosts({
    required int topicId,
    String? cursorUrl,
  }) async {
    final resp = cursorUrl != null
        ? await _api.get(cursorUrl)
        : await _api.get('/forum/topics/$topicId/posts/');
    return CursorPage.fromJson(
      resp.data as Map<String, dynamic>,
      ForumPost.fromJson,
    );
  }

  @override
  Future<ForumSyncPage> sync({
    DateTime? since,
    int? sinceId,
    String? boardSlug,
  }) async {
    final qp = <String, dynamic>{};
    if (since != null) qp['since'] = since.toUtc().toIso8601String();
    if (sinceId != null) qp['since_id'] = sinceId;
    if (boardSlug != null) qp['board'] = boardSlug;
    final resp = await _api.get(
      '/forum/sync/',
      queryParameters: qp.isEmpty ? null : qp,
    );
    return ForumSyncPage.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<CreateTopicResult> createTopic({
    required String boardSlug,
    required String title,
    required String slug,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    final resp = await _api.post(
      '/forum/boards/$boardSlug/topics/',
      data: {'title': title, 'slug': slug, 'body': body},
      options: _idempotent(idempotencyKey),
    );
    return CreateTopicResult.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<CreateReplyResult> createReply({
    required int topicId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    final resp = await _api.post(
      '/forum/topics/$topicId/posts/',
      data: {'body': body},
      options: _idempotent(idempotencyKey),
    );
    return CreateReplyResult.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<ReactionToggleResult> toggleReaction({
    required int postId,
    required String type,
    required String idempotencyKey,
  }) async {
    final resp = await _api.post(
      '/forum/posts/$postId/reactions/',
      data: {'type': type},
      options: _idempotent(idempotencyKey),
    );
    return ReactionToggleResult.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<bool> subscribeToTopic(int topicId) async {
    final resp = await _api.post('/forum/topics/$topicId/subscription/');
    return (resp.data as Map<String, dynamic>)['subscribed'] as bool? ?? true;
  }

  @override
  Future<bool> unsubscribeFromTopic(int topicId) async {
    final resp = await _api.delete('/forum/topics/$topicId/subscription/');
    return (resp.data as Map<String, dynamic>)['subscribed'] as bool? ?? false;
  }

  @override
  Future<CursorPage<ForumNotification>> fetchNotifications({
    String? cursorUrl,
  }) async {
    final resp = cursorUrl != null
        ? await _api.get(cursorUrl)
        : await _api.get('/forum/notifications/');
    return CursorPage.fromJson(
      resp.data as Map<String, dynamic>,
      ForumNotification.fromJson,
    );
  }

  @override
  Future<int> fetchUnreadNotificationCount() async {
    final resp = await _api.get('/forum/notifications/unread-count/');
    return (resp.data as Map<String, dynamic>)['count'] as int? ?? 0;
  }

  @override
  Future<int> markNotificationsRead({List<int>? ids}) async {
    final resp = await _api.post(
      '/forum/notifications/mark-read/',
      data: ids != null ? {'ids': ids} : null,
    );
    return (resp.data as Map<String, dynamic>)['updated'] as int? ?? 0;
  }
}

/// Injectable forum API client. Override in tests with a fake [ForumApi].
final forumApiProvider = Provider<ForumApi>(
  (ref) => HttpForumApi(ref.watch(apiServiceProvider)),
);
