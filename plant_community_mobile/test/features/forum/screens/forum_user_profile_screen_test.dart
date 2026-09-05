import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_user_profile_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../support/forum_test_support.dart';

/// [me] is the signed-in account's username; `null` renders the screen for
/// an anonymous viewer (no account profile is fetched in that case).
Widget _wrap(FakeForumApi api, {String username = 'alice', String? me}) =>
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: me != null),
        ),
        if (me != null)
          userProfileServiceProvider.overrideWith(
            () => FakeUserProfileService(username: me),
          ),
      ],
      child: MaterialApp(home: ForumUserProfileScreen(username: username)),
    );

Finder _messageButton() => find.widgetWithIcon(IconButton, Icons.mail_outline);

void main() {
  group('ForumUserProfileScreen (todo 317)', () {
    testWidgets('renders header identity, title, bio, and post count', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..profile = profile(
          username: 'alice',
          trustLevel: 3,
          title: 'Plant Whisperer',
          bio: 'I grow monsteras.',
          postCount: 42,
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('alice'), findsOneWidget);
      expect(find.text('Plant Whisperer'), findsOneWidget);
      expect(find.text('I grow monsteras.'), findsOneWidget);
      expect(find.textContaining('42'), findsOneWidget);
    });

    testWidgets('renders recent topics and recent posts from the fixture', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..profile = profile(
          username: 'alice',
          recentTopics: [
            profileTopicRefJson(id: 1, title: 'Monstera care', replyCount: 5),
          ],
          recentPosts: [
            profilePostRefJson(id: 9, topicTitle: 'Fiddle leaf fig'),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Recent topics'), findsOneWidget);
      expect(find.text('Monstera care'), findsOneWidget);
      expect(find.text('Recent posts'), findsOneWidget);
      expect(find.text('Fiddle leaf fig'), findsOneWidget);
    });

    testWidgets('shows empty-state lines when there is no recent activity', (
      tester,
    ) async {
      final api = FakeForumApi()..profile = profile(username: 'alice');

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Recent topics'), findsOneWidget);
      expect(find.text('Recent posts'), findsOneWidget);
      // Two distinct empty-state lines (one per section).
      expect(find.textContaining('No '), findsNWidgets(2));
    });

    testWidgets('a load failure surfaces a retry, not a crash', (tester) async {
      final api = FakeForumApi(); // no profile fixture set -> 404

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.widgetWithText(OutlinedButton, 'Retry'), findsOneWidget);

      api.profile = profile(username: 'alice');
      await tester.tap(find.widgetWithText(OutlinedButton, 'Retry'));
      await tester.pumpAndSettle();

      expect(find.text('alice'), findsOneWidget);
    });
  });

  group('ForumUserProfileScreen "Message" action (todo 339)', () {
    testWidgets('shows for a signed-in viewer on someone else\'s profile', (
      tester,
    ) async {
      final api = FakeForumApi()..profile = profile(username: 'alice');

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();

      expect(_messageButton(), findsOneWidget);
      expect(find.byTooltip('Message'), findsOneWidget);
    });

    testWidgets('is hidden on your own profile', (tester) async {
      final api = FakeForumApi()..profile = profile(username: 'alice');

      await tester.pumpWidget(_wrap(api, me: 'alice'));
      await tester.pumpAndSettle();

      expect(_messageButton(), findsNothing);
    });

    testWidgets('is hidden for an anonymous viewer', (tester) async {
      final api = FakeForumApi()..profile = profile(username: 'alice');

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(_messageButton(), findsNothing);
    });

    testWidgets('is hidden while the profile is still loading or failed', (
      tester,
    ) async {
      final api = FakeForumApi(); // 404 → error state

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();

      expect(_messageButton(), findsNothing);
    });
  });

  group('ForumUserProfileScreen Block / Unblock (todo 341)', () {
    Finder menu() => find.byTooltip('Profile options');

    testWidgets('the menu is hidden when the server says can_block is false '
        '(anonymous viewer, own profile)', (tester) async {
      final api = FakeForumApi()..profile = profile(username: 'alice');

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();

      expect(menu(), findsNothing);
    });

    testWidgets('the menu is hidden for an anonymous viewer even if the '
        'payload claims can_block', (tester) async {
      final api = FakeForumApi()
        ..profile = profile(username: 'alice', canBlock: true);

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(menu(), findsNothing);
    });

    testWidgets('Block asks for confirmation, then calls the API and shows the '
        'blocked notice, hides Message, and offers Unblock', (tester) async {
      final api = FakeForumApi()
        ..profile = profile(
          username: 'alice',
          canBlock: true,
          recentTopics: [profileTopicRefJson(id: 1, title: 'Monstera care')],
        );

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();
      expect(_messageButton(), findsOneWidget);
      expect(find.text('Monstera care'), findsOneWidget);

      await tester.tap(menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Block'));
      await tester.pumpAndSettle();

      expect(find.text('Block alice?'), findsOneWidget);
      expect(api.blockCalls, isEmpty); // nothing sent before confirming
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Block'),
        ),
      );
      await tester.pumpAndSettle();

      expect(api.blockCalls, ['alice']);
      expect(find.textContaining("You've blocked alice"), findsOneWidget);
      expect(_messageButton(), findsNothing);
      // The activity lists collapse like the server's own blocked response.
      expect(find.text('Monstera care'), findsNothing);

      await tester.tap(menu());
      await tester.pumpAndSettle();
      expect(find.text('Unblock'), findsOneWidget);
    });

    testWidgets('cancelling the confirmation sends nothing', (tester) async {
      final api = FakeForumApi()
        ..profile = profile(username: 'alice', canBlock: true);

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();

      await tester.tap(menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Block'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(api.blockCalls, isEmpty);
      expect(find.textContaining("You've blocked"), findsNothing);
      expect(_messageButton(), findsOneWidget);
    });

    testWidgets('Unblock needs no confirmation and clears the notice', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..profile = profile(username: 'alice', canBlock: true, isBlocked: true);

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();
      expect(find.textContaining("You've blocked alice"), findsOneWidget);
      expect(_messageButton(), findsNothing);

      await tester.tap(menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Unblock'));
      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
      expect(api.unblockCalls, ['alice']);
      expect(find.textContaining("You've blocked"), findsNothing);
      expect(_messageButton(), findsOneWidget);
    });

    testWidgets('a rate-limited block reverts and reads as "too fast", never '
        'a raw exception', (tester) async {
      final api = FakeForumApi()
        ..profile = profile(username: 'alice', canBlock: true)
        ..failBlockWith = ApiException(
          'Too many requests. Please wait a moment and try again.',
          statusCode: 429,
        );

      await tester.pumpWidget(_wrap(api, me: 'me'));
      await tester.pumpAndSettle();

      await tester.tap(menu());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Block'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Block'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Too fast — try again in a minute'), findsOneWidget);
      expect(find.textContaining('ApiException'), findsNothing);
      expect(find.textContaining("You've blocked"), findsNothing);
      expect(_messageButton(), findsOneWidget);
    });
  });
}
