import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:uuid/uuid.dart';

import '../models/models.dart';
import '../services/forum_api.dart';
import '../services/forum_sync_service.dart';

part 'forum_providers.g.dart';

/// A cursor-paginated, incrementally-loaded list. [nextUrl] is the absolute
/// `next` cursor URL (null when exhausted).
class PagedList<T> {
  const PagedList({
    required this.items,
    this.nextUrl,
    this.isLoadingMore = false,
  });

  final List<T> items;
  final String? nextUrl;
  final bool isLoadingMore;

  bool get hasMore => nextUrl != null;
}

/// Forum boards (not paginated).
@riverpod
class Boards extends _$Boards {
  @override
  Future<List<ForumBoard>> build() {
    return ref.watch(forumApiProvider).fetchBoards();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(forumApiProvider).fetchBoards(),
    );
  }
}

/// Topics in a board, cursor-paginated with [loadMore].
@riverpod
class BoardTopics extends _$BoardTopics {
  @override
  Future<PagedList<ForumTopicListItem>> build(String boardSlug) async {
    final page = await ref
        .watch(forumApiProvider)
        .fetchTopics(boardSlug: boardSlug);
    return PagedList(items: page.items, nextUrl: page.next);
  }

  /// Fetch and append the next page. Rethrows on failure with the loading flag
  /// reset so the caller can surface an error and the user can retry.
  Future<void> loadMore() async {
    final current = state.asData?.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncData(
      PagedList(
        items: current.items,
        nextUrl: current.nextUrl,
        isLoadingMore: true,
      ),
    );
    try {
      final page = await ref
          .read(forumApiProvider)
          .fetchTopics(boardSlug: boardSlug, cursorUrl: current.nextUrl);
      // Re-read after the await so a concurrent state change isn't lost.
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: [...latest.items, ...page.items], nextUrl: page.next),
      );
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: latest.items, nextUrl: latest.nextUrl),
      );
      rethrow;
    }
  }
}

/// A single topic's detail, plus subscribe/unsubscribe (todo 293).
@riverpod
class TopicDetail extends _$TopicDetail {
  @override
  Future<ForumTopicDetail> build(int topicId) {
    return ref.watch(forumApiProvider).fetchTopicDetail(topicId);
  }

