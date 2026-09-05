import 'dart:async';

import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_image_picker.dart';
import 'package:plant_community_mobile/models/user_profile.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

/// A test [UserProfileService] that resolves to a fixed account profile
/// (the signed-in user's own `username`) without hitting `/auth/user/`.
/// Use via `userProfileServiceProvider.overrideWith(() =>
/// FakeUserProfileService(username: 'me'))` wherever a screen needs to know
/// who the current user is (the profile "Message" action, todo 339).
class FakeUserProfileService extends UserProfileService {
  FakeUserProfileService({required this.username});
  final String username;

  @override
  Future<UserProfile?> build() async => UserProfile(
    id: 1,
    username: username,
    email: '$username@example.com',
    dateJoined: DateTime(2026, 1, 1),
  );
}

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

  /// Public-profile fixture for [fetchProfile]. A single fixture that
  /// ignores the `username` argument — mirrors [topicDetail]'s convention.
  ForumProfile? profile;
  final List<String> fetchProfileCalls = [];

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

  /// DM fixtures (todo 339). [conversationPages] mirrors [postPages]: page
  /// N+1 is returned when `cursorUrl` equals page N's `next`; `null` always
  /// returns the first page. Falls back to [conversations] when empty.
  List<ForumConversation> conversations = const [];
  List<CursorPage<ForumConversation>> conversationPages = const [];
  final List<String?> fetchConversationsCalls = [];
  int unreadConversationCount = 0;

  /// Fixture for [fetchConversationWith] — `null` (the default) means "no
  /// conversation yet", which the real client maps from the backend's 404.
  /// Ignores the `username` argument, like [profile].
  ForumConversation? conversationWith;
  final List<String> fetchConversationWithCalls = [];

  /// [fetchMessages] fixtures, NEWEST FIRST like the real endpoint.
  /// [messagePages] mirrors [postPages]; falls back to [messages].
  List<ForumDirectMessage> messages = const [];
  List<CursorPage<ForumDirectMessage>> messagePages = const [];
  final List<String?> fetchMessagesCalls = [];

  /// [sendMessage] log and hooks. The returned message is authored by
  /// [senderUsername] with an id from [nextSentMessageId].
  final List<Map<String, Object?>> sendMessageCalls = [];
  final List<String> sendMessageKeys = [];
  String senderUsername = 'me';
  int nextSentMessageId = 100;
  ApiException? failSendMessageWith;

  /// When set, [sendMessage] awaits this instead of resolving immediately.
  Completer<ForumDirectMessage>? sendMessageGate;

  final List<Map<String, Object?>> reportMessageCalls = [];
  final List<String> reportMessageKeys = [];
  ApiException? failReportMessageWith;

  /// Safety fixtures (todo 341 wave 1).
  final List<Map<String, Object?>> reportPostCalls = [];
  final List<String> reportPostKeys = [];
  ApiException? failReportPostWith;
  final List<String> blockCalls = [];
  final List<String> unblockCalls = [];
  ApiException? failBlockWith;

  /// Thread-experience fixtures (todo 341 wave 2). [solutionResult] is
  /// returned by [markSolution]; [clearSolution] always returns unsolved.
  final List<Map<String, Object?>> markSolutionCalls = [];
  final List<String> markSolutionKeys = [];
  final List<int> clearSolutionCalls = [];
  ApiException? failSolutionWith;
  ForumSolutionResult? solutionResult;

  final List<int> bookmarkCalls = [];
  final List<int> unbookmarkCalls = [];
  ApiException? failBookmarkWith;

  /// [fetchBookmarks] fixtures. [bookmarkPages] mirrors [postPages]; falls
  /// back to [bookmarks].
  List<ForumTopicListItem> bookmarks = const [];
  List<CursorPage<ForumTopicListItem>> bookmarkPages = const [];
  final List<String?> fetchBookmarksCalls = [];

  /// [fetchPostRevisions]/[fetchPostRevision] fixtures — a single list and
  /// a map by revision id, both ignoring the `postId` argument (like
  /// [profile]). Unset detail ids throw a 404.
  List<ForumPostRevision> revisions = const [];
  Map<int, ForumPostRevisionDetail> revisionDetails = const {};
  final List<int> fetchRevisionsCalls = [];
  final List<int> fetchRevisionCalls = [];
  ApiException? failRevisionsWith;

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
  Future<ForumProfile> fetchProfile(String username) async {
    fetchProfileCalls.add(username);
    final fixture = profile;
    if (fixture == null) {
      throw ApiException('no fixture', statusCode: 404);
    }
    return fixture;
  }

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

  @override
  Future<CursorPage<ForumConversation>> fetchConversations({
    String? cursorUrl,
  }) async {
    fetchConversationsCalls.add(cursorUrl);
    if (conversationPages.isEmpty) {
      return CursorPage(items: conversations);
    }
    if (cursorUrl == null) return conversationPages.first;
    for (var i = 1; i < conversationPages.length; i++) {
      if (conversationPages[i - 1].next == cursorUrl) {
        return conversationPages[i];
      }
    }
    return conversationPages.last;
  }

  @override
  Future<int> fetchUnreadConversationCount() async => unreadConversationCount;

  @override
  Future<ForumConversation?> fetchConversationWith(String username) async {
    fetchConversationWithCalls.add(username);
    return conversationWith;
  }

  @override
  Future<CursorPage<ForumDirectMessage>> fetchMessages({
    required int conversationId,
    String? cursorUrl,
  }) async {
    fetchMessagesCalls.add(cursorUrl);
    if (messagePages.isEmpty) {
      return CursorPage(items: messages);
    }
    if (cursorUrl == null) return messagePages.first;
    for (var i = 1; i < messagePages.length; i++) {
      if (messagePages[i - 1].next == cursorUrl) {
        return messagePages[i];
      }
    }
    return messagePages.last;
  }

  @override
  Future<ForumDirectMessage> sendMessage({
    required String username,
    required String body,
    required String idempotencyKey,
  }) async {
    sendMessageCalls.add({'username': username, 'body': body});
    sendMessageKeys.add(idempotencyKey);
    final gate = sendMessageGate;
    if (gate != null) return gate.future;
    final fail = failSendMessageWith;
    if (fail != null) throw fail;
    return directMessage(
      id: nextSentMessageId++,
      conversationId: conversationWith?.id ?? 1,
      senderUsername: senderUsername,
      body: body,
    );
  }

  @override
  Future<void> reportMessage({
    required int messageId,
    required String reason,
    String? detail,
    required String idempotencyKey,
  }) async {
    reportMessageCalls.add({
      'messageId': messageId,
      'reason': reason,
      'detail': detail,
    });
    reportMessageKeys.add(idempotencyKey);
    final fail = failReportMessageWith;
    if (fail != null) throw fail;
  }

  @override
  Future<void> reportPost({
    required int postId,
    required String reason,
    String? detail,
    required String idempotencyKey,
  }) async {
    reportPostCalls.add({'postId': postId, 'reason': reason, 'detail': detail});
    reportPostKeys.add(idempotencyKey);
    final fail = failReportPostWith;
    if (fail != null) throw fail;
  }

  @override
  Future<bool> blockUser(String username) async {
    blockCalls.add(username);
    final fail = failBlockWith;
    if (fail != null) throw fail;
    return true;
  }

  @override
  Future<bool> unblockUser(String username) async {
    unblockCalls.add(username);
    final fail = failBlockWith;
    if (fail != null) throw fail;
    return false;
  }

  @override
  Future<ForumSolutionResult> markSolution({
    required int topicId,
    required int postId,
    required String idempotencyKey,
  }) async {
    markSolutionCalls.add({'topicId': topicId, 'postId': postId});
    markSolutionKeys.add(idempotencyKey);
    final fail = failSolutionWith;
    if (fail != null) throw fail;
    return solutionResult ??
        ForumSolutionResult(isSolved: true, solvedPostId: postId);
  }

  @override
  Future<ForumSolutionResult> clearSolution(int topicId) async {
    clearSolutionCalls.add(topicId);
    final fail = failSolutionWith;
    if (fail != null) throw fail;
    return const ForumSolutionResult(isSolved: false);
  }

  @override
  Future<bool> bookmarkTopic(int topicId) async {
    bookmarkCalls.add(topicId);
    final fail = failBookmarkWith;
    if (fail != null) throw fail;
    return true;
  }

  @override
  Future<bool> unbookmarkTopic(int topicId) async {
    unbookmarkCalls.add(topicId);
    final fail = failBookmarkWith;
    if (fail != null) throw fail;
    return false;
  }

  @override
  Future<CursorPage<ForumTopicListItem>> fetchBookmarks({
    String? cursorUrl,
  }) async {
    fetchBookmarksCalls.add(cursorUrl);
    if (bookmarkPages.isEmpty) {
      return CursorPage(items: bookmarks);
    }
    if (cursorUrl == null) return bookmarkPages.first;
    for (var i = 1; i < bookmarkPages.length; i++) {
      if (bookmarkPages[i - 1].next == cursorUrl) {
        return bookmarkPages[i];
      }
    }
    return bookmarkPages.last;
  }

  @override
  Future<List<ForumPostRevision>> fetchPostRevisions(int postId) async {
    fetchRevisionsCalls.add(postId);
    final fail = failRevisionsWith;
    if (fail != null) throw fail;
    return revisions;
  }

  @override
  Future<ForumPostRevisionDetail> fetchPostRevision({
    required int postId,
    required int revisionId,
  }) async {
    fetchRevisionCalls.add(revisionId);
    final fail = failRevisionsWith;
    if (fail != null) throw fail;
    final detail = revisionDetails[revisionId];
    if (detail == null) {
      throw ApiException('no fixture', statusCode: 404);
    }
    return detail;
  }
}

