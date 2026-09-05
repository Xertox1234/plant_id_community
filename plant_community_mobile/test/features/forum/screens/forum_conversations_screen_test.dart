import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversations_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api) => ProviderScope(
  overrides: [forumApiProvider.overrideWithValue(api)],
  child: const MaterialApp(home: ForumConversationsScreen()),
);

void main() {
  group('ForumConversationsScreen (todo 339)', () {
    testWidgets(
      'lists conversations with the other member, preview, and unread chip',
      (tester) async {
        final api = FakeForumApi()
          ..conversations = [
            conversation(
              id: 1,
              otherUsername: 'bob',
              otherDisplayName: 'Bob Fern',
              unreadCount: 2,
              lastMessageBody: 'Is it root rot?',
            ),
            conversation(
              id: 2,
              otherUsername: 'carol',
              lastMessageBody: 'Thanks for the cutting!',
              lastMessageIsMine: true,
            ),
          ];

        await tester.pumpWidget(_wrap(api));
        await tester.pumpAndSettle();

        expect(find.text('Bob Fern'), findsOneWidget);
        expect(find.text('Is it root rot?'), findsOneWidget);
        // Unread count chip on the unread row only.
        expect(find.widgetWithText(Badge, '2'), findsOneWidget);
        expect(find.byType(Badge), findsOneWidget);
        // Own last message is prefixed so the reader knows who spoke last.
        expect(find.text('You: Thanks for the cutting!'), findsOneWidget);
        expect(find.text('carol'), findsOneWidget);
      },
    );

    testWidgets('unread rows read bold; read rows do not', (tester) async {
      final api = FakeForumApi()
        ..conversations = [
          conversation(
            id: 1,
            otherUsername: 'bob',
            unreadCount: 1,
            lastMessageBody: 'unread preview',
          ),
          conversation(
            id: 2,
            otherUsername: 'carol',
            lastMessageBody: 'read preview',
          ),
        ];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      final unread = tester.widget<Text>(find.text('bob'));
      final read = tester.widget<Text>(find.text('carol'));
      expect(unread.style?.fontWeight, FontWeight.w700);
      expect(read.style?.fontWeight, isNot(FontWeight.w700));
    });

    testWidgets('empty state renders when there are no conversations', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(FakeForumApi()));
      await tester.pumpAndSettle();

      expect(find.text('No messages yet.'), findsOneWidget);
    });

    testWidgets('load more fetches the next page via the verbatim cursor URL', (
      tester,
    ) async {
      final page1 = CursorPage(
        items: [conversation(id: 1, otherUsername: 'bob')],
        next: 'https://api/forum/conversations/?cursor=p2',
      );
      final page2 = CursorPage(
        items: [conversation(id: 2, otherUsername: 'carol')],
      );
      final api = FakeForumApi()..conversationPages = [page1, page2];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(OutlinedButton, 'Load more'));
      await tester.pumpAndSettle();

      expect(api.fetchConversationsCalls, [null, page1.next]);
      expect(find.byType(ListTile), findsNWidgets(2));
      expect(find.widgetWithText(OutlinedButton, 'Load more'), findsNothing);
    });

    testWidgets('a conversation with no messages yet shows a placeholder '
        'preview and never crashes on the null last_message', (tester) async {
      final api = FakeForumApi()
        ..conversations = [conversation(id: 1, otherUsername: 'bob')];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No messages yet.'), findsOneWidget);
    });
  });
}
