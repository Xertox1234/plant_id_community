import 'dart:async';

import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_image_picker.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

/// Configurable fake [ForumApi] for forum tests. Read fixtures are set as
/// fields; writes record the `Idempotency-Key` they received and can be made
/// to fail a fixed number of times to exercise retry/idempotency.
class FakeForumApi implements ForumApi {
  List<ForumBoard> boards = const [];
  ForumTopicDetail? topicDetail;
  CursorPage<ForumTopicListItem> topics = const CursorPage(items: []);
  CursorPage<ForumPost> posts = const CursorPage(items: []);

  /// A multi-page thread fixture for [fetchPosts]: page N+1 is returned when
  /// the caller's `cursorUrl` equals page N's `next`, and `cursorUrl: null`
  /// (the initial fetch, and every `refreshAfterReply` restart) always
  /// returns [postPages].first. Falls back to [posts] when empty, so every
  /// existing single-page fixture keeps working unchanged.
  List<CursorPage<ForumPost>> postPages = const [];
  final List<String?> fetchPostsCalls = [];

  /// If set, the [fetchPostsCalls]-th call to [fetchPosts] (1-indexed) throws
  /// instead of returning a page — for testing a mid-page-walk failure.
  int? throwOnFetchPostsCallNumber;

  /// Pages returned by successive [sync] calls (the last is repeated).
  List<ForumSyncPage> syncPages = const [];
  int _syncCursor = 0;
  final List<Map<String, Object?>> syncCalls = [];

  final List<String> createTopicKeys = [];
  final List<String> createReplyKeys = [];
  final List<List<Map<String, dynamic>>> createTopicBodies = [];
  final List<List<Map<String, dynamic>>> createReplyBodies = [];
  final List<String> reactionKeys = [];

  ForumModerationStatus topicStatus = ForumModerationStatus.published;
  ForumModerationStatus replyStatus = ForumModerationStatus.published;

  /// Fail the first N create-reply attempts with a 500 before succeeding.
  int failCreateReplyTimes = 0;

  ReactionToggleResult reactionResult = const ReactionToggleResult(
    reactionCounts: {'like': 1},
    reacted: true,
  );

  /// When true, [toggleReaction] throws instead of returning a result.
  bool failReactionToggle = false;

  final List<String> editPostKeys = [];
  ForumModerationStatus editStatus = ForumModerationStatus.published;

  /// When set, [editPost] throws this instead of returning a result — set an
  /// [ApiException] to test a specific status/message (e.g. a 409 frozen-
  /// topic rejection, todo 292 AC3).
  ApiException? failEditPostWith;

  final List<int> deletePostCalls = [];

  /// When set, [deletePost] throws this instead of succeeding.
  ApiException? failDeletePostWith;

  final List<String> uploadImageKeys = [];
  final List<String?> uploadImageFilePaths = [];
  ForumImageBlock uploadImageResult = const ForumImageBlock(
    id: 1,
    url: 'https://example.com/forum/images/1.jpg',
    alt: '',
    width: 800,
    height: 600,
  );

  /// When set, [uploadImage] throws this instead of returning a result.
  ApiException? failUploadImageWith;

  /// When set, [uploadImage] awaits this instead of resolving immediately —
  /// lets a test hold an upload "in flight" to assert UI state mid-upload
  /// (code review, todo 294: the Post button race).
  Completer<ForumImageBlock>? uploadImageGate;

  /// [subscribeToTopic]/[unsubscribeFromTopic] call log and failure hook.
  final List<int> subscribeCalls = [];
  final List<int> unsubscribeCalls = [];
  ApiException? failSubscriptionWith;

  /// Notification fixtures. [notificationPages] mirrors [postPages]: page
  /// N+1 is returned when [cursorUrl] equals page N's `next`; `null` always
  /// returns the first page. Falls back to [notifications] when empty.
  List<ForumNotification> notifications = const [];
  List<CursorPage<ForumNotification>> notificationPages = const [];
  final List<String?> fetchNotificationsCalls = [];
  int unreadCount = 0;
  final List<List<int>?> markReadCalls = [];
  ApiException? failMarkReadWith;

  /// [search] fixtures. [searchPages] maps a 1-based `page` number to the
  /// page returned for it; falls back to [searchResult] when empty.
  ForumSearchPage searchResult = const ForumSearchPage(
    topics: [],
    posts: [],
    topicsHasMore: false,
    postsHasMore: false,
    page: 1,
  );
  Map<int, ForumSearchPage> searchPages = const {};
  final List<Map<String, Object?>> searchCalls = [];
  ApiException? failSearchWith;

  /// When set, the Nth call to [search] (1-indexed, matching [searchCalls]'
  /// length after that call is recorded) awaits `searchGates[N-1]` instead
  /// of resolving immediately — lets a test hold two overlapping requests
  /// "in flight" and resolve them out of order (code review, todo 295: the
  /// stale-response race).
  List<Completer<ForumSearchPage>>? searchGates;

