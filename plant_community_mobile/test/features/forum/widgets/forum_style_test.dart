import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_typography.dart';
import 'package:plant_community_mobile/features/forum/forum_format.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_style.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_accents.dart';

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  Size size = const Size(375, 812),
  double textScale = 1.0,
  Brightness brightness = Brightness.dark,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.build(brightness, AppTheme.defaultDensity),
      home: MediaQuery.withClampedTextScaling(
        minScaleFactor: textScale,
        maxScaleFactor: textScale,
        child: Scaffold(body: SingleChildScrollView(child: child)),
      ),
    ),
  );
}

void main() {
  group('forumRelativeTime', () {
    final now = DateTime(2026, 11, 18, 12);

    test('past a week it is a short date, never the ISO form', () {
      expect(forumRelativeTime(DateTime(2026, 8, 16), now: now), 'Aug 16');
      expect(
        forumRelativeTime(DateTime(2025, 8, 16), now: now),
        'Aug 16, 2025',
      );
    });

    test('within a week it stays relative', () {
      expect(forumRelativeTime(DateTime(2026, 11, 16, 12), now: now), '2d');
    });

    test('forumListTime is the same label', () {
      final dt = DateTime(2026, 9, 26);
      expect(forumListTime(dt, now: now), forumRelativeTime(dt, now: now));
    });
  });

  group('forumMeta', () {
    testWidgets('is Geist on ink2, not the mono label face', (tester) async {
      late TextStyle meta;
      await _pump(
        tester,
        Builder(
          builder: (context) {
            meta = forumMeta(context);
            return const SizedBox.shrink();
          },
        ),
      );
      expect(meta.fontFamily, AppTypography.meta.fontFamily);
      expect(meta.fontFamily, isNot(AppTypography.label.fontFamily));
      expect(meta.fontSize, AppTypography.meta.fontSize);
    });
  });

  group('ForumListRow', () {
    for (final size in const [Size(320, 640), Size(375, 812)]) {
      for (final scale in const [1.0, 2.0]) {
        testWidgets('title, excerpt, detail and chevron fit at '
            '${size.width.toInt()}pt x$scale', (tester) async {
          var taps = 0;
          await _pump(
            tester,
            CanopyGroupedCard(
              rows: [
                ForumListRow(
                  title:
                      'Brown spots with yellow rings spreading across my '
                      'monstera and three other plants on the same shelf',
                  body: 'It started on the oldest leaf and moved outward.',
                  meta: '5 replies · Aug 16',
                  icon: LucideIcons.messagesSquare,
                  onTap: () => taps++,
                ),
              ],
            ),
            size: size,
            textScale: scale,
          );
          expect(tester.takeException(), isNull);
          expect(find.text('5 replies · Aug 16'), findsOneWidget);
          expect(find.byIcon(LucideIcons.chevronRight), findsOneWidget);
          // The title is capped at two lines, not one.
          final title = tester.widget<Text>(find.textContaining('Brown spots'));
          expect(title.maxLines, 2);
          await tester.tap(find.byType(ForumListRow));
          expect(taps, 1);
        });
      }
    }

    testWidgets('a row with a title only is still a 48pt target', (
      tester,
    ) async {
      await _pump(tester, ForumListRow(title: 'Link Test', onTap: () {}));
      expect(
        tester.getSize(find.byType(ForumListRow)).height,
        greaterThanOrEqualTo(kMinInteractiveDimension),
      );
    });
  });

  group('ForumEmptyState', () {
    testWidgets('shows the tile, the title and the line under it', (
      tester,
    ) async {
      await _pump(
        tester,
        const ForumEmptyState(
          icon: LucideIcons.bookmark,
          title: 'No bookmarks yet.',
          body: 'Tap the bookmark icon on a topic to save it here.',
        ),
        size: const Size(320, 640),
        textScale: 2.0,
      );
      expect(tester.takeException(), isNull);
      expect(find.byType(CanopyAccentTile), findsOneWidget);
      expect(find.text('No bookmarks yet.'), findsOneWidget);
      expect(
        find.text('Tap the bookmark icon on a topic to save it here.'),
        findsOneWidget,
      );
    });

    testWidgets('with no body it draws the title alone', (tester) async {
      await _pump(
        tester,
        const ForumEmptyState(
          icon: LucideIcons.mail,
          title: 'No messages yet.',
        ),
      );
      expect(find.byType(Text), findsOneWidget);
    });
  });

  group('ForumSectionHeader', () {
    testWidgets('is a 48pt row announced as a header', (tester) async {
      final handle = tester.ensureSemantics();
      await _pump(tester, const ForumSectionHeader('Recent activity'));
      expect(
        tester.getSize(find.byType(ForumSectionHeader)).height,
        greaterThanOrEqualTo(forumHeaderHeight),
      );
      expect(
        tester.getSemantics(find.text('Recent activity')),
        matchesSemantics(label: 'Recent activity', isHeader: true),
      );
      handle.dispose();
    });
  });
}