  /// Subscribe if currently unsubscribed, else unsubscribe. Writes back the
  /// server's returned `subscribed` state (like [TopicPosts.toggleReaction],
  /// never just flips the local flag) so a partial failure can't leave the
  /// toggle showing a state the backend disagrees with. Rethrows on failure
  /// — unlike the fire-and-forget reaction toggle, an explicit
  /// subscribe/unsubscribe tap should surface an error to the caller.
  Future<void> toggleSubscription() async {
    final current = state.asData?.value;
    if (current == null) return;
    final api = ref.read(forumApiProvider);
    final subscribed = current.isSubscribed
        ? await api.unsubscribeFromTopic(topicId)
        : await api.subscribeToTopic(topicId);
    // Re-read after the await so a concurrent refresh isn't lost.
    final latest = state.asData?.value ?? current;
    state = AsyncData(latest.withSubscribed(subscribed));
  }
}

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`).
@riverpod
class ForumUserProfile extends _$ForumUserProfile {
  @override
  Future<ForumProfile> build(String username) {
    return ref.watch(forumApiProvider).fetchProfile(username);
  }
}

/// Safety bound on the page walk in [TopicPosts.refreshAfterReply] — mirrors
/// the web client's MAX_REFRESH_PAGES (ThreadDetailPage.tsx) for a
/// pathologically long thread.
const _maxRefreshPages = 50;

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.
@riverpod
class TopicPosts extends _$TopicPosts {
  @override
  Future<PagedList<ForumPost>> build(int topicId) async {
    final page = await ref.watch(forumApiProvider).fetchPosts(topicId: topicId);
    return PagedList(items: page.items, nextUrl: page.next);
  }

  /// Refetch every page of the thread from the start (todo 291). Posts are
  /// oldest-first, so a just-posted reply is always on the LAST cursor page —
  /// refetching page 1 alone (a plain `invalidate`) never shows it. The reply
  /// endpoint returns no cursor/position for the new post (only its id and
  /// moderation status), so there is no cheaper way to land it in view than
  /// walking every page. Mirrors the web client's `collectAllPosts`
  /// (ThreadDetailPage.tsx). Bounded by [_maxRefreshPages]; on failure,
  /// restores the prior list rather than leaving a stuck spinner or a
  /// half-collected page walk, same discipline as [loadMore].
  ///
  /// On SUCCESS this replaces `state` wholesale with the walk's own local
  /// `items`, unlike [loadMore]/[toggleReaction]'s re-read-and-merge — that's
  /// deliberate: a concurrent [toggleReaction] while the walk is in flight
  /// gets superseded by this method's freshly-fetched server data (the fetch is
  /// strictly newer), rather than the walk trying to preserve a
  /// possibly-stale optimistic local write.
  Future<void> refreshAfterReply() async {
    final current = state.asData?.value;
    if (current != null) {
      state = AsyncData(
        PagedList(
          items: current.items,
          nextUrl: current.nextUrl,
          isLoadingMore: true,
        ),
      );
    }
    try {
      final items = <ForumPost>[];
      String? cursorUrl;
      String? next;
      for (var i = 0; i < _maxRefreshPages; i++) {
        final page = await ref
            .read(forumApiProvider)
            .fetchPosts(topicId: topicId, cursorUrl: cursorUrl);
        items.addAll(page.items);
        next = page.next;
        if (next == null) break;
        cursorUrl = next;
      }
      state = AsyncData(PagedList(items: items, nextUrl: next));
    } catch (_) {
      final latest = state.asData?.value ?? current;
      if (latest != null) {
        state = AsyncData(
          PagedList(items: latest.items, nextUrl: latest.nextUrl),
        );
      }
      rethrow;
    }
  }

  Future<void> loadMore() async {
    final current = state.asData?.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncData(
      PagedList(
        items: current.items,
        nextUrl: current.nextUrl,
        isLoadingMore: true,
      ),
    );
    try {
      final page = await ref
          .read(forumApiProvider)
          .fetchPosts(topicId: topicId, cursorUrl: current.nextUrl);
      // Re-read after the await so a concurrent reaction toggle isn't lost.
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: [...latest.items, ...page.items], nextUrl: page.next),
      );
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: latest.items, nextUrl: latest.nextUrl),
      );
      rethrow;
    }
  }

  /// Toggle a reaction on [postId]. Each tap uses a fresh idempotency key; the
  /// response's `reaction_counts` are written back wholesale so the pill state
  /// never lies on failure.
  Future<void> toggleReaction(int postId, String type) async {
    if (state.asData?.value == null) return;
    final ReactionToggleResult result;
    try {
      result = await ref
          .read(forumApiProvider)
          .toggleReaction(
            postId: postId,
            type: type,
            idempotencyKey: const Uuid().v4(),
          );
    } catch (_) {
      // Fire-and-forget from the UI: a failed toggle leaves the pills as they
      // are rather than throwing an unhandled async error or lying about state.
      return;
    }
    // Re-read state after the await — the list may have changed (e.g. a
    // concurrent loadMore).
    final latest = state.asData?.value;
    if (latest == null) return;
    final index = latest.items.indexWhere((p) => p.id == postId);
    if (index < 0) return;
    final reacted = List<String>.from(latest.items[index].reacted);
    if (result.reacted) {
      if (!reacted.contains(type)) reacted.add(type);
    } else {
      reacted.remove(type);
    }
    final updated = [...latest.items];
    updated[index] = latest.items[index].withReactions(
      reactionCounts: result.reactionCounts,
      reacted: reacted,
    );
    state = AsyncData(
      PagedList(
        items: updated,
        nextUrl: latest.nextUrl,
        isLoadingMore: latest.isLoadingMore,
      ),
    );
  }

  /// Splice a successfully-edited post into place (todo 292). Deliberately
  /// not a full [ref.invalidate]-and-refetch: `TopicPosts.build` always
  /// fetches page 1 only, so invalidating would silently drop any pages the
  /// user had already loaded via [loadMore] on a long thread. The edited
  /// post is already on a currently-loaded page, so a local splice (same
  /// idiom as [toggleReaction]) is both cheaper and preserves scroll depth.
  void applyEditedPost(ForumPost updated) {
    final current = state.asData?.value;
    if (current == null) return;
    final index = current.items.indexWhere((p) => p.id == updated.id);
    if (index < 0) return;
    final items = [...current.items];
    items[index] = updated;
    state = AsyncData(
      PagedList(
        items: items,
        nextUrl: current.nextUrl,
        isLoadingMore: current.isLoadingMore,
      ),
    );
  }

  /// Delete [postId] (todo 292). Rethrows on failure — unlike
  /// [toggleReaction]'s fire-and-forget swallow, a delete is a deliberate,
  /// confirmed user action and its failure (e.g. a 409 frozen-topic
  /// rejection) must reach the caller to show, not disappear silently.
  Future<void> deletePost(int postId) async {
    await ref.read(forumApiProvider).deletePost(postId: postId);
    final current = state.asData?.value;
    if (current == null) return;
    state = AsyncData(
      PagedList(
        items: current.items.where((p) => p.id != postId).toList(),
        nextUrl: current.nextUrl,
        isLoadingMore: current.isLoadingMore,
      ),
    );
  }
}

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.
@riverpod
class RecentTopics extends _$RecentTopics {
  @override
  Future<List<ForumTopicStub>> build() async {
    final service = ref.watch(forumSyncServiceProvider);
    try {
      return await service.sync();
    } catch (_) {
      return service.cachedTopics();
    }
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(forumSyncServiceProvider).sync(),
    );
  }
}

/// The user's notifications (cursor-paginated, newest first).
@riverpod
class NotificationsFeed extends _$NotificationsFeed {
  @override
  Future<PagedList<ForumNotification>> build() async {
    final page = await ref.watch(forumApiProvider).fetchNotifications();
    return PagedList(items: page.items, nextUrl: page.next);
  }

  Future<void> loadMore() async {
    final current = state.asData?.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncData(
      PagedList(
        items: current.items,
        nextUrl: current.nextUrl,
        isLoadingMore: true,
      ),
    );
    try {
      final page = await ref
          .read(forumApiProvider)
          .fetchNotifications(cursorUrl: current.nextUrl);
      // Re-read after the await so a concurrent mark-read isn't lost.
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: [...latest.items, ...page.items], nextUrl: page.next),
      );
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: latest.items, nextUrl: latest.nextUrl),
      );
      rethrow;
    }
  }

  /// Mark one notification read (splice locally + call the API), or every
  /// unread notification when [id] is omitted. Refreshes the unread badge
  /// via invalidation rather than a local decrement, so the badge stays
  /// accurate even if another client already read some of them.
  Future<void> markRead({int? id}) async {
    await ref
        .read(forumApiProvider)
        .markNotificationsRead(ids: id == null ? null : [id]);
    final latest = state.asData?.value;
    if (latest != null) {
      final now = DateTime.now();
      final updated = latest.items.map((n) {
        if (id != null && n.id != id) return n;
        return n.readAt == null ? n.asRead(now) : n;
      }).toList();
      state = AsyncData(
        PagedList(
          items: updated,
          nextUrl: latest.nextUrl,
          isLoadingMore: latest.isLoadingMore,
        ),
      );
    }
    ref.invalidate(unreadNotificationCountProvider);
  }
}

/// Unread notification count, for the bell badge.
@riverpod
Future<int> unreadNotificationCount(Ref ref) {
  return ref.watch(forumApiProvider).fetchUnreadNotificationCount();
}

/// The user's DM inbox (cursor-paginated, most recent activity first).
@riverpod
class ConversationsFeed extends _$ConversationsFeed {
  @override
  Future<PagedList<ForumConversation>> build() async {
    final page = await ref.watch(forumApiProvider).fetchConversations();
    return PagedList(items: page.items, nextUrl: page.next);
  }

  Future<void> loadMore() async {
    final current = state.asData?.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncData(
      PagedList(
        items: current.items,
        nextUrl: current.nextUrl,
        isLoadingMore: true,
      ),
    );
    try {
      final page = await ref
          .read(forumApiProvider)
          .fetchConversations(cursorUrl: current.nextUrl);
      // Re-read after the await so a concurrent state change isn't lost.
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: [...latest.items, ...page.items], nextUrl: page.next),
      );
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        PagedList(items: latest.items, nextUrl: latest.nextUrl),
      );
      rethrow;
    }
  }

  /// The thread was opened (the server marked it read): zero that row's
  /// unread count in place. A whole-provider invalidation would refetch
  /// page 1 only and drop every page `loadMore` had appended — the same
  /// discipline as `TopicPosts.applyEditedPost`.
  void markRead(int conversationId) {
    final current = state.asData?.value;
    if (current == null) return;
    state = AsyncData(
      PagedList(
        items: [
          for (final row in current.items)
            if (row.id == conversationId) row.copyWith(unreadCount: 0) else row,
        ],
        nextUrl: current.nextUrl,
        isLoadingMore: current.isLoadingMore,
      ),
    );
  }

  /// A message was sent in [conversation]: the row moves to the top with
  /// the new preview (own message → "You: …", never unread). A conversation
  /// the loaded pages don't hold yet (first message) is inserted at the top.
  void applyActivity(ForumConversation conversation) {
    final current = state.asData?.value;
    if (current == null) return;
    state = AsyncData(
      PagedList(
        items: [
          conversation,
          for (final row in current.items)
            if (row.id != conversation.id) row,
        ],
        nextUrl: current.nextUrl,
        isLoadingMore: current.isLoadingMore,
      ),
    );
  }
}

/// Conversations with unread messages, for the inbox badge.
@riverpod
Future<int> unreadConversationCount(Ref ref) {
  return ref.watch(forumApiProvider).fetchUnreadConversationCount();
}

/// State for [ConversationThread]. [messages] are held oldest → newest (the
/// display order); [olderCursorUrl] is the API's `next` cursor, which on a
/// newest-first endpoint walks toward OLDER messages.
class ConversationThreadState {
  const ConversationThreadState({
    required this.conversation,
    required this.messages,
    this.olderCursorUrl,
    this.isLoadingOlder = false,
    this.isSending = false,
  });

  /// `null` until the first message is sent — no conversation row exists
  /// yet for a pair who have never messaged.
  final ForumConversation? conversation;
  final List<ForumDirectMessage> messages;
  final String? olderCursorUrl;
  final bool isLoadingOlder;
  final bool isSending;

  bool get hasOlder => olderCursorUrl != null;

  ConversationThreadState copyWith({
    ForumConversation? conversation,
    List<ForumDirectMessage>? messages,
    String? olderCursorUrl,
    bool clearOlderCursor = false,
    bool? isLoadingOlder,
    bool? isSending,
  }) {
    return ConversationThreadState(
      conversation: conversation ?? this.conversation,
      messages: messages ?? this.messages,
      olderCursorUrl: clearOlderCursor
          ? null
          : (olderCursorUrl ?? this.olderCursorUrl),
      isLoadingOlder: isLoadingOlder ?? this.isLoadingOlder,
      isSending: isSending ?? this.isSending,
    );
  }
}

/// A 1:1 DM thread with [username] (todo 339): resolves the conversation
/// (absent until first send), pages older messages, and sends.
///
/// Every page from the API is newest-first; it is reversed on the way in so
/// [ConversationThreadState.messages] reads oldest → newest like a chat.
@riverpod
class ConversationThread extends _$ConversationThread {
  /// One `Idempotency-Key` per composed message, reused across retries of
  /// the SAME body and rotated when the body changes — the backend replays
  /// a same-key/same-payload retry and 422s a same-key/different-payload
  /// one (docs/rules/flutter.md → Idempotent mobile writes).
  String? _sendKey;
  String? _sendFingerprint;

  @override
  Future<ConversationThreadState> build(String username) async {
    final api = ref.watch(forumApiProvider);
    final conversation = await api.fetchConversationWith(username);
    if (conversation == null) {
      return const ConversationThreadState(conversation: null, messages: []);
    }
    final page = await api.fetchMessages(conversationId: conversation.id);
    // Reading marks the conversation read server-side. The badge is cheap to
    // refetch (invalidate); the inbox row is spliced in place IF the inbox
    // is alive — invalidating it would collapse its loaded pages to page 1.
    ref.invalidate(unreadConversationCountProvider);
    if (ref.exists(conversationsFeedProvider)) {
      ref.read(conversationsFeedProvider.notifier).markRead(conversation.id);
    }
    return ConversationThreadState(
      conversation: conversation,
      messages: page.items.reversed.toList(growable: false),
      olderCursorUrl: page.next,
    );
  }

  /// Fetch the next (older) page and prepend it. Rethrows on failure with
  /// the loading flag reset so the caller can surface an error and retry.
  Future<void> loadOlder() async {
    final current = state.asData?.value;
    final conversation = current?.conversation;
    if (current == null || conversation == null) return;
    if (!current.hasOlder || current.isLoadingOlder) return;
    state = AsyncData(current.copyWith(isLoadingOlder: true));
    try {
      final page = await ref
          .read(forumApiProvider)
          .fetchMessages(
            conversationId: conversation.id,
            cursorUrl: current.olderCursorUrl,
          );
      // Re-read after the await so a concurrent send isn't lost.
      final latest = state.asData?.value ?? current;
      state = AsyncData(
        latest.copyWith(
          messages: [...page.items.reversed, ...latest.messages],
          olderCursorUrl: page.next,
          clearOlderCursor: page.next == null,
          isLoadingOlder: false,
        ),
      );
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(latest.copyWith(isLoadingOlder: false));
      rethrow;
    }
  }

  /// Send [body]; appends the server's echo of the message and, on the
  /// first send, resolves the newly-created conversation. Rethrows so the
  /// UI can map 403 (blocked) / 400 (empty or spam-screened) to copy.
  Future<void> send(String body) async {
    final current = state.asData?.value;
    if (current == null || current.isSending) return;
    final trimmed = body.trim();
    if (trimmed.isEmpty) return;
    final fingerprint = '$username|$trimmed';
    if (_sendKey == null || _sendFingerprint != fingerprint) {
      _sendKey = const Uuid().v4();
      _sendFingerprint = fingerprint;
    }
    final key = _sendKey;
    if (key == null) return;
    state = AsyncData(current.copyWith(isSending: true));
    final api = ref.read(forumApiProvider);
    try {
      final message = await api.sendMessage(
        username: username,
        body: trimmed,
        idempotencyKey: key,
      );
      _sendKey = null;
      _sendFingerprint = null;
      var latest = state.asData?.value ?? current;
      if (latest.conversation == null) {
        // First message between this pair: the row now exists server-side.
        // A failed lookup here must not turn a successful send into an
        // error — the message is already on the list below.
        try {
          final conversation = await api.fetchConversationWith(username);
          latest = state.asData?.value ?? latest;
          if (conversation != null) {
            latest = latest.copyWith(conversation: conversation);
          }
        } catch (_) {
          // Resolved on the next open instead.
        }
      }
      state = AsyncData(
        latest.copyWith(
          messages: [...latest.messages, message],
          isSending: false,
        ),
      );
      final row = latest.conversation;
      if (row != null && ref.exists(conversationsFeedProvider)) {
        ref
            .read(conversationsFeedProvider.notifier)
            .applyActivity(
              row.copyWith(
                unreadCount: 0,
                lastMessageAt: message.createdAt,
                lastMessage: ForumLastMessage(
                  body: message.body,
                  isMine: true,
                  createdAt: message.createdAt,
                ),
              ),
            );
      }
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(latest.copyWith(isSending: false));
      rethrow;
    }
    ref.invalidate(unreadConversationCountProvider);
  }
}

enum ForumSearchStatus { idle, loading, loadingMore, data, error }

/// State for [ForumSearch]. Not [AsyncValue]-wrapped on purpose: search has
/// its own idle/loading/loadingMore/data/error states (an idle "no query
/// yet" screen, and a loadingMore that keeps existing results visible),
/// which don't map cleanly onto AsyncValue's own loading/data/error triad.
class ForumSearchResult {
  const ForumSearchResult({
    required this.status,
    this.query = '',
    this.board,
    this.page = 1,
    this.topics = const [],
    this.posts = const [],
    this.topicsHasMore = false,
    this.postsHasMore = false,
    this.semantic,
    this.semanticStatus,
    this.errorMessage,
  });

  final ForumSearchStatus status;
  final String query;
  final String? board;
  final int page;
  final List<ForumSearchTopicHit> topics;
  final List<ForumSearchPostHit> posts;
  final bool topicsHasMore;
  final bool postsHasMore;
  final List<ForumSearchTopicHit>? semantic;
  final ForumSemanticStatus? semanticStatus;
  final String? errorMessage;

  bool get hasMore => topicsHasMore || postsHasMore;
}

/// Full-text forum search. Offset-paginated (see [ForumSearchPage]) — a
/// "load more" fetches the next `page` and appends to both sections, since
/// the two `*_has_more` flags share one page cursor.
@riverpod
class ForumSearch extends _$ForumSearch {
  // Bumped at the start of every search()/loadMore() call (code review): a
  // request only commits its result if it's still the most recent one when
  // its await resolves. Without this, a double-tap Search (or a loadMore
  // racing a fresh search) lets whichever request happens to resolve LAST
  // win, regardless of which was issued last — a stale query's results
  // could silently overwrite a newer query's state.
  int _generation = 0;

  @override
  ForumSearchResult build() =>
      const ForumSearchResult(status: ForumSearchStatus.idle);

  Future<void> search({required String query, String? board}) async {
    final trimmed = query.trim();
    final generation = ++_generation;
    if (trimmed.isEmpty) {
      state = const ForumSearchResult(status: ForumSearchStatus.idle);
      return;
    }
    state = ForumSearchResult(
      status: ForumSearchStatus.loading,
      query: trimmed,
      board: board,
    );
    try {
      final result = await ref
          .read(forumApiProvider)
          .search(q: trimmed, board: board, page: 1, semantic: true);
      if (generation != _generation) return; // superseded — discard
      state = ForumSearchResult(
        status: ForumSearchStatus.data,
        query: trimmed,
        board: board,
        page: result.page,
        topics: result.topics,
        posts: result.posts,
        topicsHasMore: result.topicsHasMore,
        postsHasMore: result.postsHasMore,
        semantic: result.semantic,
        semanticStatus: result.semanticStatus,
      );
    } catch (e) {
      if (generation != _generation) return; // superseded — discard
      state = ForumSearchResult(
        status: ForumSearchStatus.error,
        query: trimmed,
        board: board,
        errorMessage: e.toString(),
      );
    }
  }

  Future<void> loadMore() async {
    final current = state;
    if (current.status != ForumSearchStatus.data || !current.hasMore) return;
    final generation = ++_generation;
    state = ForumSearchResult(
      status: ForumSearchStatus.loadingMore,
      query: current.query,
      board: current.board,
      page: current.page,
      topics: current.topics,
      posts: current.posts,
      topicsHasMore: current.topicsHasMore,
      postsHasMore: current.postsHasMore,
      semantic: current.semantic,
      semanticStatus: current.semanticStatus,
    );
    try {
      final result = await ref
          .read(forumApiProvider)
          .search(
            q: current.query,
            board: current.board,
            page: current.page + 1,
          );
      if (generation != _generation) return; // superseded — discard
      final latest = state;
      state = ForumSearchResult(
        status: ForumSearchStatus.data,
        query: latest.query,
        board: latest.board,
        page: result.page,
        topics: [...latest.topics, ...result.topics],
        posts: [...latest.posts, ...result.posts],
        topicsHasMore: result.topicsHasMore,
        postsHasMore: result.postsHasMore,
        semantic: latest.semantic,
        semanticStatus: latest.semanticStatus,
      );
    } catch (_) {
      if (generation != _generation) return; // superseded — discard
      final latest = state;
      state = ForumSearchResult(
        status: ForumSearchStatus.data,
        query: latest.query,
        board: latest.board,
        page: latest.page,
        topics: latest.topics,
        posts: latest.posts,
        topicsHasMore: latest.topicsHasMore,
        postsHasMore: latest.postsHasMore,
        semantic: latest.semantic,
        semanticStatus: latest.semanticStatus,
      );
      rethrow;
    }
  }
}