/// Build a [ForumPostRevision] fixture (an edit-history row).
ForumPostRevision revision({
  int id = 1,
  String username = 'alice',
  DateTime? createdAt,
}) {
  return ForumPostRevision(
    id: id,
    createdAt: createdAt ?? DateTime(2026, 1, 3),
    user: author(username: username),
  );
}

/// Build a [ForumPostRevisionDetail] fixture (one revision's body).
ForumPostRevisionDetail revisionDetail({
  int id = 1,
  String username = 'alice',
  List<ForumBodyBlock> body = const [ParagraphBlock('Older wording')],
}) {
  return ForumPostRevisionDetail(
    id: id,
    createdAt: DateTime(2026, 1, 3),
    user: author(username: username),
    body: body,
  );
}

/// Build a [ForumConversation] fixture with [otherUsername] on the far side.
ForumConversation conversation({
  int id = 1,
  String otherUsername = 'bob',
  String? otherDisplayName,
  int unreadCount = 0,
  String? lastMessageBody,
  bool lastMessageIsMine = false,
  DateTime? lastMessageAt,
}) {
  return ForumConversation(
    id: id,
    otherParticipant: author(
      username: otherUsername,
      displayName: otherDisplayName,
    ),
    createdAt: DateTime(2026, 1, 1),
    lastMessageAt: lastMessageAt ?? DateTime(2026, 1, 2),
    unreadCount: unreadCount,
    lastMessage: lastMessageBody == null
        ? null
        : ForumLastMessage(
            body: lastMessageBody,
            isMine: lastMessageIsMine,
            createdAt: lastMessageAt ?? DateTime(2026, 1, 2),
          ),
  );
}

