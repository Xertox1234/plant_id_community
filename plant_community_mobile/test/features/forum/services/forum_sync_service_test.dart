import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_service.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';

import '../support/forum_test_support.dart';

void main() {
  group('applyForumSyncDelta', () {
    test('upserts insert/overwrite and tombstones remove', () {
      final current = {
        1: stub(id: 1, title: 'one'),
        2: stub(id: 2, title: 'two'),
      };
      final result = applyForumSyncDelta(
        current,
        upserts: [
          stub(id: 2, title: 'two-updated'),
          stub(id: 3, title: 'three'),
        ],
        deleted: [const ForumTombstone(topicId: 1, boardId: 5)],
      );
      expect(result.keys, unorderedEquals([2, 3]));
      expect(result[2]!.title, 'two-updated');
      // Input map is not mutated.
      expect(current.keys, unorderedEquals([1, 2]));
    });
  });

  group('ForumSyncService', () {
    late FakeForumApi api;
    late InMemoryForumSyncStore store;
    late ForumSyncService service;

    setUp(() {
      api = FakeForumApi();
      store = InMemoryForumSyncStore();
      service = ForumSyncService(api: api, store: store);
    });

    test('initial full sync stores topics and advances the cursor', () async {
      api.syncPages = [
        ForumSyncPage(
          topics: [
            stub(id: 1, title: 'a'),
            stub(id: 2, title: 'b'),
          ],
          deleted: const [],
          hasMore: false,
          nextSince: DateTime.utc(2026, 2, 1),
          nextSinceId: 2,
        ),
      ];

      final merged = await service.sync();

      expect(merged.map((t) => t.id), unorderedEquals([1, 2]));
      // First call carried no cursor (initial pull).
      expect(api.syncCalls.single['since'], isNull);
      final cursor = await store.loadCursor();
      expect(cursor.since, DateTime.utc(2026, 2, 1));
      expect(cursor.sinceId, 2);
    });

    test(
      'delta sync applies upserts + tombstones over the cached mirror',
      () async {
        await store.saveTopics({
          1: stub(id: 1, title: 'one'),
          2: stub(id: 2, title: 'two'),
        });
        await store.saveCursor(
          ForumSyncCursor(since: DateTime.utc(2026, 1, 1), sinceId: 2),
        );
        api.syncPages = [
          ForumSyncPage(
            topics: [
              stub(id: 2, title: 'two-edited'),
              stub(id: 3, title: 'three'),
            ],
            deleted: const [ForumTombstone(topicId: 1, boardId: 9)],
            hasMore: false,
            nextSince: DateTime.utc(2026, 1, 5),
            nextSinceId: 3,
          ),
        ];

        final merged = await service.sync();

        expect(merged.map((t) => t.id), unorderedEquals([2, 3]));
        expect(merged.firstWhere((t) => t.id == 2).title, 'two-edited');
        // The request consumed the persisted cursor.
        expect(api.syncCalls.single['since'], DateTime.utc(2026, 1, 1));
        expect(api.syncCalls.single['sinceId'], 2);
      },
    );

    test(
      'pages through has_more until exhausted, applying every page',
      () async {
        api.syncPages = [
          ForumSyncPage(
            topics: [stub(id: 1), stub(id: 2)],
            deleted: const [],
            hasMore: true,
            nextSince: DateTime.utc(2026, 3, 1),
            nextSinceId: 2,
          ),
          ForumSyncPage(
            topics: [stub(id: 3)],
            deleted: const [ForumTombstone(topicId: 1, boardId: 1)],
            hasMore: false,
            nextSince: DateTime.utc(2026, 3, 2),
            nextSinceId: 3,
          ),
        ];

        final merged = await service.sync();

        expect(api.syncCalls, hasLength(2));
        // Page 2's tombstone removed the topic added on page 1.
        expect(merged.map((t) => t.id), unorderedEquals([2, 3]));
        final cursor = await store.loadCursor();
        expect(cursor.since, DateTime.utc(2026, 3, 2));
        expect(cursor.sinceId, 3);
      },
    );

    test('cachedTopics reads the mirror without hitting the network', () async {
      await store.saveTopics({1: stub(id: 1, title: 'cached')});
      final cached = await service.cachedTopics();
      expect(cached.single.title, 'cached');
      expect(api.syncCalls, isEmpty);
    });
  });
}
