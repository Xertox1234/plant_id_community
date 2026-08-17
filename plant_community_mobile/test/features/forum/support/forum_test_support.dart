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
