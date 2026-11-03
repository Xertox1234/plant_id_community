import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_season_card.dart';

import '../../support/forum_test_support.dart';

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  Brightness brightness = Brightness.dark,
  Size size = const Size(375, 812),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.build(brightness, AppTheme.defaultDensity),
      home: MediaQuery(
        data: MediaQueryData(
          size: size,
          textScaler: TextScaler.linear(textScale),
        ),
        child: Scaffold(body: SingleChildScrollView(child: child)),
      ),
    ),
  );
}

void main() {
  group('ForumSeasonCard', () {
    testWidgets('shows the four stats and the next-badge progress', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumSeasonCard(
          stats: myStats(
            posts: 12,
            solutionsAccepted: 3,
            identificationsShared: 4,
            streakDays: 2,
            badgeProgress: 4,
            badgeTarget: 20,
          ),
        ),
      );
      expect(find.text('YOUR SEASON'), findsOneWidget);
      expect(find.text('IDs'), findsOneWidget);
      expect(find.text('Posts'), findsOneWidget);
      expect(find.text('Solutions'), findsOneWidget);
      expect(find.text('Day streak'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      expect(find.text('12'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
      expect(find.text('Botanist badge · 4 / 20 IDs'), findsOneWidget);
      final bar = tester.widget<LinearProgressIndicator>(
        find.byType(LinearProgressIndicator),
      );
      expect(bar.value, 0.2);
    });

    testWidgets('a zero state reads 0 / 20 IDs', (tester) async {
      await _pump(tester, ForumSeasonCard(stats: myStats(badgeTarget: 20)));
      expect(find.text('Botanist badge · 0 / 20 IDs'), findsOneWidget);
    });

    testWidgets('a complete badge says so, no badge track hides the row', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumSeasonCard(stats: myStats(badgeProgress: 10, badgeTarget: 10)),
      );
      expect(find.text('Botanist badge · complete'), findsOneWidget);

      await _pump(
        tester,
        ForumSeasonCard(stats: myStats(badgeName: '', badgeTarget: 0)),
      );
      expect(find.byType(LinearProgressIndicator), findsNothing);
    });

    testWidgets('earned badges render beneath; the watermark is hidden from '
        'semantics', (tester) async {
      await _pump(tester, ForumSeasonCard(stats: myStats(badges: [badge()])));
      expect(find.text('Botanist'), findsOneWidget);
      final watermark = find.ancestor(
        of: find.byIcon(LucideIcons.leaf),
        matching: find.byType(ExcludeSemantics),
      );
      expect(watermark, findsWidgets);
    });

    for (final brightness in Brightness.values) {
      for (final scale in [1.0, 2.0]) {
        testWidgets('no overflow at 320x640, ${brightness.name}, x$scale', (
          tester,
        ) async {
          await _pump(
            tester,
            ForumSeasonCard(
              stats: myStats(
                posts: 1234,
                solutionsAccepted: 56,
                identificationsShared: 7,
                streakDays: 12,
                badgeProgress: 7,
                badgeTarget: 20,
              ),
            ),
            brightness: brightness,
            size: const Size(320, 640),
            textScale: scale,
          );
          expect(tester.takeException(), isNull);
        });
      }
    }
  });
}
