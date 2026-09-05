import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_service.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';

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

    test('a failure on a later page leaves the persisted mirror and cursor '
        'untouched (audit 2026-09-04 L9)', () async {
      // sync() persists only after the whole has_more walk, so a page-2
      // failure must not half-apply page 1: the store keeps exactly what
      // the previous successful sync left.
      await store.saveTopics({1: stub(id: 1, title: 'kept')});
      await store.saveCursor(const ForumSyncCursor(since: null, sinceId: 1));
      final failing = _FailingSyncApi(failOnCall: 2)
        ..syncPages = [
          ForumSyncPage(
            topics: [stub(id: 2, title: 'never-persisted')],
            deleted: const [ForumTombstone(topicId: 1, boardId: 1)],
            hasMore: true,
            nextSince: DateTime.utc(2026, 3, 1),
            nextSinceId: 2,
          ),
        ];
      final failingService = ForumSyncService(api: failing, store: store);

      await expectLater(failingService.sync(), throwsA(isA<ApiException>()));

      final kept = await store.loadTopics();
      expect(kept.keys, [1]);
      expect(kept[1]!.title, 'kept');
      final cursor = await store.loadCursor();
      expect(cursor.since, isNull);
      expect(cursor.sinceId, 1);
    });

    test(
      'a contract that never clears has_more is cut off at the page bound',
      () async {
        // The fake repeats its last page, so has_more stays true forever.
        api.syncPages = [
          ForumSyncPage(
            topics: [stub(id: 1)],
            deleted: const [],
            hasMore: true,
            nextSince: DateTime.utc(2026, 3, 1),
            nextSinceId: 1,
          ),
        ];

        final merged = await service.sync();

        // Pin the value, not just the loop's use of it: a shrunk bound
        // would otherwise go green (todo 321 lesson).
        expect(ForumSyncService.maxPages, 500);
        expect(api.syncCalls, hasLength(500));
        expect(merged.single.id, 1);
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

/// A [FakeForumApi] whose Nth [sync] call throws instead of returning a page.
class _FailingSyncApi extends FakeForumApi {
  _FailingSyncApi({required this.failOnCall});

  final int failOnCall;
  int _calls = 0;

  @override
  Future<ForumSyncPage> sync({
    DateTime? since,
    int? sinceId,
    String? boardSlug,
  }) async {
    if (++_calls == failOnCall) {
      throw ApiException('boom', statusCode: 503);
    }
    return super.sync(since: since, sinceId: sinceId, boardSlug: boardSlug);
  }
}