  @override
  Future<List<ForumBoard>> fetchBoards() async => boards;

  @override
  Future<ForumTopicDetail> fetchTopicDetail(int topicId) async {
    final detail = topicDetail;
    if (detail == null) {
      throw ApiException('no fixture', statusCode: 404);
    }
    return detail;
  }

  @override
  Future<CursorPage<ForumTopicListItem>> fetchTopics({
    required String boardSlug,
    String? sort,
    String? cursorUrl,
  }) async => topics;

  @override
  Future<CursorPage<ForumPost>> fetchPosts({
    required int topicId,
    String? cursorUrl,
  }) async {
    fetchPostsCalls.add(cursorUrl);
    if (fetchPostsCalls.length == throwOnFetchPostsCallNumber) {
      throw ApiException('temporary failure', statusCode: 500);
    }
    if (postPages.isEmpty) return posts;
    if (cursorUrl == null) return postPages.first;
    for (var i = 1; i < postPages.length; i++) {
      if (postPages[i - 1].next == cursorUrl) return postPages[i];
    }
    // Unrecognized cursor (shouldn't happen — the last page's `next` is
    // null, so a well-behaved caller never reaches here). Repeat the last
    // page defensively rather than throw.
    return postPages.last;
  }

  @override
  Future<ForumSyncPage> sync({
    DateTime? since,
    int? sinceId,
    String? boardSlug,
  }) async {
    syncCalls.add({'since': since, 'sinceId': sinceId, 'board': boardSlug});
    if (syncPages.isEmpty) {
      return const ForumSyncPage(topics: [], deleted: [], hasMore: false);
    }
    final index = _syncCursor < syncPages.length
        ? _syncCursor
        : syncPages.length - 1;
    _syncCursor++;
    return syncPages[index];
  }

