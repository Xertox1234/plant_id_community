import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_user_profile_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api, {String username = 'alice'}) => ProviderScope(
  overrides: [forumApiProvider.overrideWithValue(api)],
  child: MaterialApp(home: ForumUserProfileScreen(username: username)),
);

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

    testWidgets('a load failure surfaces a retry, not a crash', (
      tester,
    ) async {
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
}
