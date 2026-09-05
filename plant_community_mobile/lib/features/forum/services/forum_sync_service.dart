import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import 'forum_api.dart';
import 'forum_sync_store.dart';

/// Consumes the `/forum/sync/` delta feed and maintains a local topic mirror.
///
/// Each run reads the persisted `(since, since_id)` cursor, pages through the
/// keyset-paginated deltas (applying upserts and tombstone removals), advances
/// the cursor, and persists the merged mirror. A first run (no cursor) pulls
/// everything; tombstones are only present once a cursor exists.
class ForumSyncService {
  ForumSyncService({required ForumApi api, required ForumSyncStore store})
    : _api = api,
      _store = store;

  final ForumApi _api;
  final ForumSyncStore _store;

  /// Safety bound: 200 topics/page × 500 pages = 100k topics, far beyond any
  /// realistic delta, guarding against a contract regression that never
  /// clears `has_more`.
  /// Public only so the sync tests can pin the bound.
  static const int maxPages = 500;

  /// Run a delta sync. Returns the merged topic mirror sorted newest-first.
  Future<List<ForumTopicStub>> sync({String? boardSlug}) async {
    var cursor = await _store.loadCursor();
    var topics = await _store.loadTopics();

    var pages = 0;
    while (pages < maxPages) {
      pages++;
      final page = await _api.sync(
        since: cursor.since,
        sinceId: cursor.sinceId,
        boardSlug: boardSlug,
      );
      topics = applyForumSyncDelta(
        topics,
        upserts: page.topics,
        deleted: page.deleted,
      );
      cursor = ForumSyncCursor(
        since: page.nextSince ?? cursor.since,
        sinceId: page.nextSinceId ?? cursor.sinceId,
      );
      if (!page.hasMore) break;
    }

    await _store.saveTopics(topics);
    await _store.saveCursor(cursor);
    return _sorted(topics);
  }

  /// The cached topic mirror without touching the network (offline / instant
  /// render).
  Future<List<ForumTopicStub>> cachedTopics() async {
    return _sorted(await _store.loadTopics());
  }

  static List<ForumTopicStub> _sorted(Map<int, ForumTopicStub> topics) {
    final list = topics.values.toList()
      ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
    return list;
  }
}

/// Injectable sync service wired to the forum API and sync store.
final forumSyncServiceProvider = Provider<ForumSyncService>(
  (ref) => ForumSyncService(
    api: ref.watch(forumApiProvider),
    store: ref.watch(forumSyncStoreProvider),
  ),
);
