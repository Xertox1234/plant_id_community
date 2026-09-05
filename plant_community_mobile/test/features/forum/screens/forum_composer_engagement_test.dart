import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_mention_suggestions.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

Future<void> _pumpComposer(
  WidgetTester tester,
  FakeForumApi api, {
  ForumComposeArgs args = const ForumComposeArgs.reply(topicId: 10),
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
      ],
      child: MaterialApp(home: ForumComposerScreen(args: args)),
    ),
  );
  await tester.pumpAndSettle();
}

/// The suggestion strip's rows — `find.text('@alice')` alone would also
/// match the field once the mention is inserted.
Finder _suggestion(String username) => find.descendant(
  of: find.byType(ForumMentionSuggestions),
  matching: find.text('@$username'),
);

void main() {
  group('Composer quote draft (todo 341 wave 3)', () {
    testWidgets('a pre-filled quote is shown, and sent as a quote block '
        'ahead of the paragraph', (tester) async {
      final api = FakeForumApi();
      await _pumpComposer(
        tester,
        api,
        args: const ForumComposeArgs.reply(
          topicId: 10,
          quoteText: 'bob wrote:\nOriginal point',
        ),
      );

      expect(find.text('bob wrote:\nOriginal point'), findsOneWidget);
      expect(find.byTooltip('Remove quote'), findsOneWidget);
      // A quote alone is not a reply — Post stays disabled until text.
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, 'Post'))
            .onPressed,
        isNull,
      );

      await tester.enterText(find.byType(TextField), 'Agreed.');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'quote', 'value': 'bob wrote:\nOriginal point'},
        {'type': 'paragraph', 'value': 'Agreed.'},
      ]);
    });

    testWidgets('removing the quote drops the block', (tester) async {
      final api = FakeForumApi();
      await _pumpComposer(
        tester,
        api,
        args: const ForumComposeArgs.reply(
          topicId: 10,
          quoteText: 'bob wrote:\nOriginal point',
        ),
      );

      await tester.tap(find.byTooltip('Remove quote'));
      await tester.pump();
      expect(find.text('bob wrote:\nOriginal point'), findsNothing);

      await tester.enterText(find.byType(TextField), 'Agreed.');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();

      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': 'Agreed.'},
      ]);
    });

    testWidgets('the quote rides the idempotency fingerprint', (tester) async {
      final api = FakeForumApi()..failCreateReplyTimes = 1;
      await _pumpComposer(
        tester,
        api,
        args: const ForumComposeArgs.reply(topicId: 10, quoteText: 'q'),
      );
      await tester.enterText(find.byType(TextField), 'Agreed.');
      await tester.pump();

      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      // Same content retried → same key (replayed server-side).
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      expect(api.createReplyKeys.length, 2);
      expect(api.createReplyKeys[0], api.createReplyKeys[1]);
    });
  });

  group('Composer @mention autocomplete (todo 341 wave 4)', () {
    testWidgets('typing @prefix shows suggestions after the debounce; a tap '
        'inserts the plain-text mention and hides the strip', (tester) async {
      final api = FakeForumApi()
        ..mentionUsers = [
          mentionUser('alice', displayName: 'Alice L'),
          mentionUser('alan'),
          mentionUser('bob'),
        ];
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), 'Thanks @al');
      await tester.pump();
      expect(find.byType(ForumMentionSuggestions), findsOneWidget);
      expect(_suggestion('alice'), findsNothing);
      expect(api.mentionSearchCalls, isEmpty);

      await tester.pump(forumMentionDebounce);
      await tester.pump();
      expect(api.mentionSearchCalls, ['al']);
      expect(_suggestion('alice'), findsOneWidget);
      expect(find.text('Alice L'), findsOneWidget);
      expect(_suggestion('alan'), findsOneWidget);
      expect(_suggestion('bob'), findsNothing);

      await tester.tap(_suggestion('alice'));
      await tester.pump();

      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'Thanks @alice ');
      expect(field.controller!.selection.baseOffset, 'Thanks @alice '.length);
      expect(_suggestion('alice'), findsNothing);
      expect(_suggestion('alan'), findsNothing);

      // A mention is plain text in the body — the server resolves it.
      await tester.tap(find.widgetWithText(FilledButton, 'Post'));
      await tester.pumpAndSettle();
      expect(api.createReplyBodies.single, [
        {'type': 'paragraph', 'value': 'Thanks @alice '.trim()},
      ]);
    });

    testWidgets('a superseded lookup that lands late never replaces the '
        'newer suggestions', (tester) async {
      final gates = [
        Completer<List<ForumMentionUser>>(),
        Completer<List<ForumMentionUser>>(),
      ];
      final api = FakeForumApi()..mentionGates = gates;
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), '@a');
      await tester.pump(forumMentionDebounce);
      await tester.enterText(find.byType(TextField), '@al');
      await tester.pump(forumMentionDebounce);
      expect(api.mentionSearchCalls, ['a', 'al']);

      gates[1].complete([mentionUser('alice')]);
      // One pump lands the response in the provider, one rebuilds the strip.
      await tester.pump();
      await tester.pump();
      expect(_suggestion('alice'), findsOneWidget);

      gates[0].complete([mentionUser('adam'), mentionUser('alice')]);
      await tester.pump();
      await tester.pump();
      expect(_suggestion('adam'), findsNothing);
      expect(_suggestion('alice'), findsOneWidget);
    });

    testWidgets('leaving the @word clears the strip; an email is never a '
        'mention', (tester) async {
      final api = FakeForumApi()..mentionUsers = [mentionUser('alice')];
      await _pumpComposer(tester, api);

      await tester.enterText(find.byType(TextField), '@al');
      await tester.pump(forumMentionDebounce);
      await tester.pump();
      expect(_suggestion('alice'), findsOneWidget);

      await tester.enterText(find.byType(TextField), '@al done');
      await tester.pump();
      expect(_suggestion('alice'), findsNothing);

      await tester.enterText(find.byType(TextField), 'mail me@al');
      await tester.pump(forumMentionDebounce);
      await tester.pump();
      expect(api.mentionSearchCalls, ['al']);
      expect(_suggestion('alice'), findsNothing);
    });
  });
}