  @override
  Future<CreateTopicResult> createTopic({
    required String boardSlug,
    required String title,
    required String slug,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    createTopicKeys.add(idempotencyKey);
    createTopicBodies.add(body);
    return CreateTopicResult(id: 1, slug: slug, status: topicStatus);
  }

  @override
  Future<CreateReplyResult> createReply({
    required int topicId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    createReplyKeys.add(idempotencyKey);
    createReplyBodies.add(body);
    if (createReplyKeys.length <= failCreateReplyTimes) {
      throw ApiException('temporary failure', statusCode: 500);
    }
    return CreateReplyResult(id: 2, status: replyStatus);
  }

  @override
  Future<ReactionToggleResult> toggleReaction({
    required int postId,
    required String type,
    required String idempotencyKey,
  }) async {
    reactionKeys.add(idempotencyKey);
    if (failReactionToggle) {
      throw ApiException('rate limited', statusCode: 429);
    }
    return reactionResult;
  }

  @override
  Future<EditPostResult> editPost({
    required int postId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    editPostKeys.add(idempotencyKey);
    final fail = failEditPostWith;
    if (fail != null) throw fail;
    return EditPostResult(
      post: post(
        id: postId,
        body: parseForumBody(body),
        canEdit: true,
        canDelete: true,
      ),
      status: editStatus,
    );
  }

  @override
  Future<void> deletePost({required int postId}) async {
    deletePostCalls.add(postId);
    final fail = failDeletePostWith;
    if (fail != null) throw fail;
  }

  @override
  Future<ForumImageBlock> uploadImage({
    required String filePath,
    String? alt,
    required String idempotencyKey,
  }) async {
    uploadImageKeys.add(idempotencyKey);
    uploadImageFilePaths.add(filePath);
    final gate = uploadImageGate;
    if (gate != null) return gate.future;
    final fail = failUploadImageWith;
    if (fail != null) throw fail;
    return uploadImageResult;
  }

  @override
  Future<ForumSearchPage> search({
    required String q,
    String? board,
    int page = 1,
    bool semantic = false,
  }) async {
    searchCalls.add({
      'q': q,
      'board': board,
      'page': page,
      'semantic': semantic,
    });
    final gates = searchGates;
    if (gates != null && searchCalls.length <= gates.length) {
      return gates[searchCalls.length - 1].future;
    }
    final fail = failSearchWith;
    if (fail != null) throw fail;
    return searchPages[page] ?? searchResult;
  }

  @override
  Future<bool> subscribeToTopic(int topicId) async {
    subscribeCalls.add(topicId);
    if (failSubscriptionWith != null) throw failSubscriptionWith!;
    return true;
  }

  @override
  Future<bool> unsubscribeFromTopic(int topicId) async {
    unsubscribeCalls.add(topicId);
    if (failSubscriptionWith != null) throw failSubscriptionWith!;
    return false;
  }

  @override
  Future<CursorPage<ForumNotification>> fetchNotifications({
    String? cursorUrl,
  }) async {
    fetchNotificationsCalls.add(cursorUrl);
    if (notificationPages.isEmpty) {
      return CursorPage(items: notifications);
    }
    if (cursorUrl == null) return notificationPages.first;
    for (var i = 1; i < notificationPages.length; i++) {
      if (notificationPages[i - 1].next == cursorUrl) {
        return notificationPages[i];
      }
    }
    return notificationPages.last;
  }

  @override
  Future<int> fetchUnreadNotificationCount() async => unreadCount;

  @override
  Future<int> markNotificationsRead({List<int>? ids}) async {
    markReadCalls.add(ids);
    if (failMarkReadWith != null) throw failMarkReadWith!;
    final updated = ids?.length ?? unreadCount;
    unreadCount = (unreadCount - updated).clamp(0, unreadCount);
    return updated;
  }
}

/// A test [AuthService] that returns a fixed [AuthState] without touching
/// Firebase. Use via `authServiceProvider.overrideWith(...)`.
class FakeAuthService extends AuthService {
  FakeAuthService({required this.loggedIn});
  final bool loggedIn;

  @override
  AuthState build() =>
      loggedIn ? const AuthState(jwtToken: 'test-jwt') : const AuthState();
}

/// Build a [ForumAuthor] fixture.
ForumAuthor author({
  String username = 'alice',
  String? displayName,
  int? trustLevel = 2,
}) {
  return ForumAuthor(
    username: username,
    displayName: displayName ?? username,
    trustLevel: trustLevel,
  );
}

/// Build a [ForumPost] fixture.
ForumPost post({
  int id = 1,
  int topicId = 10,
  List<ForumBodyBlock> body = const [ParagraphBlock('Hello')],
  bool isPending = false,
  Map<String, int> reactionCounts = const {},
  List<String> reacted = const [],
  bool canEdit = false,
  bool canDelete = false,
}) {
  return ForumPost(
    id: id,
    topicId: topicId,
    author: author(),
    body: body,
    createdAt: DateTime(2026, 1, 1),
    isOpeningPost: id == 1,
    isPending: isPending,
    reactionCounts: reactionCounts,
    reacted: reacted,
    canEdit: canEdit,
    canDelete: canDelete,
    canReport: false,
  );
}

/// Build a [ForumTopicListItem] fixture.
ForumTopicListItem topic({int id = 10, String title = 'Sample topic'}) {
  return ForumTopicListItem(
    id: id,
    title: title,
    slug: 'sample-topic',
    author: author(),
    isPinned: false,
    isClosed: false,
    locked: false,
    replyCount: 3,
    viewCount: 12,
    lastPostAt: DateTime(2026, 1, 2),
    lastPostAuthor: author(),
    isUnread: false,
  );
}

/// Build a [ForumTopicDetail] fixture.
ForumTopicDetail topicDetail({int id = 10, String title = 'Sample topic'}) {
  return ForumTopicDetail(
    id: id,
    title: title,
    slug: 'sample-topic',
    board: const ForumTopicBoardRef(id: 1, slug: 'general', title: 'General'),
    author: author(),
    isPinned: false,
    isClosed: false,
    locked: false,
    replyCount: 3,
    viewCount: 12,
    createdAt: DateTime(2026, 1, 1),
    lastPostAt: DateTime(2026, 1, 2),
    lastPostAuthor: author(),
    openingPostId: 1,
    isSubscribed: false,
  );
}

/// Build a [ForumNotification] fixture.
ForumNotification notification({
  int id = 1,
  String verb = 'reply',
  int? topicId = 10,
  String topicTitle = 'Sample topic',
  int? postId,
  DateTime? readAt,
}) {
  return ForumNotification(
    id: id,
    verb: verb,
    actor: author(),
    topic: topicId == null
        ? null
        : ForumNotificationTopicRef(
            id: topicId,
            slug: 'sample-topic',
            title: topicTitle,
            boardId: 1,
            boardSlug: 'general',
          ),
    postId: postId,
    createdAt: DateTime(2026, 1, 1),
    readAt: readAt,
  );
}

/// Build a [ForumTopicStub] fixture.
ForumTopicStub stub({int id = 1, String title = 'Stub', DateTime? updatedAt}) {
  return ForumTopicStub(
    id: id,
    slug: 'stub-$id',
    title: title,
    updatedAt: updatedAt ?? DateTime.utc(2026, 1, 1),
  );
}

/// A test [ForumImagePicker] that returns a fixed path (or `null` for a
/// cancelled pick) without touching platform channels.
class FakeForumImagePicker implements ForumImagePicker {
  FakeForumImagePicker({this.nextPath, this.throwOnPick});
  String? nextPath;

  /// When set, [pickImagePath] throws this instead of returning
  /// [nextPath] — simulates a platform-level failure (e.g. a denied
  /// photo-library permission), which is a real, reachable case distinct
  /// from an upload rejection (code review, todo 294).
  Object? throwOnPick;

  final List<int> pickCalls = [];

  @override
  Future<String?> pickImagePath() async {
    pickCalls.add(pickCalls.length);
    final err = throwOnPick;
    if (err != null) throw err;
    return nextPath;
  }
}
