import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_conversation_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../support/forum_test_support.dart';

/// The group thread pushed over a stub inbox, signed in as [me] — so
/// "Leave group" has somewhere to pop to and a SnackBar host underneath.
Future<void> _open(
  WidgetTester tester,
  FakeForumApi api, {
  String me = 'me',
  int conversationId = 12,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        userProfileServiceProvider.overrideWith(
          () => FakeUserProfileService(username: me),
        ),
      ],
      child: MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        ForumConversationScreen(conversationId: conversationId),
                  ),
                ),
                child: const Text('inbox'),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('inbox'));
  await tester.pumpAndSettle();
}

Finder _sendButton() => find.widgetWithIcon(IconButton, Icons.send);

Finder _removeIn(String member) => find.descendant(
  of: find.widgetWithText(ListTile, member),
  matching: find.widgetWithText(TextButton, 'Remove'),
);

void main() {
  group('ForumConversationScreen — group mode (todo 350)', () {
    testWidgets(
      'shows the group title, attributes other members\' messages with '
      'name + avatar, and keeps own messages un-attributed on the right',
      (tester) async {
        final api = FakeForumApi()
          ..conversations = [
            groupConversation(
              id: 12,
              title: 'Seed swap committee',
              memberUsernames: const ['ada', 'bob'],
              canManage: true,
            ),
          ]
          ..messages = [
            directMessage(
              id: 3,
              conversationId: 12,
              senderUsername: 'ada',
              body: 'Bring pots',
            ),
            directMessage(
              id: 2,
              conversationId: 12,
              senderUsername: 'me',
              body: 'Sure thing',
            ),
            directMessage(
              id: 1,
              conversationId: 12,
              senderUsername: 'bob',
              body: 'Hi all',
            ),
          ];

        await _open(tester, api);

        expect(
          find.descendant(
            of: find.byType(AppBar),
            matching: find.text('Seed swap committee'),
          ),
          findsOneWidget,
        );
        // Sender labels for the two other members, none for me.
        expect(find.text('ada'), findsOneWidget);
        expect(find.text('bob'), findsOneWidget);
        expect(find.text('me'), findsNothing);
        expect(find.byType(AuthorAvatar), findsNWidgets(2));
        // Visual order oldest → newest, own message to the right.
        final hiY = tester.getTopLeft(find.text('Hi all')).dy;
        final sureY = tester.getTopLeft(find.text('Sure thing')).dy;
        final potsY = tester.getTopLeft(find.text('Bring pots')).dy;
        expect(hiY, lessThan(sureY));
        expect(sureY, lessThan(potsY));
        expect(
          tester.getCenter(find.text('Sure thing')).dx,
          greaterThan(tester.getCenter(find.text('Hi all')).dx),
        );
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('send goes through the by-id endpoint — the exact call — and '
        'never the username route', (tester) async {
      final api = FakeForumApi()
        ..conversations = [groupConversation(id: 12)]
        ..messages = [directMessage(id: 1, conversationId: 12, body: 'hi')];

      await _open(tester, api);

      await tester.enterText(find.byType(TextField), 'On my way');
      await tester.pump();
      await tester.tap(_sendButton());
      await tester.pumpAndSettle();

      expect(api.sendConversationMessageCalls, [
        {'conversationId': 12, 'body': 'On my way'},
      ]);
      expect(api.sendConversationMessageKeys.single, isNotEmpty);
      expect(api.sendMessageCalls, isEmpty);
      expect(find.text('On my way'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller?.text,
        isEmpty,
      );
    });

    testWidgets('a 403 on send shows the group notice and keeps the draft', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversations = [groupConversation(id: 12)]
        ..failSendConversationMessageWith = ApiException(
          'You cannot message this group.',
          statusCode: 403,
        );

      await _open(tester, api);
      await tester.enterText(find.byType(TextField), 'hello?');
      await tester.pump();
      await tester.tap(_sendButton());
      await tester.pumpAndSettle();

      expect(find.text("You can't message this group."), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller?.text,
        'hello?',
      );
    });

    testWidgets(
      'members sheet as the creator: Remove on every other member, never on '
      'yourself; Add member enabled below the cap; no Leave group',
      (tester) async {
        final api = FakeForumApi()
          ..conversations = [
            groupConversation(
              id: 12,
              creatorUsername: 'me',
              memberUsernames: const ['ada', 'bob'],
              canManage: true,
            ),
          ];

        await _open(tester, api);
        await tester.tap(find.byTooltip('Members'));
        await tester.pumpAndSettle();

        expect(find.text('Members'), findsOneWidget);
        expect(find.text('3 of 8'), findsOneWidget);
        expect(find.text('me (you)'), findsOneWidget);
        expect(find.text('Creator'), findsOneWidget);
        expect(find.widgetWithText(TextButton, 'Remove'), findsNWidgets(2));
        expect(_removeIn('me (you)'), findsNothing);
        expect(_removeIn('ada'), findsOneWidget);
        expect(_removeIn('bob'), findsOneWidget);
        final add = find.widgetWithText(FilledButton, 'Add member');
        expect(add, findsOneWidget);
        expect(tester.widget<FilledButton>(add).onPressed, isNotNull);
        expect(find.text('Leave group'), findsNothing);

        await tester.tap(_removeIn('bob'));
        await tester.pumpAndSettle();

        expect(api.removeParticipantCalls, [
          {'conversationId': 12, 'username': 'bob'},
        ]);
        expect(find.widgetWithText(ListTile, 'bob'), findsNothing);
        expect(find.text('2 of 8'), findsOneWidget);
      },
    );

    testWidgets(
      'members sheet as a non-creator: no Remove, no Add member, Leave group',
      (tester) async {
        final api = FakeForumApi()
          ..conversations = [
            groupConversation(
              id: 12,
              creatorUsername: 'ada',
              memberUsernames: const ['me', 'bob'],
              canManage: false,
            ),
          ];

        await _open(tester, api);
        await tester.tap(find.byTooltip('Members'));
        await tester.pumpAndSettle();

        expect(find.widgetWithText(ListTile, 'ada'), findsOneWidget);
        expect(find.text('Creator'), findsOneWidget);
        expect(find.text('me (you)'), findsOneWidget);
        expect(find.widgetWithText(TextButton, 'Remove'), findsNothing);
        expect(find.text('Add member'), findsNothing);
        expect(find.widgetWithText(TextButton, 'Leave group'), findsOneWidget);
      },
    );

    testWidgets('Add member is disabled at the 8-member cap', (tester) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            creatorUsername: 'me',
            memberUsernames: const ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
            canManage: true,
          ),
        ];

      await _open(tester, api);
      await tester.tap(find.byTooltip('Members'));
      await tester.pumpAndSettle();

      expect(find.text('8 of 8'), findsOneWidget);
      final add = find.widgetWithText(FilledButton, 'Add member');
      expect(tester.widget<FilledButton>(add).onPressed, isNull);
      expect(find.text('This group is full.'), findsOneWidget);
    });

    testWidgets('Add member posts the username and shows the returned roster', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            creatorUsername: 'me',
            memberUsernames: const ['ada'],
            canManage: true,
          ),
        ];

      await _open(tester, api);
      await tester.tap(find.byTooltip('Members'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add member'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextField, 'Username'),
        '@carol',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Add'));
      await tester.pumpAndSettle();

      expect(api.addParticipantCalls, [
        {'conversationId': 12, 'username': 'carol'},
      ]);
      expect(find.widgetWithText(ListTile, 'carol'), findsOneWidget);
      expect(find.text('3 of 8'), findsOneWidget);
    });

    testWidgets('a refused Add member shows the server\'s 400 sentence', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(id: 12, creatorUsername: 'me', canManage: true),
        ]
        ..failAddParticipantWith = ApiException(
          'One of the members cannot be added.',
          statusCode: 400,
        );

      await _open(tester, api);
      await tester.tap(find.byTooltip('Members'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add member'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, 'Username'), 'x');
      await tester.tap(find.widgetWithText(FilledButton, 'Add'));
      await tester.pumpAndSettle();

      expect(find.text('One of the members cannot be added.'), findsOneWidget);
      expect(find.text('3 of 8'), findsOneWidget);
    });

    testWidgets('Leave group removes me, pops to the inbox and says so', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            title: 'Seed swap committee',
            creatorUsername: 'ada',
            memberUsernames: const ['me', 'bob'],
            canManage: false,
          ),
        ];

      await _open(tester, api);
      expect(find.text('Seed swap committee'), findsOneWidget);
      await tester.tap(find.byTooltip('Members'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Leave group'));
      await tester.pumpAndSettle();
      expect(find.text('Leave this group?'), findsOneWidget);
      await tester.tap(find.widgetWithText(TextButton, 'Leave'));
      await tester.pumpAndSettle();

      expect(api.removeParticipantCalls, [
        {'conversationId': 12, 'username': 'me'},
      ]);
      // Back on the stub inbox with the notice.
      expect(find.text('Seed swap committee'), findsNothing);
      expect(find.text('inbox'), findsOneWidget);
      expect(find.text('You left the group.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('a refused Leave keeps you in the thread', (tester) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            title: 'Seed swap committee',
            creatorUsername: 'ada',
            memberUsernames: const ['me'],
          ),
        ]
        ..failRemoveParticipantWith = ApiException(
          'Transfer or close the group first.',
          statusCode: 400,
        );

      await _open(tester, api);
      await tester.tap(find.byTooltip('Members'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Leave group'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Leave'));
      await tester.pumpAndSettle();

      expect(find.text('Transfer or close the group first.'), findsOneWidget);
      expect(find.text('Seed swap committee'), findsOneWidget);
      expect(find.text('You left the group.'), findsNothing);
    });

    testWidgets('cancelling the Leave confirmation leaves the group alone', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..conversations = [
          groupConversation(
            id: 12,
            title: 'Seed swap committee',
            creatorUsername: 'ada',
            memberUsernames: const ['me', 'bob'],
            canManage: false,
          ),
        ];

      await _open(tester, api);
      await tester.tap(find.byTooltip('Members'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Leave group'));
      await tester.pumpAndSettle();
      expect(find.text('Leave this group?'), findsOneWidget);

      await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
      await tester.pumpAndSettle();

      // Nothing happened: no call, still in the thread, still a member.
      expect(api.removeParticipantCalls, isEmpty);
      expect(find.text('Leave this group?'), findsNothing);
      expect(find.widgetWithText(TextButton, 'Leave group'), findsOneWidget);
      expect(find.text('You left the group.'), findsNothing);
    });

    testWidgets(
      'a deep link with no inbox mounted resolves the header and the Members '
      'action through the by-id GET',
      (tester) async {
        // No `conversations` fixture at all — the inbox is not mounted, so
        // only the detail GET can supply the title and roster.
        final api = FakeForumApi()
          ..conversationDetail = groupConversation(
            id: 12,
            title: 'Seed swap committee',
            memberUsernames: const ['ada', 'bob'],
          )
          ..messages = [directMessage(id: 1, conversationId: 12, body: 'Hi')];

        await _open(tester, api);

        expect(api.fetchConversationCalls, [12]);
        expect(api.fetchConversationsCalls, isEmpty);
        expect(
          find.descendant(
            of: find.byType(AppBar),
            matching: find.text('Seed swap committee'),
          ),
          findsOneWidget,
        );
        final members = find.widgetWithIcon(IconButton, Icons.group_outlined);
        expect(tester.widget<IconButton>(members).onPressed, isNotNull);

        await tester.tap(members);
        await tester.pumpAndSettle();
        expect(find.widgetWithText(ListTile, 'ada'), findsOneWidget);
      },
    );

    testWidgets('a 404 on the by-id GET shows the unavailable copy, and '
        'Retry re-fetches', (tester) async {
      // Nothing resolves id 12 — the fake returns null, the client's 404.
      final api = FakeForumApi();

      await _open(tester, api);

      expect(find.text('This group could not be found.'), findsOneWidget);
      expect(api.fetchMessagesCalls, isEmpty);
      // No composer, no members sheet from a group I cannot read.
      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNull);
      expect(
        tester
            .widget<IconButton>(
              find.widgetWithIcon(IconButton, Icons.group_outlined),
            )
            .onPressed,
        isNull,
      );

      api.conversationDetail = groupConversation(id: 12, title: 'Cuttings');
      api.messages = [directMessage(id: 1, conversationId: 12, body: 'back')];
      await tester.tap(find.widgetWithText(OutlinedButton, 'Retry'));
      await tester.pumpAndSettle();

      expect(api.fetchConversationCalls, [12, 12]);
      expect(find.text('This group could not be found.'), findsNothing);
      expect(find.text('back'), findsOneWidget);
    });

    testWidgets(
      'own messages never render on the wrong side while the account profile '
      'is still loading',
      (tester) async {
        final api = FakeForumApi()
          ..conversationDetail = groupConversation(
            id: 12,
            memberUsernames: const ['ada'],
          )
          ..messages = [
            directMessage(
              id: 2,
              conversationId: 12,
              senderUsername: 'me',
              body: 'Mine',
            ),
            directMessage(
              id: 1,
              conversationId: 12,
              senderUsername: 'ada',
              body: 'Theirs',
            ),
          ];
        // One gate per profile build: the first mount, then the re-fetch
        // below. Both start pending, so each loading window is observable.
        final gates = [Completer<void>(), Completer<void>()];
        var builds = 0;

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              forumApiProvider.overrideWithValue(api),
              userProfileServiceProvider.overrideWith(
                () => FakeUserProfileService(
                  username: 'me',
                  gate: gates[builds++].future,
                ),
              ),
            ],
            child: const MaterialApp(
              home: ForumConversationScreen(conversationId: 12),
            ),
          ),
        );
        // The thread itself resolves here; the profile does NOT (the gate is
        // still open). `pumpAndSettle` would spin on the progress indicator.
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // Nothing is attributed yet — rendering now would put "Mine" on the
        // left and snap it right a frame later.
        expect(find.text('Mine'), findsNothing);
        expect(find.text('Theirs'), findsNothing);

        gates[0].complete();
        await tester.pumpAndSettle();

        expect(
          tester.getCenter(find.text('Mine')).dx,
          greaterThan(tester.getCenter(find.text('Theirs')).dx),
        );

        // A LATER re-fetch must not blank the thread or flip the sides:
        // `asData` keeps the previously resolved username while the profile
        // reloads, so only the FIRST resolve is ever held.
        ProviderScope.containerOf(
          tester.element(find.byType(ForumConversationScreen)),
          listen: false,
        ).invalidate(userProfileServiceProvider);
        await tester.pump();

        expect(find.text('Mine'), findsOneWidget);
        expect(
          tester.getCenter(find.text('Mine')).dx,
          greaterThan(tester.getCenter(find.text('Theirs')).dx),
        );

        gates[1].complete();
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('an empty group thread shows the group placeholder', (
      tester,
    ) async {
      final api = FakeForumApi()..conversations = [groupConversation(id: 12)];

      await _open(tester, api);

      expect(
        find.text('No messages yet. Say hello to the group.'),
        findsOneWidget,
      );
      expect(tester.widget<IconButton>(_sendButton()).onPressed, isNull);
    });
  });
}
