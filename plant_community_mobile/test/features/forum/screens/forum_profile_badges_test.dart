import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_user_profile_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_stats_grid.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

Widget _wrap(FakeForumApi api) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: false)),
  ],
  child: const MaterialApp(home: ForumUserProfileScreen(username: 'alice')),
);

void main() {
  group('Profile badges (todo 341 wave 4)', () {
    testWidgets('earned badges render as chips under the identity', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..profile = profile(
          username: 'alice',
          badges: [
            badgeJson(name: 'Botanist', description: 'Shared 10 IDs'),
            badgeJson(slug: 'helper', name: 'Helper'),
          ],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Badges'), findsOneWidget);
      expect(find.byType(ForumBadgeChips), findsOneWidget);
      expect(find.widgetWithText(Chip, 'Botanist'), findsOneWidget);
      expect(find.widgetWithText(Chip, 'Helper'), findsOneWidget);
      expect(find.byTooltip('Shared 10 IDs'), findsOneWidget);
    });

    testWidgets('no section at all for a member with no badges', (
      tester,
    ) async {
      final api = FakeForumApi()..profile = profile(username: 'alice');

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.text('Badges'), findsNothing);
      expect(find.byType(ForumBadgeChips), findsNothing);
    });

    testWidgets('badges survive a block — they are identity, not content', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..profile = profile(
          username: 'alice',
          isBlocked: true,
          badges: [badgeJson(name: 'Botanist')],
        );

      await tester.pumpWidget(_wrap(api));
      await tester.pumpAndSettle();

      expect(find.textContaining("You've blocked"), findsOneWidget);
      expect(find.widgetWithText(Chip, 'Botanist'), findsOneWidget);
    });
  });
}