/// Build a [ForumDirectMessage] fixture.
ForumDirectMessage directMessage({
  int id = 1,
  int conversationId = 1,
  String senderUsername = 'bob',
  String body = 'Hello',
  DateTime? createdAt,
}) {
  return ForumDirectMessage(
    id: id,
    conversationId: conversationId,
    sender: author(username: senderUsername),
    body: body,
    createdAt: createdAt ?? DateTime(2026, 1, 1),
  );
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
  String title = '',
}) {
  return ForumAuthor(
    username: username,
    displayName: displayName ?? username,
    trustLevel: trustLevel,
    title: title,
  );
}

/// Build a [ForumPost] fixture. [authorOverride] (NOT `author` — that name
/// would shadow the top-level [author] builder referenced in its own default
/// expression) lets a test swap in e.g. a deleted-author fixture:
/// `post(authorOverride: author(username: ForumAuthor.deletedUsername, trustLevel: null))`.
ForumPost post({
  int id = 1,
  int topicId = 10,
  ForumAuthor? authorOverride,
  List<ForumBodyBlock> body = const [ParagraphBlock('Hello')],
  bool isPending = false,
  Map<String, int> reactionCounts = const {},
  List<String> reacted = const [],
  bool canEdit = false,
  bool canDelete = false,
  bool canReport = false,
  bool isBlocked = false,
  bool canBlock = false,
  DateTime? editedAt,
}) {
  return ForumPost(
    id: id,
    topicId: topicId,
    author: authorOverride ?? author(),
    body: body,
    createdAt: DateTime(2026, 1, 1),
    editedAt: editedAt,
    isOpeningPost: id == 1,
    isPending: isPending,
    reactionCounts: reactionCounts,
    reacted: reacted,
    canEdit: canEdit,
    canDelete: canDelete,
    canReport: canReport,
    isBlocked: isBlocked,
    canBlock: canBlock,
  );
}

