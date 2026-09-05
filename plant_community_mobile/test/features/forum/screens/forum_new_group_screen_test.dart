import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/forum_errors.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_new_group_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../support/forum_test_support.dart';

/// The compose screen behind a router whose group-thread route records the
/// navigation instead of mounting the real thread.
Widget _wrap(FakeForumApi api, List<Uri> opened) {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => const ForumNewGroupScreen()),
      GoRoute(
        path: '/forum/groups/:id',
        name: 'forumGroupConversation',
        builder: (_, state) {
          opened.add(state.uri);
          return const Scaffold(body: Text('thread'));
        },
      ),
    ],
  );
  return ProviderScope(
    overrides: [
      forumApiProvider.overrideWithValue(api),
      // Signed in as `me`, so the self-username guard has something to
      // compare against.
      userProfileServiceProvider.overrideWith(
        () => FakeUserProfileService(username: 'me'),
      ),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

Finder _title() => find.widgetWithText(TextField, 'Group name');
Finder _member() => find.widgetWithText(TextField, 'Add member');
Finder _body() => find.widgetWithText(TextField, 'First message');
Finder _create() => find.widgetWithText(FilledButton, 'Create group');

bool _createEnabled(WidgetTester tester) =>
    tester.widget<FilledButton>(_create()).onPressed != null;

Future<void> _addMember(WidgetTester tester, String username) async {
  await tester.enterText(_member(), username);
  await tester.tap(find.byTooltip('Add'));
  await tester.pumpAndSettle();
}

Future<void> _fillValidForm(WidgetTester tester) async {
  await tester.enterText(_title(), 'Seed swap committee');
  await _addMember(tester, 'ada');
  await _addMember(tester, '@bob');
  await tester.enterText(_body(), 'Who has spare pots?');
  await tester.pumpAndSettle();
}

void main() {
  group('ForumNewGroupScreen (todo 350)', () {
    testWidgets('submits the exact {title, usernames, body} payload with an '
        'Idempotency-Key and replaces itself with the new thread', (
      tester,
    ) async {
      final api = FakeForumApi();
      final opened = <Uri>[];

      await tester.pumpWidget(_wrap(api, opened));
      await tester.pumpAndSettle();
      await _fillValidForm(tester);
      expect(find.text('@ada'), findsOneWidget);
      expect(find.text('@bob'), findsOneWidget);
      expect(_createEnabled(tester), isTrue);

      await tester.tap(_create());
      await tester.pumpAndSettle();

      expect(api.createGroupConversationCalls, [
        {
          'title': 'Seed swap committee',
          'usernames': ['ada', 'bob'],
          'body': 'Who has spare pots?',
        },
      ]);
      expect(api.createGroupConversationKeys.single, isNotEmpty);
      expect(opened.single.path, '/forum/groups/500');
      // Replaced, not pushed: the compose screen is gone.
      expect(find.byType(ForumNewGroupScreen), findsNothing);
    });

    testWidgets('Create is disabled until a title, 2 members and a body are '
        'present; the member field disables at 7 with the cap hint', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(FakeForumApi(), []));
      await tester.pumpAndSettle();

      expect(_createEnabled(tester), isFalse);
      await tester.enterText(_title(), 'Cuttings');
      await tester.enterText(_body(), 'hello');
      await tester.pumpAndSettle();
      expect(_createEnabled(tester), isFalse);
      await _addMember(tester, 'ada');
      expect(_createEnabled(tester), isFalse); // one is a direct DM
      expect(find.text('Add 2 to 7 members (1 added).'), findsOneWidget);
      await _addMember(tester, 'bob');
      expect(_createEnabled(tester), isTrue);

      // Duplicates and blanks are ignored.
      await _addMember(tester, 'ada');
      await _addMember(tester, '   ');
      expect(find.byType(InputChip), findsNWidgets(2));

      for (final u in ['c', 'd', 'e', 'f', 'g']) {
        await _addMember(tester, u);
      }
      expect(find.byType(InputChip), findsNWidgets(7));
      expect(tester.widget<TextField>(_member()).enabled, isFalse);
      expect(
        find.text('Groups hold up to 8 people including you.'),
        findsOneWidget,
      );
      expect(_createEnabled(tester), isTrue);

      // Removing a chip (its only Icon is the delete affordance) re-opens
      // the field.
      await tester.tap(
        find.descendant(
          of: find.widgetWithText(InputChip, '@g'),
          matching: find.byType(Icon),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(InputChip), findsNWidgets(6));
      expect(tester.widget<TextField>(_member()).enabled, isTrue);
    });

    testWidgets('typing in the member field searches usernames; tapping a '
        'suggestion adds the chip', (tester) async {
      final api = FakeForumApi()
        ..mentionUsers = [
          mentionUser('adalovelace', displayName: 'Ada Lovelace'),
          mentionUser('bob'),
        ];

      await tester.pumpWidget(_wrap(api, []));
      await tester.pumpAndSettle();

      await tester.enterText(_member(), 'ada');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      expect(api.mentionSearchCalls, ['ada']);
      expect(find.text('@adalovelace'), findsOneWidget);
      expect(find.text('Ada Lovelace'), findsOneWidget);

      await tester.tap(find.text('@adalovelace'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(InputChip, '@adalovelace'), findsOneWidget);
      expect(tester.widget<TextField>(_member()).controller?.text, isEmpty);
      // The strip clears once the pick is made.
      expect(find.text('Ada Lovelace'), findsNothing);
    });

    testWidgets('the generic 400 is shown verbatim and the form stays intact', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..failCreateGroupWith = ApiException(
          'One of the members cannot be added.',
          statusCode: 400,
        );
      final opened = <Uri>[];

      await tester.pumpWidget(_wrap(api, opened));
      await tester.pumpAndSettle();
      await _fillValidForm(tester);
      await tester.tap(_create());
      await tester.pumpAndSettle();

      expect(find.text('One of the members cannot be added.'), findsOneWidget);
      expect(opened, isEmpty);
      expect(
        tester.widget<TextField>(_title()).controller?.text,
        'Seed swap committee',
      );
      expect(find.text('@ada'), findsOneWidget);
      expect(find.text('@bob'), findsOneWidget);
      expect(
        tester.widget<TextField>(_body()).controller?.text,
        'Who has spare pots?',
      );
      expect(_createEnabled(tester), isTrue);

      // A retry of the SAME payload reuses the key; a changed one rotates.
      api.failCreateGroupWith = null;
      await tester.tap(_create());
      await tester.pumpAndSettle();
      expect(api.createGroupConversationKeys.length, 2);
      expect(
        api.createGroupConversationKeys[0],
        api.createGroupConversationKeys[1],
      );
      expect(opened.single.path, '/forum/groups/500');
    });

    testWidgets('a 429 shows the shared rate-limit copy', (tester) async {
      final api = FakeForumApi()
        ..failCreateGroupWith = ApiException(
          'Request was throttled.',
          statusCode: 429,
        );

      await tester.pumpWidget(_wrap(api, []));
      await tester.pumpAndSettle();
      await _fillValidForm(tester);
      await tester.tap(_create());
      await tester.pumpAndSettle();

      expect(find.text(forumRateLimitedMessage), findsOneWidget);
      expect(find.text('Request was throttled.'), findsNothing);
    });

    testWidgets('a second tap while the create is in flight is a no-op', (
      tester,
    ) async {
      final gate = Completer<ForumConversation>();
      final api = FakeForumApi()..createGroupGate = gate;
      final opened = <Uri>[];

      await tester.pumpWidget(_wrap(api, opened));
      await tester.pumpAndSettle();
      await _fillValidForm(tester);

      await tester.tap(_create());
      await tester.pump();
      expect(_createEnabled(tester), isFalse);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.tap(_create(), warnIfMissed: false);
      await tester.pump();
      expect(api.createGroupConversationCalls.length, 1);

      gate.complete(groupConversation(id: 77, title: 'Seed swap committee'));
      await tester.pumpAndSettle();
      expect(opened.single.path, '/forum/groups/77');
    });

    testWidgets('adding yourself says so instead of doing nothing', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(FakeForumApi(), []));
      await tester.pumpAndSettle();

      await _addMember(tester, '@me');

      expect(find.text("That's you."), findsOneWidget);
      // No chip — the text is only still in the field, uncleared on purpose.
      expect(find.widgetWithText(InputChip, '@me'), findsNothing);
      // The next keystroke clears the notice.
      await tester.enterText(_member(), 'ada');
      await tester.pumpAndSettle();
      expect(find.text("That's you."), findsNothing);
      await tester.tap(find.byTooltip('Add'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(InputChip, '@ada'), findsOneWidget);
    });

    testWidgets('adding the same member twice says so instead of doing '
        'nothing', (tester) async {
      await tester.pumpWidget(_wrap(FakeForumApi(), []));
      await tester.pumpAndSettle();

      await _addMember(tester, 'ada');
      expect(find.widgetWithText(InputChip, '@ada'), findsOneWidget);

      await _addMember(tester, '@ada');

      expect(find.text('Already added.'), findsOneWidget);
      // Still exactly one chip, not a silent no-op the user can't explain.
      expect(find.widgetWithText(InputChip, '@ada'), findsOneWidget);
    });

    testWidgets('the title field caps at 80 characters', (tester) async {
      await tester.pumpWidget(_wrap(FakeForumApi(), []));
      await tester.pumpAndSettle();

      expect(
        tester.widget<TextField>(_title()).maxLength,
        forumGroupTitleMaxChars,
      );
      expect(forumGroupTitleMaxChars, 80);
    });
  });
}
