import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_experts_strip.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_stats_grid.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import 'support/forum_test_support.dart';

Widget _wrap(FakeForumApi api, {required bool loggedIn}) => ProviderScope(
  overrides: [
    forumApiProvider.overrideWithValue(api),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: loggedIn)),
  ],
  child: const MaterialApp(home: ForumScreen()),
);

void main() {
  group('Forum home "Your season" (todo 341 wave 4)', () {
    testWidgets('a signed-in member sees the stats grid and badge chips', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..stats = myStats(
          posts: 12,
          solutionsAccepted: 3,
          identificationsShared: 4,
          streakDays: 2,
          badgeProgress: 4,
          badgeTarget: 10,
          badges: [
            badge(name: 'Botanist'),
            badge(slug: 'h', name: 'Helper'),
          ],
        );

      await tester.pumpWidget(_wrap(api, loggedIn: true));
      await tester.pumpAndSettle();

      expect(find.text('Your season'), findsOneWidget);
      expect(find.byType(ForumStatsGrid), findsOneWidget);
      expect(find.text('12'), findsOneWidget);
      expect(find.text('6 to Botanist badge'), findsOneWidget);
      expect(find.text('days in a row'), findsOneWidget);
      expect(find.byType(ForumBadgeChips), findsOneWidget);
      expect(find.widgetWithText(Chip, 'Botanist'), findsOneWidget);
      expect(find.widgetWithText(Chip, 'Helper'), findsOneWidget);
      expect(api.fetchMyStatsCalls, 1);
    });

    testWidgets('a signed-out viewer never sees (or fetches) it', (
      tester,
    ) async {
      final api = FakeForumApi();
      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.text('Your season'), findsNothing);
      expect(api.fetchMyStatsCalls, 0);
    });
  });

  group('Forum home experts strip', () {
    testWidgets('lists the experts with an online dot and a count', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..experts = [
          expert(username: 'sage', online: true),
          expert(username: 'fern', online: false),
        ];

      await tester.pumpWidget(_wrap(api, loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.text('Experts · 1 online'), findsOneWidget);
      expect(find.byType(ForumExpertsStrip), findsOneWidget);
      expect(find.text('sage'), findsOneWidget);
      expect(find.text('fern'), findsOneWidget);
      expect(find.byKey(const Key('forum-online-dot')), findsOneWidget);
    });

    testWidgets('is absent when nobody qualifies yet', (tester) async {
      await tester.pumpWidget(_wrap(FakeForumApi(), loggedIn: false));
      await tester.pumpAndSettle();

      expect(find.textContaining('Experts'), findsNothing);
      expect(find.byType(ForumExpertsStrip), findsNothing);
    });
  });
}
