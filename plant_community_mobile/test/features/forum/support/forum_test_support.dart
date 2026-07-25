import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
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

  /// Pages returned by successive [sync] calls (the last is repeated).
  List<ForumSyncPage> syncPages = const [];
  int _syncCursor = 0;
  final List<Map<String, Object?>> syncCalls = [];

  final List<String> createTopicKeys = [];
  final List<String> createReplyKeys = [];
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
  }) async => posts;

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
    return CreateTopicResult(id: 1, slug: slug, status: topicStatus);
  }

  @override
  Future<CreateReplyResult> createReply({
    required int topicId,
    required List<Map<String, dynamic>> body,
    required String idempotencyKey,
  }) async {
    createReplyKeys.add(idempotencyKey);
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
    canEdit: false,
    canDelete: false,
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
