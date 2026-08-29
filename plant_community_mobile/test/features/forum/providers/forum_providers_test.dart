import 'dart:async';

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

        await container.read(
          topicPostsProvider(10).future,
        ); // build(): page1 only
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
      await container.read(topicPostsProvider(10).notifier).refreshAfterReply();

      final result = container.read(topicPostsProvider(10)).asData!.value;
      expect(result.items.map((p) => p.id), [1]);
      expect(result.hasMore, isFalse);
    });

    test('a mid-walk failure restores the prior list and rethrows', () async {
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
    });
  });

  group('TopicPosts.applyEditedPost (todo 292)', () {
    test('splices the updated post into place without a refetch', () async {
      final api = FakeForumApi()
        ..posts = CursorPage(
          items: [
            post(id: 1, body: const [ParagraphBlock('original')]),
          ],
        );
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicPostsProvider(10).future);
      final edited = post(id: 1, body: const [ParagraphBlock('edited')]);
      container.read(topicPostsProvider(10).notifier).applyEditedPost(edited);

      final items = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(items.single.body, [const ParagraphBlock('edited')]);
      // No extra fetchPosts call — proves this is a local splice, not an
      // invalidate-and-refetch (which would have called fetchPosts again).
      expect(api.fetchPostsCalls, hasLength(1));
    });

    test('a post id not currently in state is a no-op', () async {
      final api = FakeForumApi()..posts = CursorPage(items: [post(id: 1)]);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicPostsProvider(10).future);
      container
          .read(topicPostsProvider(10).notifier)
          .applyEditedPost(post(id: 999));

      final items = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(items.map((p) => p.id), [1]);
    });
  });

  group('TopicPosts.deletePost (todo 292)', () {
    test('removes the post from state on success', () async {
      final api = FakeForumApi()
        ..posts = CursorPage(items: [post(id: 1), post(id: 2)]);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicPostsProvider(10).future);
      await container.read(topicPostsProvider(10).notifier).deletePost(2);

      final items = container.read(topicPostsProvider(10)).asData!.value.items;
      expect(items.map((p) => p.id), [1]);
      expect(api.deletePostCalls, [2]);
    });

    test(
      'rethrows on failure and leaves the post in state (todo 292 AC3)',
      () async {
        final api = FakeForumApi()
          ..posts = CursorPage(items: [post(id: 1)])
          ..failDeletePostWith = ApiException(
            'Topic is closed or locked.',
            statusCode: 409,
          );
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(topicPostsProvider(10).future);
        await expectLater(
          container.read(topicPostsProvider(10).notifier).deletePost(1),
          throwsA(
            isA<ApiException>().having(
              (e) => e.message,
              'message',
              'Topic is closed or locked.',
            ),
          ),
        );

        final items = container
            .read(topicPostsProvider(10))
            .asData!
            .value
            .items;
        expect(items.map((p) => p.id), [1]); // unchanged — delete never applied
      },
    );
  });

  group('TopicDetail.toggleSubscription', () {
    test('subscribes when currently unsubscribed', () async {
      final api = FakeForumApi()..topicDetail = topicDetail(id: 10);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicDetailProvider(10).future);
      await container
          .read(topicDetailProvider(10).notifier)
          .toggleSubscription();

      expect(api.subscribeCalls, [10]);
      expect(api.unsubscribeCalls, isEmpty);
      expect(
        container.read(topicDetailProvider(10)).asData!.value.isSubscribed,
        isTrue,
      );
    });

    test('unsubscribes when currently subscribed', () async {
      final subscribed = topicDetail(id: 10).withSubscribed(true);
      final api = FakeForumApi()..topicDetail = subscribed;
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicDetailProvider(10).future);
      await container
          .read(topicDetailProvider(10).notifier)
          .toggleSubscription();

      expect(api.unsubscribeCalls, [10]);
      expect(api.subscribeCalls, isEmpty);
      expect(
        container.read(topicDetailProvider(10)).asData!.value.isSubscribed,
        isFalse,
      );
    });

    test('a failed toggle rethrows and leaves state unchanged', () async {
      final api = FakeForumApi()
        ..topicDetail = topicDetail(id: 10)
        ..failSubscriptionWith = ApiException('boom', statusCode: 500);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(topicDetailProvider(10).future);
      await expectLater(
        container.read(topicDetailProvider(10).notifier).toggleSubscription(),
        throwsA(isA<ApiException>()),
      );

      expect(
        container.read(topicDetailProvider(10)).asData!.value.isSubscribed,
        isFalse,
      );
    });
  });

  group('ForumUserProfile (todo 317)', () {
    test('fetches the profile for the given username', () async {
      final fixture = profile(username: 'alice', bio: 'I grow monsteras.');
      final api = FakeForumApi()..profile = fixture;
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      final result = await container.read(
        forumUserProfileProvider('alice').future,
      );

      // Asserts against the fake's recorded call, not just the fixture's own
      // content — the fixture is returned unconditionally regardless of the
      // `username` argument, so asserting only `result.author.username` would
      // pass even if a different username reached the API layer (final
      // whole-branch review, todo 317).
      expect(api.fetchProfileCalls, ['alice']);
      expect(result.bio, 'I grow monsteras.');
    });

    // The "no fixture" 404 path is covered at the screen level
    // (forum_user_profile_screen_test.dart) via testWidgets/pumpAndSettle,
    // not here: Riverpod's build()-failure handling schedules real-clock
    // retry bookkeeping that a bare test()/ProviderContainer (no Flutter
    // test binding, no fake clock) cannot settle deterministically —
    // pumpAndSettle's fake clock does.
  });

  group('NotificationsFeed', () {
    test(
      'loadMore fetches the second page via the verbatim cursor URL',
      () async {
        final page1 = CursorPage(
          items: [notification(id: 1)],
          next: 'https://api/forum/notifications/?cursor=p2',
        );
        final page2 = CursorPage(items: [notification(id: 2)]);
        final api = FakeForumApi()..notificationPages = [page1, page2];
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(notificationsFeedProvider.future);
        await container.read(notificationsFeedProvider.notifier).loadMore();

        final result = container.read(notificationsFeedProvider).asData!.value;
        expect(result.items.map((n) => n.id), [1, 2]);
        // DRF cursor `next`/`previous` are absolute URLs — must be fetched
        // verbatim, never re-prefixed with the API base (docs/rules/api.md).
        expect(api.fetchNotificationsCalls, [null, page1.next]);
      },
    );

    test(
      'markRead(id: ...) splices that row read and refreshes the badge',
      () async {
        final api = FakeForumApi()
          ..notifications = [
            notification(id: 1, readAt: null),
            notification(id: 2, readAt: null),
          ]
          ..unreadCount = 2;
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(notificationsFeedProvider.future);
        await container.read(unreadNotificationCountProvider.future);
        await container
            .read(notificationsFeedProvider.notifier)
            .markRead(id: 1);

        final items = container
            .read(notificationsFeedProvider)
            .asData!
            .value
            .items;
        expect(items.firstWhere((n) => n.id == 1).isRead, isTrue);
        expect(items.firstWhere((n) => n.id == 2).isRead, isFalse);
        expect(api.markReadCalls, [
          [1],
        ]);
        final unread = await container.read(
          unreadNotificationCountProvider.future,
        );
        expect(unread, 1);
      },
    );

    test('markRead() with no id marks every unread row read', () async {
      final api = FakeForumApi()
        ..notifications = [
          notification(id: 1, readAt: null),
          notification(id: 2, readAt: null),
        ]
        ..unreadCount = 2;
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(notificationsFeedProvider.future);
      await container.read(notificationsFeedProvider.notifier).markRead();

      final items = container
          .read(notificationsFeedProvider)
          .asData!
          .value
          .items;
      expect(items.every((n) => n.isRead), isTrue);
      expect(api.markReadCalls, [null]);
      final unread = await container.read(
        unreadNotificationCountProvider.future,
      );
      expect(unread, 0);
    });
  });

  group('ForumSearch', () {
    test('starts idle', () {
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(FakeForumApi())],
      );
      addTearDown(container.dispose);

      expect(
        container.read(forumSearchProvider).status,
        ForumSearchStatus.idle,
      );
    });

    test(
      'an empty/whitespace query resets to idle without calling the API',
      () async {
        final api = FakeForumApi();
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(forumSearchProvider.notifier).search(query: '   ');

        expect(
          container.read(forumSearchProvider).status,
          ForumSearchStatus.idle,
        );
        expect(api.searchCalls, isEmpty);
      },
    );

    test('search() populates topics/posts and pagination flags', () async {
      final api = FakeForumApi()
        ..searchResult = const ForumSearchPage(
          topics: [
            ForumSearchTopicHit(
              id: 1,
              slug: 'monstera',
              title: 'Monstera care',
              replyCount: 3,
              viewCount: 12,
              isPinned: false,
              isSolved: false,
              boardId: 1,
              boardSlug: 'general',
            ),
          ],
          posts: [],
          topicsHasMore: true,
          postsHasMore: false,
          page: 1,
        );
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container
          .read(forumSearchProvider.notifier)
          .search(query: 'monstera');

      final state = container.read(forumSearchProvider);
      expect(state.status, ForumSearchStatus.data);
      expect(state.topics, hasLength(1));
      expect(state.topics.single.title, 'Monstera care');
      expect(state.hasMore, isTrue);
      expect(api.searchCalls.single['q'], 'monstera');
      expect(api.searchCalls.single['semantic'], isTrue);
    });

    test('a search failure surfaces an error state', () async {
      final api = FakeForumApi()
        ..failSearchWith = ApiException('temporary failure', statusCode: 500);
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(forumSearchProvider.notifier).search(query: 'q');

      expect(
        container.read(forumSearchProvider).status,
        ForumSearchStatus.error,
      );
    });

    test(
      'loadMore() appends to both sections and advances the shared page cursor',
      () async {
        final api = FakeForumApi()
          ..searchPages = {
            1: const ForumSearchPage(
              topics: [
                ForumSearchTopicHit(
                  id: 1,
                  slug: 't1',
                  title: 'Topic 1',
                  replyCount: 0,
                  viewCount: 0,
                  isPinned: false,
                  isSolved: false,
                  boardId: 1,
                  boardSlug: 'general',
                ),
              ],
              posts: [],
              topicsHasMore: true,
              postsHasMore: false,
              page: 1,
            ),
            2: const ForumSearchPage(
              topics: [
                ForumSearchTopicHit(
                  id: 2,
                  slug: 't2',
                  title: 'Topic 2',
                  replyCount: 0,
                  viewCount: 0,
                  isPinned: false,
                  isSolved: false,
                  boardId: 1,
                  boardSlug: 'general',
                ),
              ],
              posts: [],
              topicsHasMore: false,
              postsHasMore: false,
              page: 2,
            ),
          };
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container
            .read(forumSearchProvider.notifier)
            .search(query: 'topic');
        await container.read(forumSearchProvider.notifier).loadMore();

        final state = container.read(forumSearchProvider);
        expect(state.topics.map((t) => t.title), ['Topic 1', 'Topic 2']);
        expect(state.hasMore, isFalse);
        expect(state.page, 2);
        expect(api.searchCalls.map((c) => c['page']), [1, 2]);
      },
    );

    test('loadMore() is a no-op when there is nothing more to load', () async {
      final api = FakeForumApi()
        ..searchResult = const ForumSearchPage(
          topics: [],
          posts: [],
          topicsHasMore: false,
          postsHasMore: false,
          page: 1,
        );
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await container.read(forumSearchProvider.notifier).search(query: 'q');
      await container.read(forumSearchProvider.notifier).loadMore();

      expect(api.searchCalls, hasLength(1)); // only the initial search
    });

    test('a stale response from an earlier search does not overwrite a '
        'newer search\'s result (code review: the double-tap race)', () async {
      final firstGate = Completer<ForumSearchPage>();
      final secondGate = Completer<ForumSearchPage>();
      final api = FakeForumApi()..searchGates = [firstGate, secondGate];
      final container = ProviderContainer(
        overrides: [forumApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      // Two overlapping searches — neither has resolved yet.
      final firstSearch = container
          .read(forumSearchProvider.notifier)
          .search(query: 'first');
      final secondSearch = container
          .read(forumSearchProvider.notifier)
          .search(query: 'second');

      // The FIRST (now-stale) request resolves LAST, after the second.
      secondGate.complete(
        const ForumSearchPage(
          topics: [
            ForumSearchTopicHit(
              id: 2,
              slug: 'second',
              title: 'Second result',
              replyCount: 0,
              viewCount: 0,
              isPinned: false,
              isSolved: false,
              boardId: 1,
              boardSlug: 'general',
            ),
          ],
          posts: [],
          topicsHasMore: false,
          postsHasMore: false,
          page: 1,
        ),
      );
      await secondSearch;
      firstGate.complete(
        const ForumSearchPage(
          topics: [
            ForumSearchTopicHit(
              id: 1,
              slug: 'first',
              title: 'First result (stale)',
              replyCount: 0,
              viewCount: 0,
              isPinned: false,
              isSolved: false,
              boardId: 1,
              boardSlug: 'general',
            ),
          ],
          posts: [],
          topicsHasMore: false,
          postsHasMore: false,
          page: 1,
        ),
      );
      await firstSearch;

      final state = container.read(forumSearchProvider);
      expect(state.query, 'second');
      expect(state.topics.single.title, 'Second result');
    });

    test(
      'semantic_status "unavailable" is surfaced as a state, not an error',
      () async {
        final api = FakeForumApi()
          ..searchResult = const ForumSearchPage(
            topics: [],
            posts: [],
            topicsHasMore: false,
            postsHasMore: false,
            page: 1,
            semanticStatus: ForumSemanticStatus.unavailable,
          );
        final container = ProviderContainer(
          overrides: [forumApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);

        await container.read(forumSearchProvider.notifier).search(query: 'q');

        final state = container.read(forumSearchProvider);
        expect(state.status, ForumSearchStatus.data);
        expect(state.semanticStatus, ForumSemanticStatus.unavailable);
      },
    );
  });
}
