import 'package:dio/dio.dart' show FormData, MultipartFile, Options;
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

  /// Public forum profile for [username] (`GET /forum/users/{username}/`,
  /// `AllowAny` server-side). 404s (as an [ApiException]) for a missing or
  /// inactive user.
  Future<ForumProfile> fetchProfile(String username);

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

  /// Edit a post the caller owns (or moderates). Server-enforced ownership —
  /// callers must gate the affordance on `post.canEdit`, never re-derive it.
  /// 409 on a closed/locked topic or a locked post (todo 292 AC3).
  Future<EditPostResult> editPost({
    required int postId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  });

  /// Soft-delete a post the caller owns (or moderates). Not idempotency-key
  /// protected server-side — a repeat DELETE of an already-deleted post 404s,
  /// which is naturally idempotent enough for this action.
  Future<void> deletePost({required int postId});

  /// Upload an inline post image (4-layer validated server-side) into the
  /// forum image collection. Returns the stored image — reference its `id`
  /// from a write-shape `image` body block ([buildImageBlockBody]).
  Future<ForumImageBlock> uploadImage({
    required String filePath,
    String? alt,
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
  ///
  /// No `Idempotency-Key`: like subscribe/unsubscribe, this is naturally
  /// idempotent server-side (a retry just finds fewer/no unread rows left to
  /// update) and creates nothing that could duplicate. A retry's `updated`
  /// count may differ from the original call's, but callers discard it —
  /// `NotificationsFeed.markRead` re-derives read state from the caller's
  /// own `ids` and refreshes the badge via `unreadNotificationCountProvider`
  /// invalidation, not from this return value.
  Future<int> markNotificationsRead({List<int>? ids});

  /// Full-text search across topics and posts. Offset-paginated via [page]
  /// (1-based) — NOT the cursor pattern the other list endpoints use, since
  /// the response has no `results`/`next` URL, just two independently-
  /// flagged sections sharing one page cursor. [semantic] opts into the
  /// premium "related topics" section (`?semantic=1`); the response reports
  /// [ForumSearchPage.semanticStatus] rather than erroring when it's
  /// unavailable (feature-flagged off) or gated (non-premium caller).
  Future<ForumSearchPage> search({
    required String q,
    String? board,
    int page = 1,
    bool semantic = false,
  });

  // --- Direct messages (todo 339) -----------------------------------------

  /// The caller's DM inbox, most recent activity first. First page when
  /// [cursorUrl] is null; pass the absolute `next` URL for a later page.
  Future<CursorPage<ForumConversation>> fetchConversations({String? cursorUrl});

  /// Number of conversations holding unread messages (NOT unread messages),
  /// for the inbox badge.
  Future<int> fetchUnreadConversationCount();

  /// The 1:1 conversation with [username], or `null` when none exists yet —
  /// the backend 404s for "no conversation", an unknown user AND a blocked
  /// pair alike, so a null here is "nothing to show", never an error. A
  /// blocked pair only surfaces as a 403 on [sendMessage].
  Future<ForumConversation?> fetchConversationWith(String username);

  /// Messages in a conversation, **newest first** (page via `next` for older
  /// ones). Reading marks the conversation read server-side, so callers
  /// should refresh the unread badge afterwards.
  Future<CursorPage<ForumDirectMessage>> fetchMessages({
    required int conversationId,
    String? cursorUrl,
  });

  /// Send [body] to [username], creating the conversation on first send.
  /// 403 = blocked pair ("You cannot message this user."), 400 = empty /
  /// spam-screened (the server's own reason), 404 = unknown user. Carries an
  /// `Idempotency-Key` — the backend replays a same-key retry.
  Future<ForumDirectMessage> sendMessage({
    required String username,
    required String body,
    required String idempotencyKey,
  });

  /// Report a message the OTHER participant sent, for moderator review.
  /// [reason] is one of [forumReportReasons]; [detail] is optional free
  /// text (≤ 280 chars). Reporting your own message is a 400.
  Future<void> reportMessage({
    required int messageId,
    required String reason,
    String? detail,
    required String idempotencyKey,
  });

  // --- Safety (todo 341 wave 1) --------------------------------------------

  /// Report a post for moderator review (`POST /forum/posts/{id}/reports/`).
  /// [reason] is one of [forumReportReasons]; [detail] is optional free text
  /// (≤ 280 chars). 400 for your own post (callers gate on `post.canReport`);
  /// reporting the same post twice is a server-side no-op, not an error.
  /// Carries an `Idempotency-Key` — the backend replays a same-key retry.
  Future<void> reportPost({
    required int postId,
    required String reason,
    String? detail,
    required String idempotencyKey,
  });

  /// Block / unblock [username] for the caller. Both are idempotent
  /// server-side (`UserBlockView` reads no `Idempotency-Key`, so none is
  /// sent — same reasoning as [subscribeToTopic]); 400 on self-block; 404
  /// for a missing/inactive user. Returns the resulting `blocked` state.
  Future<bool> blockUser(String username);
  Future<bool> unblockUser(String username);

  // --- Thread experience (todo 341 wave 2) ---------------------------------

  /// Accept [postId] as [topicId]'s answer (`POST /forum/topics/{id}/
  /// solution/`). Topic author or moderator only (403); the post must be a
  /// live reply on THIS topic and not the opening post (422). Carries an
  /// `Idempotency-Key` (the backend replays a same-key/same-payload retry
  /// and 422s a same-key/different-payload one).
  Future<ForumSolutionResult> markSolution({
    required int topicId,
    required int postId,
    required String idempotencyKey,
  });

  /// Clear [topicId]'s accepted answer. Idempotent server-side (a 200 no-op
  /// on an unsolved topic) and the view reads no `Idempotency-Key`.
  Future<ForumSolutionResult> clearSolution(int topicId);

  /// Bookmark / unbookmark a topic for the caller. Both idempotent
  /// server-side and key-less (`TopicBookmarkView` reads no
  /// `Idempotency-Key`); returns the resulting `bookmarked` state.
  Future<bool> bookmarkTopic(int topicId);
  Future<bool> unbookmarkTopic(int topicId);

  /// The caller's bookmarked topics, most recently bookmarked first
  /// (`GET /forum/me/bookmarks/`, `TopicListSerializer` rows). First page
  /// when [cursorUrl] is null; pass the absolute `next` URL for a later one.
  Future<CursorPage<ForumTopicListItem>> fetchBookmarks({String? cursorUrl});

  /// A post's edit history, newest first (`GET /forum/posts/{id}/
  /// revisions/`, unpaginated). Author or moderator only — a 403 is an
  /// EXPECTED state, not a failure: once anyone other than the author has
  /// edited the post, its history is moderator-only (earlier revisions still
  /// hold whatever that edit removed).
  Future<List<ForumPostRevision>> fetchPostRevisions(int postId);

  /// One revision's body, in the same block shape as the live post.
  Future<ForumPostRevisionDetail> fetchPostRevision({
    required int postId,
    required int revisionId,
  });
}

/// A report reason the backend accepts (`Report.REASON_CHOICES`), with its
/// user-facing label. MUST stay in sync with the server.
class ForumReportReason {
  const ForumReportReason(this.value, this.label);
  final String value;
  final String label;
}

/// The report reasons the backend accepts, in display order.
const List<ForumReportReason> forumReportReasons = [
  ForumReportReason('spam', 'Spam'),
  ForumReportReason('abuse', 'Abuse'),
  ForumReportReason('off_topic', 'Off topic'),
  ForumReportReason('other', 'Other'),
];

/// The reaction types the backend accepts (`Reaction.REACTION_CHOICES`). MUST
/// stay in sync with the server; a backend drift-guard test enforces the same
/// on the web client.
const List<String> forumReactionTypes = ['like', 'love', 'helpful', 'thanks'];

/// dio-backed [ForumApi]. All read GETs are public; writes attach the
/// `Idempotency-Key` header so a mobile retry cannot create a duplicate —
/// except the naturally-idempotent ones (see [subscribeToTopic]/
/// [unsubscribeFromTopic]/[markNotificationsRead]'s own docs).
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
  Future<ForumProfile> fetchProfile(String username) async {
    final resp = await _api.get('/forum/users/$username/');
    return ForumProfile.fromJson(resp.data as Map<String, dynamic>);
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

  @override
  Future<EditPostResult> editPost({
    required int postId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    final resp = await _api.patch(
      '/forum/posts/$postId/',
      data: {'body': body},
      options: _idempotent(idempotencyKey),
    );
    return EditPostResult.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<void> deletePost({required int postId}) async {
    await _api.delete('/forum/posts/$postId/');
  }

  @override
  Future<ForumImageBlock> uploadImage({
    required String filePath,
    String? alt,
    required String idempotencyKey,
  }) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(
        filePath,
        filename: filePath.split('/').last,
      ),
      if (alt != null && alt.isNotEmpty) 'alt': alt,
    });
    final resp = await _api.post(
      '/forum/images/',
      data: formData,
      options: _idempotent(idempotencyKey),
    );
    return ForumImageBlock.fromUploadResponse(
      resp.data as Map<String, dynamic>,
    );
  }

  @override
  Future<ForumSearchPage> search({
    required String q,
    String? board,
    int page = 1,
    bool semantic = false,
  }) async {
    final qp = <String, dynamic>{'q': q, 'page': page};
    if (board != null) qp['board'] = board;
    if (semantic) qp['semantic'] = 1;
    final resp = await _api.get('/forum/search/', queryParameters: qp);
    return ForumSearchPage.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<CursorPage<ForumConversation>> fetchConversations({
    String? cursorUrl,
  }) async {
    final resp = cursorUrl != null
        ? await _api.get(cursorUrl)
        : await _api.get('/forum/conversations/');
    return CursorPage.fromJson(
      resp.data as Map<String, dynamic>,
      ForumConversation.fromJson,
    );
  }

  @override
  Future<int> fetchUnreadConversationCount() async {
    final resp = await _api.get('/forum/conversations/unread-count/');
    return (resp.data as Map<String, dynamic>)['count'] as int? ?? 0;
  }

  @override
  Future<ForumConversation?> fetchConversationWith(String username) async {
    try {
      final resp = await _api.get('/forum/conversations/with/$username/');
      return ForumConversation.fromJson(resp.data as Map<String, dynamic>);
    } on ApiException catch (e) {
      if (e.statusCode == 404) return null;
      rethrow;
    }
  }

  @override
  Future<CursorPage<ForumDirectMessage>> fetchMessages({
    required int conversationId,
    String? cursorUrl,
  }) async {
    final resp = cursorUrl != null
        ? await _api.get(cursorUrl)
        : await _api.get('/forum/conversations/$conversationId/messages/');
    return CursorPage.fromJson(
      resp.data as Map<String, dynamic>,
      ForumDirectMessage.fromJson,
    );
  }

  @override
  Future<ForumDirectMessage> sendMessage({
    required String username,
    required String body,
    required String idempotencyKey,
  }) async {
    final resp = await _api.post(
      '/forum/users/$username/messages/',
      data: {'body': body},
      options: _idempotent(idempotencyKey),
    );
    return ForumDirectMessage.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<void> reportMessage({
    required int messageId,
    required String reason,
    String? detail,
    required String idempotencyKey,
  }) async {
    await _api.post(
      '/forum/messages/$messageId/report/',
      data: {
        'reason': reason,
        if (detail != null && detail.isNotEmpty) 'detail': detail,
      },
      options: _idempotent(idempotencyKey),
    );
  }

  @override
  Future<void> reportPost({
    required int postId,
    required String reason,
    String? detail,
    required String idempotencyKey,
  }) async {
    await _api.post(
      '/forum/posts/$postId/reports/',
      data: {
        'reason': reason,
        if (detail != null && detail.isNotEmpty) 'detail': detail,
      },
      options: _idempotent(idempotencyKey),
    );
  }

  @override
  Future<bool> blockUser(String username) async {
    final resp = await _api.post('/forum/users/$username/block/');
    return (resp.data as Map<String, dynamic>)['blocked'] as bool? ?? true;
  }

  @override
  Future<bool> unblockUser(String username) async {
    final resp = await _api.delete('/forum/users/$username/block/');
    return (resp.data as Map<String, dynamic>)['blocked'] as bool? ?? false;
  }

  @override
  Future<ForumSolutionResult> markSolution({
    required int topicId,
    required int postId,
    required String idempotencyKey,
  }) async {
    final resp = await _api.post(
      '/forum/topics/$topicId/solution/',
      data: {'post_id': postId},
      options: _idempotent(idempotencyKey),
    );
    return ForumSolutionResult.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<ForumSolutionResult> clearSolution(int topicId) async {
    final resp = await _api.delete('/forum/topics/$topicId/solution/');
    return ForumSolutionResult.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<bool> bookmarkTopic(int topicId) async {
    final resp = await _api.post('/forum/topics/$topicId/bookmark/');
    return (resp.data as Map<String, dynamic>)['bookmarked'] as bool? ?? true;
  }

  @override
  Future<bool> unbookmarkTopic(int topicId) async {
    final resp = await _api.delete('/forum/topics/$topicId/bookmark/');
    return (resp.data as Map<String, dynamic>)['bookmarked'] as bool? ?? false;
  }

  @override
  Future<CursorPage<ForumTopicListItem>> fetchBookmarks({
    String? cursorUrl,
  }) async {
    final resp = cursorUrl != null
        ? await _api.get(cursorUrl)
        : await _api.get('/forum/me/bookmarks/');
    return CursorPage.fromJson(
      resp.data as Map<String, dynamic>,
      ForumTopicListItem.fromJson,
    );
  }

  @override
  Future<List<ForumPostRevision>> fetchPostRevisions(int postId) async {
    final resp = await _api.get('/forum/posts/$postId/revisions/');
    return (resp.data as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ForumPostRevision.fromJson)
        .toList(growable: false);
  }

  @override
  Future<ForumPostRevisionDetail> fetchPostRevision({
    required int postId,
    required int revisionId,
  }) async {
    final resp = await _api.get('/forum/posts/$postId/revisions/$revisionId/');
    return ForumPostRevisionDetail.fromJson(resp.data as Map<String, dynamic>);
  }
}

/// Injectable forum API client. Override in tests with a fake [ForumApi].
final forumApiProvider = Provider<ForumApi>(
  (ref) => HttpForumApi(ref.watch(apiServiceProvider)),
);
