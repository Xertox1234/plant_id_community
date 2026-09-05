import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversation_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api, {String username = 'bob'}) => ProviderScope(
  overrides: [forumApiProvider.overrideWithValue(api)],
  child: MaterialApp(home: ForumConversationScreen(username: username)),
);

Finder _sendButton() => find.widgetWithIcon(IconButton, Icons.send);

void main() {
  group('ForumConversationScreen (todo 339)', () {
    testWidgets(
      'renders the newest-first page oldest → newest with own messages on '
      'the right and the other member in the app bar',
      (tester) async {
        final api = FakeForumApi()
          ..conversationWith = conversation(
            id: 7,
            otherUsername: 'bob',
            otherDisplayName: 'Bob Fern',
          )
          ..messages = [
            directMessage(id: 3, senderUsername: 'bob', body: 'third'),
            directMessage(id: 2, senderUsername: 'me', body: 'second'),
            directMessage(id: 1, senderUsername: 'bob', body: 'first'),
          ];

        await tester.pumpWidget(_wrap(api));
        await tester.pumpAndSettle();

        expect(find.text('Bob Fern'), findsOneWidget);
        // Visual order: oldest at the top.
        final firstY = tester.getTopLeft(find.text('first')).dy;
        final secondY = tester.getTopLeft(find.text('second')).dy;
        final thirdY = tester.getTopLeft(find.text('third')).dy;
        expect(firstY, lessThan(secondY));
        expect(secondY, lessThan(thirdY));
        // Own message sits to the right of the other member's.
        final mine = tester.getCenter(find.text('second')).dx;
        final theirs = tester.getCenter(find.text('first')).dx;
        expect(mine, greaterThan(theirs));
      },
    );

    testWidgets('an empty thread shows the say-hello placeholder', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(FakeForumApi()));
      await tester.pumpAndSettle();

      expect(find.textContaining('Say hello to bob'), findsOneWidget);
      // Nothing typed yet → Send is disabled.
      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNull);
    });

    testWidgets('Load older sits at the top and pages via the cursor', (
      tester,
    ) async {
      final page1 = CursorPage(
        items: [directMessage(id: 2, body: 'newer')],
        next: 'https://api/forum/conversations/7/messages/?cursor=older',
      );
      final page2 = CursorPage(items: [directMessage(id: 1, body: 'older')]);
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..messagePages = [page1, page2];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      final button = find.widgetWithText(OutlinedButton, 'Load older');
      expect(button, findsOneWidget);
      expect(
        tester.getTopLeft(button).dy,
        lessThan(tester.getTopLeft(find.text('newer')).dy),
      );

      await tester.tap(button);
      await tester.pumpAndSettle();

      expect(api.fetchMessagesCalls, [null, page1.next]);
      expect(find.text('older'), findsOneWidget);
      expect(
        tester.getTopLeft(find.text('older')).dy,
        lessThan(tester.getTopLeft(find.text('newer')).dy),
      );
      expect(button, findsNothing);
    });

    testWidgets('send appends the message and clears the composer', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..messages = [directMessage(id: 1, body: 'hi')];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNull);
      await tester.enterText(find.byType(TextField), 'How is the monstera?');
      await tester.pump();
      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNotNull);

      await tester.tap(_sendButton());
      await tester.pumpAndSettle();

      expect(api.sendMessageCalls, [
        {'username': 'bob', 'body': 'How is the monstera?'},
      ]);
      expect(find.text('How is the monstera?'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller?.text,
        isEmpty,
      );
      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNull);
    });

    testWidgets('whitespace-only input keeps Send disabled', (tester) async {
      final api = FakeForumApi()..conversationWith = conversation(id: 7);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), '   ');
      await tester.pump();

      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNull);
    });

    testWidgets('a 403 shows the blocked notice and keeps the draft', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..failSendMessageWith = ApiException(
          'You cannot message this user.',
          statusCode: 403,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'hello?');
      await tester.pump();
      await tester.tap(_sendButton());
      await tester.pumpAndSettle();

      expect(find.text("You can't message this member."), findsOneWidget);
      expect(tester.takeException(), isNull);
      // The draft survives a rejection so the user can retry or edit.
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller?.text,
        'hello?',
      );
    });

    testWidgets('a 400 surfaces the server message verbatim', (tester) async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..failSendMessageWith = ApiException(
          'Too many links.',
          statusCode: 400,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'http://a http://b');
      await tester.pump();
      await tester.tap(_sendButton());
      await tester.pumpAndSettle();

      expect(find.text('Too many links.'), findsOneWidget);
    });

    testWidgets(
      'long-pressing the other member\'s message opens the report sheet '
      'and submitting calls the API',
      (tester) async {
        final api = FakeForumApi()
          ..conversationWith = conversation(id: 7)
          ..messages = [
            directMessage(id: 42, senderUsername: 'bob', body: 'buy now!!!'),
          ];

        await tester.pumpWidget(_wrap(api));
        await tester.pumpAndSettle();

        await tester.longPress(find.text('buy now!!!'));
        await tester.pumpAndSettle();

        expect(find.text('Report message'), findsOneWidget);
        // No reason picked yet → submit disabled.
        final submit = find.widgetWithText(FilledButton, 'Report');
        expect(tester.widget<FilledButton>(submit).onPressed, isNull);

        await tester.tap(find.widgetWithText(ChoiceChip, 'Spam'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextField, 'Details (optional)'),
          'Third time this week',
        );
        await tester.tap(submit);
        await tester.pumpAndSettle();

        expect(api.reportMessageCalls, [
          {'messageId': 42, 'reason': 'spam', 'detail': 'Third time this week'},
        ]);
        expect(api.reportMessageKeys.single, isNotEmpty);
        expect(find.text('Reported'), findsOneWidget);
        expect(find.text('Report message'), findsNothing);
      },
    );

    testWidgets('own messages have no report affordance', (tester) async {
      final api = FakeForumApi()
        ..conversationWith = conversation(id: 7)
        ..messages = [directMessage(id: 1, senderUsername: 'me', body: 'mine')];

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      await tester.longPress(find.text('mine'));
      await tester.pumpAndSettle();

      expect(find.text('Report message'), findsNothing);
    });

    testWidgets('a failed load surfaces a retry, not a crash', (tester) async {
      // A fake that throws on the conversation lookup.
      final api = _ThrowingConversationApi();

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.widgetWithText(OutlinedButton, 'Retry'), findsOneWidget);

      api.shouldThrow = false;
      api.conversationWith = conversation(id: 7);
      await tester.tap(find.widgetWithText(OutlinedButton, 'Retry'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Say hello to bob'), findsOneWidget);
    });
  });
}

class _ThrowingConversationApi extends FakeForumApi {
  bool shouldThrow = true;

  @override
  Future<ForumConversation?> fetchConversationWith(String username) async {
    if (shouldThrow) throw ApiException('down', statusCode: 500);
    return super.fetchConversationWith(username);
  }
}
