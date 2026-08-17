import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

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

  group('TopicPosts.refreshAfterReply', () {
    test(
      'walks every page so a reply on the last page becomes visible',
      () async {
        // Todo 291: a new reply is oldest-first-ordered onto the LAST cursor
        // page. A single-page fixture would pass even with the old
        // page-1-only `invalidate` behaviour, proving nothing — this fixture
        // has the new reply ONLY on page 2.
        final page1 = CursorPage(
          items: [post(id: 1)],
          next: 'https://api/forum/topics/10/posts/?cursor=p2',
        );
        final page2 = CursorPage(items: [post(id: 2)]); // the new reply
        final api = FakeForumApi()..postPages = [page1, page2];
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(topicPostsProvider(10).future); // build(): page1 only
        await container
            .read(topicPostsProvider(10).notifier)
            .refreshAfterReply();

        final result = container.read(topicPostsProvider(10)).asData!.value;
        expect(result.items.map((p) => p.id), [1, 2]);
        expect(result.hasMore, isFalse);
        expect(result.isLoadingMore, isFalse);
      },
    );

    test('a single-page thread still returns just that page', () async {
      final api = FakeForumApi()..posts = CursorPage(items: [post(id: 1)]);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicPostsProvider(10).future);
      await container
          .read(topicPostsProvider(10).notifier)
          .refreshAfterReply();

      final result = container.read(topicPostsProvider(10)).asData!.value;
      expect(result.items.map((p) => p.id), [1]);
      expect(result.hasMore, isFalse);
    });

    test(
      'a mid-walk failure restores the prior list and rethrows',
      () async {
        final page1 = CursorPage(
          items: [post(id: 1)],
          next: 'https://api/forum/topics/10/posts/?cursor=p2',
        );
        final api = FakeForumApi()..postPages = [page1];
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(topicPostsProvider(10).future); // 1 call so far
        // Fail the 3rd fetchPosts call: build() is #1, refreshAfterReply's
        // page-1 restart is #2, its page-2 continuation is #3.
        api.throwOnFetchPostsCallNumber = 3;

        await expectLater(
          container.read(topicPostsProvider(10).notifier).refreshAfterReply(),
          throwsA(isA<ApiException>()),
        );

        final result = container.read(topicPostsProvider(10)).asData!.value;
        expect(result.items.map((p) => p.id), [1]); // prior list, not lost
        expect(result.isLoadingMore, isFalse); // spinner flag cleared
      },
    );
  });
}
