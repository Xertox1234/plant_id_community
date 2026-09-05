import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

/// A container with the fake API installed. Every provider under test is
/// autoDispose, so callers hold a `listen` on what they exercise
/// (docs/patterns/riverpod.md → Unit-testing an @riverpod notifier).
ProviderContainer _container(FakeForumApi api) {
  final container = ProviderContainer(
    overrides: [forumApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

ConversationThreadState _thread(ProviderContainer c, int id) =>
    c.read(groupConversationThreadProvider(id)).asData!.value;

List<ForumConversation> _inbox(ProviderContainer c) =>
    c.read(conversationsFeedProvider).asData!.value.items;

void main() {
  group('GroupConversationThread (todo 350)', () {
    test('build takes the row from the mounted inbox (no refetch), reverses '
        'the newest-first page and marks the inbox row read', () async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(id: 12, unreadCount: 2, canManage: true),
          conversation(id: 1, otherUsername: 'bob'),
        ]
        ..messages = [
          directMessage(id: 3, conversationId: 12, senderUsername: 'ada'),
          directMessage(id: 2, conversationId: 12, senderUsername: 'me'),
          directMessage(id: 1, conversationId: 12, senderUsername: 'bob'),
        ]
        ..unreadConversationCount = 1;
      final container = _container(api);
      container.listen(conversationsFeedProvider, (_, _) {});
      container.listen(unreadConversationCountProvider, (_, _) {});
      await container.read(conversationsFeedProvider.future);
      expect(await container.read(unreadConversationCountProvider.future), 1);

      api.unreadConversationCount = 0;
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      final thread = await container.read(
        groupConversationThreadProvider(12).future,
      );

      expect(thread.conversation?.id, 12);
      expect(thread.conversation?.title, 'Seed swap committee');
      expect(thread.conversation?.canManage, isTrue);
      expect(thread.messages.map((m) => m.id), [1, 2, 3]);
      expect(thread.hasOlder, isFalse);
      // The inbox already held the row — page 1 was fetched once, by the
      // inbox itself, never again by the thread, and the cache hit spared
      // the by-id GET entirely.
      expect(api.fetchConversationsCalls, [null]);
      expect(api.fetchConversationCalls, isEmpty);
      expect(api.fetchConversationWithCalls, isEmpty);
      expect(api.fetchMessagesCalls, [null]);
      expect(_inbox(container).first.unreadCount, 0);
      expect(await container.read(unreadConversationCountProvider.future), 0);
    });

    test('build without a mounted inbox resolves through the by-id detail GET '
        '— the exact call — and never scans inbox page 1', () async {
      final api = FakeForumApi()
        ..conversationDetail = groupConversation(id: 12, title: 'Cuttings')
        ..messages = [directMessage(id: 1, conversationId: 12)];
      final container = _container(api);
      container.listen(groupConversationThreadProvider(12), (_, _) {});

      final thread = await container.read(
        groupConversationThreadProvider(12).future,
      );

      expect(thread.conversation?.title, 'Cuttings');
      expect(api.fetchConversationCalls, [12]);
      // Scanning the inbox would leave every group past page 1 unresolvable.
      expect(api.fetchConversationsCalls, isEmpty);
      expect(thread.messages.single.id, 1);
      expect(thread.isUnavailable, isFalse);
    });

    test('a 404 from the detail GET is the unavailable state — no messages '
        'are fetched, and retry re-fetches', () async {
      final api = FakeForumApi()
        ..messages = [directMessage(id: 1, conversationId: 99)];
      final container = _container(api);
      container.listen(groupConversationThreadProvider(99), (_, _) {});

      final thread = await container.read(
        groupConversationThreadProvider(99).future,
      );

      expect(thread.isUnavailable, isTrue);
      expect(thread.conversation, isNull);
      expect(thread.messages, isEmpty);
      expect(api.fetchConversationCalls, [99]);
      expect(api.fetchMessagesCalls, isEmpty);

      // Re-added since: invalidating re-runs the GET and the thread returns.
      api.conversationDetail = groupConversation(id: 99, title: 'Cuttings');
      container.invalidate(groupConversationThreadProvider(99));
      final retried = await container.read(
        groupConversationThreadProvider(99).future,
      );
      expect(retried.isUnavailable, isFalse);
      expect(retried.conversation?.title, 'Cuttings');
      expect(api.fetchConversationCalls, [99, 99]);
      expect(retried.messages.single.id, 1);
    });

    test('a non-404 failure on the detail GET stays an error, never the '
        'unavailable state', () async {
      final api = FakeForumApi()
        ..failFetchConversationWith = ApiException('boom', statusCode: 500);
      final container = _container(api);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      // Not `await …future`: Riverpod retries a failed build with backoff,
      // so that future stays pending. The emitted state is the assertion.
      await Future<void>.delayed(Duration.zero);

      final state = container.read(groupConversationThreadProvider(12));
      expect(state.error, isA<ApiException>());
      expect(state.hasValue, isFalse);
      // A transient 5xx must never read as "this group is gone".
      expect(api.fetchConversationCalls, [12]);
      expect(api.fetchMessagesCalls, isEmpty);
    });

    test('send goes through the by-id endpoint (never the username one), '
        'appends the echo and moves the inbox row to the top', () async {
      final api = FakeForumApi()
        ..conversations = [
          conversation(id: 1, otherUsername: 'bob'),
          groupConversation(id: 12, canManage: true),
        ]
        ..messages = [directMessage(id: 1, conversationId: 12, body: 'hi')];
      final container = _container(api);
      container.listen(conversationsFeedProvider, (_, _) {});
      await container.read(conversationsFeedProvider.future);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);

      await container
          .read(groupConversationThreadProvider(12).notifier)
          .send('  hello all  ');

      expect(api.sendConversationMessageCalls, [
        {'conversationId': 12, 'body': 'hello all'},
      ]);
      expect(api.sendConversationMessageKeys.single, isNotEmpty);
      expect(api.sendMessageCalls, isEmpty);
      final thread = _thread(container, 12);
      expect(thread.messages.map((m) => m.body), ['hi', 'hello all']);
      expect(thread.isSending, isFalse);
      final inbox = _inbox(container);
      expect(inbox.map((c) => c.id), [12, 1]);
      expect(inbox.first.lastMessage?.body, 'hello all');
      expect(inbox.first.lastMessage?.isMine, isTrue);
      expect(inbox.first.lastMessage?.sender?.username, 'me');
      expect(inbox.first.isGroup, isTrue);
      expect(inbox.first.title, 'Seed swap committee');
    });

    test('a rejected send rethrows, clears the flag, and reuses the key for '
        'a same-body retry', () async {
      final api = FakeForumApi()
        ..conversations = [groupConversation(id: 12)]
        ..failSendConversationMessageWith = ApiException(
          'You cannot message this group.',
          statusCode: 403,
        );
      final container = _container(api);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);
      final notifier = container.read(
        groupConversationThreadProvider(12).notifier,
      );

      await expectLater(
        notifier.send('hello'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
      );
      expect(_thread(container, 12).isSending, isFalse);

      api.failSendConversationMessageWith = null;
      await notifier.send('hello');
      await notifier.send('different');
      expect(api.sendConversationMessageKeys.length, 3);
      expect(
        api.sendConversationMessageKeys[0],
        api.sendConversationMessageKeys[1],
      );
      expect(
        api.sendConversationMessageKeys[2],
        isNot(api.sendConversationMessageKeys[1]),
      );
    });

    test('loadOlder prepends the older page via the verbatim cursor', () async {
      final page1 = CursorPage(
        items: [
          directMessage(id: 4, conversationId: 12),
          directMessage(id: 3, conversationId: 12),
        ],
        next: 'https://api/forum/conversations/12/messages/?cursor=older',
      );
      final page2 = CursorPage(
        items: [
          directMessage(id: 2, conversationId: 12),
          directMessage(id: 1, conversationId: 12),
        ],
      );
      final api = FakeForumApi()
        ..conversations = [groupConversation(id: 12)]
        ..messagePages = [page1, page2];
      final container = _container(api);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);
      expect(_thread(container, 12).hasOlder, isTrue);

      await container
          .read(groupConversationThreadProvider(12).notifier)
          .loadOlder();

      expect(_thread(container, 12).messages.map((m) => m.id), [1, 2, 3, 4]);
      expect(_thread(container, 12).hasOlder, isFalse);
      expect(api.fetchMessagesCalls, [null, page1.next]);
    });

    test('addMember replaces the row with the server\'s and splices the inbox '
        'row IN PLACE (membership is not activity)', () async {
      final api = FakeForumApi()
        ..conversations = [
          conversation(id: 1, otherUsername: 'bob'),
          groupConversation(
            id: 12,
            memberUsernames: const ['ada', 'bob'],
            canManage: true,
          ),
        ];
      final container = _container(api);
      container.listen(conversationsFeedProvider, (_, _) {});
      await container.read(conversationsFeedProvider.future);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);

      await container
          .read(groupConversationThreadProvider(12).notifier)
          .addMember('carol');

      expect(api.addParticipantCalls, [
        {'conversationId': 12, 'username': 'carol'},
      ]);
      final row = _thread(container, 12).conversation;
      expect(row?.participants.map((p) => p.username), [
        'me',
        'ada',
        'bob',
        'carol',
      ]);
      expect(row?.participantCount, 4);
      final inbox = _inbox(container);
      expect(inbox.map((c) => c.id), [1, 12]); // position kept
      expect(inbox[1].participantCount, 4);
      expect(api.fetchConversationsCalls, [null]); // never refetched
    });

    test('removeMember trims the roster locally after the 204', () async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            memberUsernames: const ['ada', 'bob'],
            canManage: true,
          ),
        ];
      final container = _container(api);
      container.listen(conversationsFeedProvider, (_, _) {});
      await container.read(conversationsFeedProvider.future);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);

      await container
          .read(groupConversationThreadProvider(12).notifier)
          .removeMember('bob');

      expect(api.removeParticipantCalls, [
        {'conversationId': 12, 'username': 'bob'},
      ]);
      final row = _thread(container, 12).conversation;
      expect(row?.participants.map((p) => p.username), ['me', 'ada']);
      expect(row?.participantCount, 2);
      expect(_inbox(container).single.participantCount, 2);
    });

    test('a refused removal rethrows and leaves the roster intact', () async {
      final api = FakeForumApi()
        ..conversations = [groupConversation(id: 12, canManage: true)]
        ..failRemoveParticipantWith = ApiException('nope', statusCode: 403);
      final container = _container(api);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);

      await expectLater(
        container
            .read(groupConversationThreadProvider(12).notifier)
            .removeMember('bob'),
        throwsA(isA<ApiException>()),
      );
      expect(_thread(container, 12).conversation?.participants.length, 3);
    });

    test('leave removes ME and drops the inbox row', () async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(id: 12, creatorUsername: 'ada'),
          conversation(id: 1, otherUsername: 'bob'),
        ];
      final container = _container(api);
      container.listen(conversationsFeedProvider, (_, _) {});
      await container.read(conversationsFeedProvider.future);
      container.listen(groupConversationThreadProvider(12), (_, _) {});
      await container.read(groupConversationThreadProvider(12).future);

      await container
          .read(groupConversationThreadProvider(12).notifier)
          .leave('me');

      expect(api.removeParticipantCalls, [
        {'conversationId': 12, 'username': 'me'},
      ]);
      expect(_inbox(container).map((c) => c.id), [1]);
      expect(api.fetchConversationsCalls, [null]);
    });
  });

  group('ConversationsFeed roster splices (todo 350)', () {
    test('replaceRow rewrites in place and remove drops, both keeping every '
        'loaded page', () async {
      final page1 = CursorPage(
        items: [
          conversation(id: 1, otherUsername: 'bob'),
          groupConversation(id: 12, memberUsernames: const ['ada']),
        ],
        next: 'https://api/forum/conversations/?cursor=p2',
      );
      final page2 = CursorPage(
        items: [conversation(id: 3, otherUsername: 'dave')],
      );
      final api = FakeForumApi()..conversationPages = [page1, page2];
      final container = _container(api);
      container.listen(conversationsFeedProvider, (_, _) {});
      await container.read(conversationsFeedProvider.future);
      await container.read(conversationsFeedProvider.notifier).loadMore();
      final notifier = container.read(conversationsFeedProvider.notifier);

      notifier.replaceRow(
        groupConversation(id: 12, memberUsernames: const ['ada', 'carol']),
      );
      var items = _inbox(container);
      expect(items.map((c) => c.id), [1, 12, 3]);
      expect(items[1].participantCount, 3);

      notifier.replaceRow(groupConversation(id: 77)); // unknown: no-op
      expect(_inbox(container).map((c) => c.id), [1, 12, 3]);

      notifier.remove(12);
      items = _inbox(container);
      expect(items.map((c) => c.id), [1, 3]);
      expect(api.fetchConversationsCalls, [null, page1.next]); // no refetch
    });
  });
}
