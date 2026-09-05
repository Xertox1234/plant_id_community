import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

/// A container with the fake API installed. Every provider under test is
/// autoDispose, so callers hold a `listen` on what they exercise — a bare
/// `read` would build a notifier and tear it down before the next call
/// (docs/patterns/riverpod.md → Unit-testing an @riverpod notifier).
ProviderContainer _container(FakeForumApi api) {
  final container = ProviderContainer(
    overrides: [forumApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('TopicDetail.toggleBookmark (todo 341)', () {
    test('flips optimistically, then keeps the server state', () async {
      final api = FakeForumApi()..topicDetail = topicDetail(id: 10);
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      final pending = container
          .read(topicDetailProvider(10).notifier)
          .toggleBookmark();
      // Optimistic: the flag is already flipped before the API resolves.
      expect(
        container.read(topicDetailProvider(10)).asData!.value.isBookmarked,
        isTrue,
      );
      await pending;

      expect(api.bookmarkCalls, [10]);
      expect(api.unbookmarkCalls, isEmpty);
      expect(
        container.read(topicDetailProvider(10)).asData!.value.isBookmarked,
        isTrue,
      );
    });

    test('unbookmarks when currently bookmarked', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, isBookmarked: true);
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await container.read(topicDetailProvider(10).notifier).toggleBookmark();

      expect(api.unbookmarkCalls, [10]);
      expect(api.bookmarkCalls, isEmpty);
      expect(
        container.read(topicDetailProvider(10)).asData!.value.isBookmarked,
        isFalse,
      );
    });

    test('a failed toggle reverts the optimistic flip and rethrows', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..failBookmarkWith = ApiException('rate limited', statusCode: 429);
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await expectLater(
        container.read(topicDetailProvider(10).notifier).toggleBookmark(),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 429)),
      );

      expect(
        container.read(topicDetailProvider(10)).asData!.value.isBookmarked,
        isFalse,
      );
    });

    test(
      'splices the mounted bookmarks feed in place and never refetches it',
      () async {
        final page1 = CursorPage(
          items: [
            topic(id: 1, title: 'first'),
            topic(id: 2, title: 'second'),
          ],
          next: 'https://api/forum/me/bookmarks/?cursor=p2',
        );
        final page2 = CursorPage(items: [topic(id: 3, title: 'third')]);
        final api = FakeForumApi()
          ..bookmarkPages = [page1, page2]
          ..topicDetail = topicDetail(id: 99, title: 'Newly saved');
        final container = _container(api);
        container.listen(bookmarksFeedProvider, (_, _) {});
        container.listen(topicDetailProvider(99), (_, _) {});
        await container.read(bookmarksFeedProvider.future);
        await container.read(bookmarksFeedProvider.notifier).loadMore();
        await container.read(topicDetailProvider(99).future);

        // Bookmark: inserted at the top, every loaded page kept.
        await container.read(topicDetailProvider(99).notifier).toggleBookmark();
        var items = container.read(bookmarksFeedProvider).asData!.value.items;
        expect(items.map((t) => t.id), [99, 1, 2, 3]);
        expect(items.first.title, 'Newly saved');

        // Unbookmark: the row goes, the rest stays.
        await container.read(topicDetailProvider(99).notifier).toggleBookmark();
        items = container.read(bookmarksFeedProvider).asData!.value.items;
        expect(items.map((t) => t.id), [1, 2, 3]);

        // No refetch of the feed at any point — page 1 + the loadMore only.
        expect(api.fetchBookmarksCalls, [null, page1.next]);
      },
    );
  });

  group('TopicDetail accepted answer (todo 341)', () {
    test('markSolution writes the server result, never a local flip', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        // The server is the authority — a result that names a DIFFERENT
        // post than the one asked for must win.
        ..solutionResult = const ForumSolutionResult(
          isSolved: true,
          solvedPostId: 7,
        );
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await container.read(topicDetailProvider(10).notifier).markSolution(5);

      expect(api.markSolutionCalls, [
        {'topicId': 10, 'postId': 5},
      ]);
      final detail = container.read(topicDetailProvider(10)).asData!.value;
      expect(detail.solvedPostId, 7);
      expect(detail.isSolved, isTrue);
    });

    test('clearSolution unsets the accepted answer', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10, solvedPostId: 5);
      final container = _container(api);
      container.listen(topicDetailProvider(10), (_, _) {});
      await container.read(topicDetailProvider(10).future);

      await container.read(topicDetailProvider(10).notifier).clearSolution();

      expect(api.clearSolutionCalls, [10]);
      final detail = container.read(topicDetailProvider(10)).asData!.value;
      expect(detail.solvedPostId, isNull);
      expect(detail.isSolved, isFalse);
    });

    test(
      'a refused mark rethrows, leaves the topic unsolved, reuses the key for '
      'a same-post retry, and rotates it for a different post',
      () async {
        final api = FakeForumApi()
          ..topicDetail = topicDetail(id: 10)
          ..failSolutionWith = ApiException('forbidden', statusCode: 403);
        final container = _container(api);
        container.listen(topicDetailProvider(10), (_, _) {});
        await container.read(topicDetailProvider(10).future);
        final notifier = container.read(topicDetailProvider(10).notifier);

        await expectLater(
          notifier.markSolution(5),
          throwsA(
            isA<ApiException>().having((e) => e.statusCode, 'status', 403),
          ),
        );
        expect(
          container.read(topicDetailProvider(10)).asData!.value.solvedPostId,
          isNull,
        );

        api.failSolutionWith = null;
        await notifier.markSolution(5); // same post → same key (replayed)
        await notifier.markSolution(6); // different post → new key
        expect(api.markSolutionKeys.length, 3);
        expect(api.markSolutionKeys[0], api.markSolutionKeys[1]);
        expect(api.markSolutionKeys[2], isNot(api.markSolutionKeys[1]));
      },
    );
  });

  group('TopicPosts.reportPost (todo 341)', () {
    test('reuses the key for a same-report retry and rotates when the report '
        'changes', () async {
      final api = FakeForumApi()
        ..posts = CursorPage(items: [post(id: 2, canReport: true)])
        ..failReportPostWith = ApiException('rate limited', statusCode: 429);
      final container = _container(api);
      container.listen(topicPostsProvider(10), (_, _) {});
      await container.read(topicPostsProvider(10).future);
      final notifier = container.read(topicPostsProvider(10).notifier);

      await expectLater(
        notifier.reportPost(postId: 2, reason: 'spam', detail: 'again'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 429)),
      );

      api.failReportPostWith = null;
      await notifier.reportPost(postId: 2, reason: 'spam', detail: 'again');
      await notifier.reportPost(postId: 2, reason: 'abuse');

      expect(api.reportPostCalls, [
        {'postId': 2, 'reason': 'spam', 'detail': 'again'},
        {'postId': 2, 'reason': 'spam', 'detail': 'again'},
        {'postId': 2, 'reason': 'abuse', 'detail': null},
      ]);
      expect(api.reportPostKeys.length, 3);
      expect(api.reportPostKeys[0], api.reportPostKeys[1]);
      expect(api.reportPostKeys[2], isNot(api.reportPostKeys[1]));
    });
  });

  group('Blocking an author (todo 341)', () {
    test('a block change collapses that author\'s posts on every loaded page '
        'without a refetch, and an unblock reveals them', () async {
      final page1 = CursorPage(
        items: [
          post(id: 1, authorOverride: author(username: 'alice')),
          post(id: 2, authorOverride: author(username: 'bob')),
        ],
        next: 'https://api/forum/topics/10/posts/?cursor=p2',
      );
      final page2 = CursorPage(
        items: [post(id: 3, authorOverride: author(username: 'alice'))],
      );
      final api = FakeForumApi()..postPages = [page1, page2];
      final container = _container(api);
      container.listen(topicPostsProvider(10), (_, _) {});
      await container.read(topicPostsProvider(10).future);
      await container.read(topicPostsProvider(10).notifier).loadMore();

      container
          .read(authorBlockChangesProvider.notifier)
          .emit(username: 'alice', blocked: true);
      var items = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(items.map((p) => p.id), [1, 2, 3]);
      expect(items.map((p) => p.isBlocked), [true, false, true]);

      container
          .read(authorBlockChangesProvider.notifier)
          .emit(username: 'alice', blocked: false);
      items = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(items.map((p) => p.isBlocked), [false, false, false]);

      expect(api.fetchPostsCalls, [null, page1.next]); // no refetch
    });

    test('ForumUserProfile.toggleBlock blocks optimistically, writes back the '
        'server state, clears the activity lists, and broadcasts', () async {
      final api = FakeForumApi()
        ..profile = profile(
          username: 'alice',
          canBlock: true,
          recentTopics: [profileTopicRefJson(id: 1, title: 'Monstera care')],
        )
        ..posts = CursorPage(
          items: [post(id: 1, authorOverride: author(username: 'alice'))],
        );
      final container = _container(api);
      container.listen(forumUserProfileProvider('alice'), (_, _) {});
      container.listen(topicPostsProvider(10), (_, _) {});
      await container.read(forumUserProfileProvider('alice').future);
      await container.read(topicPostsProvider(10).future);

      final pending = container
          .read(forumUserProfileProvider('alice').notifier)
          .toggleBlock();
      expect(
        container
            .read(forumUserProfileProvider('alice'))
            .asData!
            .value
            .isBlocked,
        isTrue,
      );
      await pending;

      expect(api.blockCalls, ['alice']);
      final profileState = container
          .read(forumUserProfileProvider('alice'))
          .asData!
          .value;
      expect(profileState.isBlocked, isTrue);
      expect(profileState.recentTopics, isEmpty);
      // The thread underneath collapsed alice's post in place.
      expect(
        container
            .read(topicPostsProvider(10))
            .asData!
            .value
            .items
            .single
            .isBlocked,
        isTrue,
      );

      await container
          .read(forumUserProfileProvider('alice').notifier)
          .toggleBlock();
      expect(api.unblockCalls, ['alice']);
      expect(
        container
            .read(forumUserProfileProvider('alice'))
            .asData!
            .value
            .isBlocked,
        isFalse,
      );
    });

    test('a failed block reverts, rethrows, and broadcasts nothing', () async {
      final api = FakeForumApi()
        ..profile = profile(username: 'alice', canBlock: true)
        ..posts = CursorPage(
          items: [post(id: 1, authorOverride: author(username: 'alice'))],
        )
        ..failBlockWith = ApiException('rate limited', statusCode: 429);
      final container = _container(api);
      container.listen(forumUserProfileProvider('alice'), (_, _) {});
      container.listen(topicPostsProvider(10), (_, _) {});
      await container.read(forumUserProfileProvider('alice').future);
      await container.read(topicPostsProvider(10).future);

      await expectLater(
        container
            .read(forumUserProfileProvider('alice').notifier)
            .toggleBlock(),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 429)),
      );

      expect(
        container
            .read(forumUserProfileProvider('alice'))
            .asData!
            .value
            .isBlocked,
        isFalse,
      );
      expect(
        container
            .read(topicPostsProvider(10))
            .asData!
            .value
            .items
            .single
            .isBlocked,
        isFalse,
      );
    });
  });

  group('BookmarksFeed (todo 341)', () {
    test(
      'loadMore fetches the second page via the verbatim cursor URL',
      () async {
        final page1 = CursorPage(
          items: [topic(id: 1)],
          next: 'https://api/forum/me/bookmarks/?cursor=p2',
        );
        final page2 = CursorPage(items: [topic(id: 2)]);
        final api = FakeForumApi()..bookmarkPages = [page1, page2];
        final container = _container(api);
        container.listen(bookmarksFeedProvider, (_, _) {});

        await container.read(bookmarksFeedProvider.future);
        await container.read(bookmarksFeedProvider.notifier).loadMore();

        final result = container.read(bookmarksFeedProvider).asData!.value;
        expect(result.items.map((t) => t.id), [1, 2]);
        expect(result.hasMore, isFalse);
        expect(api.fetchBookmarksCalls, [null, page1.next]);
      },
    );
  });

  group(
    're-entrancy guards (review: no opposite key-less writes on a double-tap)',
    () {
      test(
        'a second bookmark tap while the first is in flight is dropped',
        () async {
          final api = FakeForumApi()
            ..topicDetail = topicDetail(id: 5, isBookmarked: false);
          final container = _container(api);
          container.listen(topicDetailProvider(5), (_, _) {});
          await container.read(topicDetailProvider(5).future);
          final notifier = container.read(topicDetailProvider(5).notifier);

          final first = notifier.toggleBookmark();
          final second = notifier.toggleBookmark();
          await Future.wait([first, second]);

          expect(api.bookmarkCalls, [5]);
          expect(api.unbookmarkCalls, isEmpty);
          expect(
            container.read(topicDetailProvider(5)).asData!.value.isBookmarked,
            isTrue,
          );
        },
      );

      test(
        'a second block tap while the first is in flight is dropped',
        () async {
          final api = FakeForumApi()
            ..profile = profile(username: 'alice', canBlock: true);
          final container = _container(api);
          container.listen(forumUserProfileProvider('alice'), (_, _) {});
          await container.read(forumUserProfileProvider('alice').future);
          final notifier = container.read(
            forumUserProfileProvider('alice').notifier,
          );

          await Future.wait([notifier.toggleBlock(), notifier.toggleBlock()]);

          expect(api.blockCalls, ['alice']);
          expect(api.unblockCalls, isEmpty);
        },
      );

      test('a double-tap on mark-as-answer sends one request', () async {
        final api = FakeForumApi()
          ..topicDetail = topicDetail(id: 6, canMarkSolution: true);
        final container = _container(api);
        container.listen(topicDetailProvider(6), (_, _) {});
        await container.read(topicDetailProvider(6).future);
        final notifier = container.read(topicDetailProvider(6).notifier);

        await Future.wait([notifier.markSolution(7), notifier.markSolution(7)]);

        expect(api.markSolutionCalls.length, 1);
      });
    },
  );
}
