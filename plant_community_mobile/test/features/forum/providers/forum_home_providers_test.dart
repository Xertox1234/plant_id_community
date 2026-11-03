import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';

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
}
