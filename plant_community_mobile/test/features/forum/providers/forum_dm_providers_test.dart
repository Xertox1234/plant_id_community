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
  group('ConversationsFeed (todo 339)', () {
    test(
      'loadMore fetches the second page via the verbatim cursor URL',
      () async {
        final page1 = CursorPage(
          items: [conversation(id: 1, otherUsername: 'bob')],
          next: 'https://api/forum/conversations/?cursor=p2',
        );
        final page2 = CursorPage(
          items: [conversation(id: 2, otherUsername: 'carol')],
        );
        final api = FakeForumApi()..conversationPages = [page1, page2];
        final container = _container(api);
        container.listen(conversationsFeedProvider, (_, _) {});

        await container.read(conversationsFeedProvider.future);
        await container.read(conversationsFeedProvider.notifier).loadMore();

        final result = container.read(conversationsFeedProvider).asData!.value;
        expect(result.items.map((c) => c.id), [1, 2]);
        expect(result.hasMore, isFalse);
        // DRF cursor `next` is an absolute URL — fetched verbatim, never
        // re-prefixed with the API base (docs/rules/api.md).
        expect(api.fetchConversationsCalls, [null, page1.next]);
      },
    );
  });

  test('unreadConversationCount reads the badge count', () async {
    final api = FakeForumApi()..unreadConversationCount = 4;
    final container = _container(api);
    expect(await container.read(unreadConversationCountProvider.future), 4);
  });

  group('ConversationThread (todo 339)', () {
    test('build reverses the newest-first page into oldest → newest and holds '
        'the resolved conversation', () async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7, otherUsername: 'bob')
        ..messages = [
          directMessage(id: 3, senderUsername: 'me', body: 'third'),
          directMessage(id: 2, senderUsername: 'bob', body: 'second'),
          directMessage(id: 1, senderUsername: 'me', body: 'first'),
        ];
      final container = _container(api);
      container.listen(conversationThreadProvider('bob'), (_, _) {});

      final thread = await container.read(
        conversationThreadProvider('bob').future,
      );

      expect(thread.conversation?.id, 7);
      expect(thread.messages.map((m) => m.id), [1, 2, 3]);
      expect(thread.hasOlder, isFalse);
      expect(api.fetchConversationWithCalls, ['bob']);
      expect(api.fetchMessagesCalls, [null]);
    });

    test('build with no conversation yet yields an empty thread', () async {
      final api = FakeForumApi(); // conversationWith stays null (404)
      final container = _container(api);
      container.listen(conversationThreadProvider('bob'), (_, _) {});

      final thread = await container.read(
        conversationThreadProvider('bob').future,
      );

      expect(thread.conversation, isNull);
      expect(thread.messages, isEmpty);
      // No conversation id to page — the messages endpoint is never hit.
      expect(api.fetchMessagesCalls, isEmpty);
    });

    test(
      'loadOlder prepends the older page (reversed) via the verbatim cursor',
      () async {
        final page1 = CursorPage(
          items: [
            directMessage(id: 6),
            directMessage(id: 5),
            directMessage(id: 4),
          ],
          next: 'https://api/forum/conversations/7/messages/?cursor=older',
        );
        final page2 = CursorPage(
          items: [
            directMessage(id: 3),
            directMessage(id: 2),
            directMessage(id: 1),
          ],
        );
        final api = FakeForumApi()
          ..conversationWith = conversation(id: 7)
          ..messagePages = [page1, page2];
        final container = _container(api);
        container.listen(conversationThreadProvider('bob'), (_, _) {});

        await container.read(conversationThreadProvider('bob').future);
        final before = container
            .read(conversationThreadProvider('bob'))
            .asData!
            .value;
        expect(before.messages.map((m) => m.id), [4, 5, 6]);
        expect(before.hasOlder, isTrue);

        await container
            .read(conversationThreadProvider('bob').notifier)
            .loadOlder();

        final after = container
            .read(conversationThreadProvider('bob'))
            .asData!
            .value;
        expect(after.messages.map((m) => m.id), [1, 2, 3, 4, 5, 6]);
        expect(after.hasOlder, isFalse);
        expect(after.isLoadingOlder, isFalse);
        expect(api.fetchMessagesCalls, [null, page1.next]);
      },
    );

    test('send appends the returned message and refreshes the badge', () async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..messages = [directMessage(id: 1, body: 'hi')]
        ..unreadConversationCount = 1;
      final container = _container(api);
      container.listen(conversationThreadProvider('bob'), (_, _) {});
      container.listen(unreadConversationCountProvider, (_, _) {});
      await container.read(conversationThreadProvider('bob').future);
      expect(await container.read(unreadConversationCountProvider.future), 1);

      // The server "reads" nothing on send, but another client may have —
      // the badge must be re-fetched, not locally adjusted.
      api.unreadConversationCount = 0;
      await container
          .read(conversationThreadProvider('bob').notifier)
          .send('  hello there  ');

      final thread = container
          .read(conversationThreadProvider('bob'))
          .asData!
          .value;
      expect(thread.messages.map((m) => m.body), ['hi', 'hello there']);
      expect(thread.isSending, isFalse);
      expect(api.sendMessageCalls, [
        {'username': 'bob', 'body': 'hello there'},
      ]);
      expect(api.sendMessageKeys.single, isNotEmpty);
      expect(await container.read(unreadConversationCountProvider.future), 0);
    });

    test('the first send resolves the conversation for the thread', () async {
      final api = FakeForumApi(); // no conversation yet
      final container = _container(api);
      container.listen(conversationThreadProvider('bob'), (_, _) {});
      await container.read(conversationThreadProvider('bob').future);

      // Server creates the row on first send; the next lookup finds it.
      api.conversationWith = conversation(id: 9, otherUsername: 'bob');
      await container
          .read(conversationThreadProvider('bob').notifier)
          .send('first!');

      final thread = container
          .read(conversationThreadProvider('bob'))
          .asData!
          .value;
      expect(thread.conversation?.id, 9);
      expect(thread.messages.single.body, 'first!');
      expect(api.fetchConversationWithCalls, ['bob', 'bob']);
    });

    test('a rejected send rethrows, clears the sending flag, and keeps the '
        'idempotency key for a same-body retry', () async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..failSendMessageWith = ApiException('blocked', statusCode: 403);
      final container = _container(api);
      container.listen(conversationThreadProvider('bob'), (_, _) {});
      await container.read(conversationThreadProvider('bob').future);
      final notifier = container.read(
        conversationThreadProvider('bob').notifier,
      );

      await expectLater(
        notifier.send('hello'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
      );
      expect(
        container
            .read(conversationThreadProvider('bob'))
            .asData!
            .value
            .isSending,
        isFalse,
      );

      // Same body → same key (server replays); new body → new key.
      api.failSendMessageWith = null;
      await notifier.send('hello');
      await notifier.send('different');
      expect(api.sendMessageKeys.length, 3);
      expect(api.sendMessageKeys[0], api.sendMessageKeys[1]);
      expect(api.sendMessageKeys[2], isNot(api.sendMessageKeys[1]));
    });

    test('reading the thread refreshes the unread badge', () async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..messages = [directMessage(id: 1)]
        ..unreadConversationCount = 2;
      final container = _container(api);
      container.listen(unreadConversationCountProvider, (_, _) {});
      expect(await container.read(unreadConversationCountProvider.future), 2);

      // Opening the thread marks it read server-side.
      api.unreadConversationCount = 1;
      container.listen(conversationThreadProvider('bob'), (_, _) {});
      await container.read(conversationThreadProvider('bob').future);

      expect(await container.read(unreadConversationCountProvider.future), 1);
    });
  });

  group(
    'ConversationsFeed local splices (review: never collapse loaded pages)',
    () {
      test(
        'markRead zeroes only that row and keeps every loaded page',
        () async {
          final page1 = CursorPage(
            items: [
              conversation(id: 1, otherUsername: 'bob', unreadCount: 2),
              conversation(id: 2, otherUsername: 'carol', unreadCount: 1),
            ],
            next: 'https://api/forum/conversations/?cursor=p2',
          );
          final page2 = CursorPage(
            items: [conversation(id: 3, otherUsername: 'dave', unreadCount: 3)],
          );
          final api = FakeForumApi()..conversationPages = [page1, page2];
          final container = _container(api);
          container.listen(conversationsFeedProvider, (_, _) {});
          await container.read(conversationsFeedProvider.future);
          await container.read(conversationsFeedProvider.notifier).loadMore();

          container.read(conversationsFeedProvider.notifier).markRead(2);

          final items = container
              .read(conversationsFeedProvider)
              .asData!
              .value
              .items;
          expect(items.map((c) => c.id), [1, 2, 3]);
          expect(items.map((c) => c.unreadCount), [2, 0, 3]);
          expect(api.fetchConversationsCalls, [null, page1.next]); // no refetch
        },
      );

      test(
        'applyActivity moves the row to the top with the new preview, or inserts a new one',
        () async {
          final api = FakeForumApi()
            ..conversationPages = [
              CursorPage(
                items: [
                  conversation(id: 1, otherUsername: 'bob'),
                  conversation(id: 2, otherUsername: 'carol'),
                ],
              ),
            ];
          final container = _container(api);
          container.listen(conversationsFeedProvider, (_, _) {});
          await container.read(conversationsFeedProvider.future);
          final notifier = container.read(conversationsFeedProvider.notifier);

          notifier.applyActivity(
            conversation(id: 2, otherUsername: 'carol').copyWith(
              lastMessage: const ForumLastMessage(body: 'sent', isMine: true),
            ),
          );
          var items = container
              .read(conversationsFeedProvider)
              .asData!
              .value
              .items;
          expect(items.map((c) => c.id), [2, 1]);
          expect(items.first.lastMessage?.body, 'sent');
          expect(items.first.lastMessage?.isMine, isTrue);

          notifier.applyActivity(conversation(id: 9, otherUsername: 'erin'));
          items = container.read(conversationsFeedProvider).asData!.value.items;
          expect(items.map((c) => c.id), [9, 2, 1]);
          expect(api.fetchConversationsCalls, [null]);
        },
      );
    },
  );
}