/// Build a [ForumTopicListItem] fixture. See [post] for why the param is
/// [authorOverride], not `author`.
ForumTopicListItem topic({
  int id = 10,
  String title = 'Sample topic',
  ForumAuthor? authorOverride,
}) {
  return ForumTopicListItem(
    id: id,
    title: title,
    slug: 'sample-topic',
    author: authorOverride ?? author(),
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
ForumTopicDetail topicDetail({
  int id = 10,
  String title = 'Sample topic',
  bool isBookmarked = false,
  int? solvedPostId,
  bool canMarkSolution = false,
}) {
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
    isBookmarked: isBookmarked,
    solvedPostId: solvedPostId,
    canMarkSolution: canMarkSolution,
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

/// Raw map for one `recent_topics[]` entry, shaped like
/// `PublicProfileView`'s response — for [profile]'s `recentTopics` param.
Map<String, dynamic> profileTopicRefJson({
  int id = 1,
  String slug = 'sample-topic',
  String title = 'Sample topic',
  int boardId = 1,
  String boardSlug = 'general',
  int replyCount = 0,
  DateTime? createdAt,
}) {
  return {
    'id': id,
    'slug': slug,
    'title': title,
    'board_id': boardId,
    'board_slug': boardSlug,
    'reply_count': replyCount,
    'created_at': (createdAt ?? DateTime.utc(2026, 1, 1)).toIso8601String(),
  };
}

/// Raw map for one `recent_posts[]` entry, shaped like
/// `PublicProfileView`'s response — for [profile]'s `recentPosts` param.
Map<String, dynamic> profilePostRefJson({
  int id = 1,
  int topicId = 1,
  String topicSlug = 'sample-topic',
  String topicTitle = 'Sample topic',
  int boardId = 1,
  String boardSlug = 'general',
  DateTime? createdAt,
}) {
  return {
    'id': id,
    'topic_id': topicId,
    'topic_slug': topicSlug,
    'topic_title': topicTitle,
    'board_id': boardId,
    'board_slug': boardSlug,
    'created_at': (createdAt ?? DateTime.utc(2026, 1, 1)).toIso8601String(),
  };
}

/// Build a [ForumProfile] fixture. Builds a raw `Map<String, dynamic>`
/// shaped like `PUBLIC_PROFILE_SCHEMA` and routes it through
/// [ForumProfile.fromJson] — NOT a hand-built typed object — so tests
/// exercise the real parse path. `avatar` is always `null`; never set a
/// non-empty avatar URL in a fixture (CachedNetworkImage hangs
/// `pumpAndSettle` in widget tests).
ForumProfile profile({
  String username = 'alice',
  String? displayName,
  int? trustLevel = 2,
  String title = '',
  String bio = '',
  String signature = '',
  int postCount = 0,
  DateTime? joinedAt,
  List<Map<String, dynamic>> recentTopics = const [],
  List<Map<String, dynamic>> recentPosts = const [],
  bool isBlocked = false,
  bool canBlock = false,
}) {
  return ForumProfile.fromJson({
    'username': username,
    'display_name': displayName ?? username,
    'avatar': null,
    'trust_level': trustLevel,
    'title': title,
    'bio': bio,
    'signature': signature,
    'post_count': postCount,
    'joined_at': joinedAt?.toIso8601String(),
    'recent_topics': recentTopics,
    'recent_posts': recentPosts,
    'is_blocked': isBlocked,
    'can_block': canBlock,
  });
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
