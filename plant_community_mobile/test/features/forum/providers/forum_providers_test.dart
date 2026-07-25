import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';

import '../support/forum_test_support.dart';

void main() {
  group('TopicPosts.toggleReaction', () {
    test('success writes the fresh reaction counts back to the post', () async {
      final api = FakeForumApi()
        ..posts = CursorPage(
          items: [post(id: 5, reactionCounts: const {}, reacted: const [])],
        )
        ..reactionResult = const ReactionToggleResult(
          reactionCounts: {'like': 3},
          reacted: true,
        );
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicPostsProvider(10).future);
      await container
          .read(topicPostsProvider(10).notifier)
          .toggleReaction(5, 'like');

      final posts = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(posts.single.reactionCounts['like'], 3);
      expect(posts.single.reacted, contains('like'));
    });

    test('a failed toggle does not throw and leaves state unchanged', () async {
      final api = FakeForumApi()
        ..posts = CursorPage(
          items: [
            post(
              id: 5,
              reactionCounts: const {'like': 1},
              reacted: const ['like'],
            ),
          ],
        )
        ..failReactionToggle = true;
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicPostsProvider(10).future);
      // Must complete without throwing.
      await container
          .read(topicPostsProvider(10).notifier)
          .toggleReaction(5, 'love');

      final posts = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(posts.single.reactionCounts['like'], 1);
      expect(posts.single.reacted, ['like']);
    });
  });
}
