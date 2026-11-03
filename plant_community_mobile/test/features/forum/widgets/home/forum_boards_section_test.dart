import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_typography.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_boards_section.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_accents.dart';

const _care = ForumBoard(
  id: 1,
  title: 'Care Problems',
  slug: 'care-problems',
  description: 'Yellow leaves, drooping, watering questions',
  topicCount: 1,
  postCount: 1,
);
const _ident = ForumBoard(
  id: 2,
  title: 'Plant Identification',
  slug: 'plant-identification',
  description:
      'What is this plant? A very long description that must stay on one '
      'line no matter how long the editor made it, truncated with an ellipsis',
  topicCount: 12,
  postCount: 340,
);

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
  group('ForumBoardsSection', () {
    testWidgets('one accent tile per board with identity icon and singulars', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumBoardsSection(boards: const [_care, _ident], onTap: (_) {}),
      );
      expect(find.byType(CanopyAccentTile), findsNWidgets(2));
      expect(find.byIcon(LucideIcons.droplet), findsOneWidget);
      expect(find.byIcon(LucideIcons.leaf), findsOneWidget);
      expect(find.text('Care Problems'), findsOneWidget);
      expect(find.text('1 topic · 1 post'), findsOneWidget);
      expect(find.text('12 topics · 340 posts'), findsOneWidget);
      final style = tester
          .widget<Text>(find.text('12 topics · 340 posts'))
          .style!;
      expect(style.fontSize, AppTypography.label.fontSize);
    });

    testWidgets('description is one line; rows are at least 48pt', (
      tester,
    ) async {
      await _pump(
        tester,
        ForumBoardsSection(boards: const [_ident], onTap: (_) {}),
      );
      final desc = tester.widget<Text>(
        find.textContaining('What is this plant?'),
      );
      expect(desc.maxLines, 1);
      expect(
        tester.getSize(find.byType(CanopyPressable)).height,
        greaterThanOrEqualTo(48),
      );
    });

    testWidgets('tapping a row calls onTap with that board', (tester) async {
      ForumBoard? tapped;
      await _pump(
        tester,
        ForumBoardsSection(
          boards: const [_care, _ident],
          onTap: (b) => tapped = b,
        ),
      );
      await tester.tap(find.text('Plant Identification'));
      expect(tapped, _ident);
    });

    for (final brightness in Brightness.values) {
      testWidgets('no overflow at 320x640, x2.0, ${brightness.name}', (
        tester,
      ) async {
        await _pump(
          tester,
          ForumBoardsSection(boards: const [_care, _ident], onTap: (_) {}),
          brightness: brightness,
          size: const Size(320, 640),
          textScale: 2.0,
        );
        expect(tester.takeException(), isNull);
      });
    }
  });
}
