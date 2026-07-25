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

/// A single topic's detail.
@riverpod
Future<ForumTopicDetail> topicDetail(Ref ref, int topicId) {
  return ref.watch(forumApiProvider).fetchTopicDetail(topicId);
}

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.
@riverpod
class TopicPosts extends _$TopicPosts {
  @override
  Future<PagedList<ForumPost>> build(int topicId) async {
    final page = await ref.watch(forumApiProvider).fetchPosts(topicId: topicId);
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
