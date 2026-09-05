import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_stats_grid.dart';

import '../support/forum_test_support.dart';

Future<void> _pump(WidgetTester tester, Widget child) {
  return tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

void main() {
  group('ForumStatsGrid (todo 341 wave 4)', () {
    testWidgets('renders the four all-time tiles with the badge track', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumStatsGrid(
          stats: myStats(
            posts: 12,
            solutionsAccepted: 3,
            identificationsShared: 4,
            streakDays: 2,
            badgeProgress: 4,
            badgeTarget: 10,
          ),
        ),
      );

      expect(find.text('Identifications'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      expect(find.text('6 to Botanist badge'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(
        tester
            .widget<LinearProgressIndicator>(
              find.byType(LinearProgressIndicator),
            )
            .value,
        0.4,
      );
      expect(find.text('Posts'), findsOneWidget);
      expect(find.text('12'), findsOneWidget);
      expect(find.text('all time'), findsOneWidget);
      expect(find.text('Solutions'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('accepted answers'), findsOneWidget);
      expect(find.text('Day streak'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
      expect(find.text('days in a row'), findsOneWidget);
      // Never a season claim — the stats are all-time by design.
      expect(find.textContaining('this season'), findsNothing);
    });

    testWidgets('sublabels for a complete badge and an empty streak', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumStatsGrid(
          stats: myStats(
            identificationsShared: 12,
            badgeProgress: 10,
            badgeTarget: 10,
            streakDays: 0,
          ),
        ),
      );

      expect(find.text('Botanist badge complete'), findsOneWidget);
      expect(find.text('Post to start a streak'), findsOneWidget);
    });

    testWidgets('one-day streak and a host with no badge track', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumStatsGrid(
          stats: myStats(streakDays: 1, badgeTarget: 0, badgeName: ''),
        ),
      );

      expect(find.text('day in a row'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.text('all time'), findsNWidgets(2));
    });
  });

  group('ForumBadgeChips', () {
    testWidgets('one chip per badge with the description as tooltip', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumBadgeChips(
          badges: [
            badge(name: 'Botanist', description: 'Shared 10 identifications'),
            badge(slug: 'helper', name: 'Helper', description: ''),
          ],
        ),
      );

      expect(find.byType(Chip), findsNWidgets(2));
      expect(find.text('Botanist'), findsOneWidget);
      expect(find.text('Helper'), findsOneWidget);
      expect(find.byTooltip('Shared 10 identifications'), findsOneWidget);
      // No description → the name is the tooltip, never an empty bubble.
      expect(find.byTooltip('Helper'), findsOneWidget);
    });

    testWidgets('renders nothing for no badges', (tester) async {
      await _pump(tester, const ForumBadgeChips(badges: []));
      expect(find.byType(Chip), findsNothing);
    });
  });
}
