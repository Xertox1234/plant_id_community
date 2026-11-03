import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

ProviderContainer _container(FakeForumApi api) {
  final container = ProviderContainer(
    overrides: [forumApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('ExpandedActivityTopic', () {
    test('toggles one open at a time and closes on a repeat', () {
      final container = _container(FakeForumApi());
      container.listen(expandedActivityTopicProvider, (_, _) {});
      final notifier = container.read(expandedActivityTopicProvider.notifier);

      expect(container.read(expandedActivityTopicProvider), isNull);
      notifier.toggle(1);
      expect(container.read(expandedActivityTopicProvider), 1);
      notifier.toggle(2);
      expect(container.read(expandedActivityTopicProvider), 2);
      notifier.toggle(2);
      expect(container.read(expandedActivityTopicProvider), isNull);
    });

    test('collapse clears the open topic', () {
      final container = _container(FakeForumApi());
      container.listen(expandedActivityTopicProvider, (_, _) {});
      final notifier = container.read(expandedActivityTopicProvider.notifier);
      notifier.toggle(3);
      notifier.collapse();
      expect(container.read(expandedActivityTopicProvider), isNull);
    });
  });

  test('latestReplies is kept alive: two reads, one fetch', () async {
    final api = FakeForumApi();
    final container = _container(api);

    await container.read(latestRepliesProvider(5).future);
    await container.read(latestRepliesProvider(5).future);

    expect(api.latestRepliesCalls(5), 1);
  });

  test('homeRecentTopics asks for ten', () async {
    final api = FakeForumApi();
    final container = _container(api);
    container.listen(homeRecentTopicsProvider, (_, _) {});

    await container.read(homeRecentTopicsProvider.future);

    expect(api.recentTopicsLimits, [10]);
  });

  test('communityStats returns the API value', () async {
    final api = FakeForumApi()
      ..communityStats = const ForumCommunityStats(membersOnline: 4);
    final container = _container(api);
    container.listen(communityStatsProvider, (_, _) {});

    final stats = await container.read(communityStatsProvider.future);

    expect(stats.membersOnline, 4);
  });

  // Riverpod 3 retries a failure ~10 times over ~40 s by default; a 4xx will
  // not change on retry, so these home reads fail at once (forumRetry, the
  // forum copy of blogRetry). A 5xx/network error keeps the default backoff.
  group('home reads do not retry a 4xx', () {
    Future<void> settleRetries(WidgetTester tester) async {
      for (var i = 0; i < 12; i++) {
        await tester.pump(const Duration(seconds: 5));
      }
    }

    testWidgets('latestReplies: one fetch for a 404', (tester) async {
      final api = FakeForumApi()
        ..latestRepliesError = ApiException('gone', statusCode: 404);
      final container = _container(api);
      container.listen(latestRepliesProvider(7), (_, _) {});
      await settleRetries(tester);
      expect(api.latestRepliesCalls(7), 1);
      expect(container.read(latestRepliesProvider(7)).hasError, isTrue);
    });

    testWidgets('latestReplies: a 503 is still retried', (tester) async {
      final api = FakeForumApi()
        ..latestRepliesError = ApiException('down', statusCode: 503);
      final container = _container(api);
      container.listen(latestRepliesProvider(7), (_, _) {});
      await tester.pump(const Duration(seconds: 2));
      expect(api.latestRepliesCalls(7), greaterThan(1));
      // Let the backoff finish so no timer outlives the test.
      api.latestRepliesError = null;
      await settleRetries(tester);
    });

    testWidgets('homeRecentTopics: one fetch for a 403', (tester) async {
      final api = FakeForumApi()
        ..recentTopicsError = ApiException('no', statusCode: 403);
      final container = _container(api);
      container.listen(homeRecentTopicsProvider, (_, _) {});
      await settleRetries(tester);
      expect(api.recentTopicsLimits, hasLength(1));
    });

    testWidgets('communityStats: one fetch for a 404', (tester) async {
      final api = FakeForumApi()
        ..communityStatsError = ApiException('gone', statusCode: 404);
      final container = _container(api);
      container.listen(communityStatsProvider, (_, _) {});
      await settleRetries(tester);
      expect(api.communityStatsCalls, 1);
    });
  });
}
