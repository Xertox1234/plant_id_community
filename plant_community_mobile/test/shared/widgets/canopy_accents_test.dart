import 'dart:ui' show Tristate;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_accents.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';

const _tone = Color(0xFF3366CC);

Widget _wrap(Widget child, {bool disableAnimations = false}) => MaterialApp(
  theme: AppTheme.build(Brightness.dark, AppDensity.cozy),
  home: MediaQuery(
    data: MediaQueryData(disableAnimations: disableAnimations),
    child: Scaffold(body: Center(child: child)),
  ),
);

double _scaleOf(WidgetTester tester) {
  final transforms = find.descendant(
    of: find.byType(CanopyPressable),
    matching: find.byType(Transform),
  );
  if (transforms.evaluate().isEmpty) return 1;
  return tester
      .widget<Transform>(transforms.first)
      .transform
      .storage[0]; // x scale (getMaxScaleOnAxis would include z = 1)
}

void main() {
  testWidgets('tile takes fill, border and icon colour from the tone', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(const CanopyAccentTile(icon: LucideIcons.leaf, tone: _tone)),
    );
    final box = tester.widget<DecoratedBox>(
      find.descendant(
        of: find.byType(CanopyAccentTile),
        matching: find.byType(DecoratedBox),
      ),
    );
    final deco = box.decoration as BoxDecoration;
    expect(deco.color, _tone.withValues(alpha: 0.15));
    expect((deco.border! as Border).top.color, _tone.withValues(alpha: 0.30));
    expect(tester.widget<Icon>(find.byIcon(LucideIcons.leaf)).color, _tone);
    expect(tester.getSize(find.byType(CanopyAccentTile)), const Size(40, 40));
  });

  testWidgets('chip takes fill and text colour from the tone', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const CanopyChip(label: 'Care', tone: _tone, icon: LucideIcons.droplet),
      ),
    );
    final deco =
        tester
                .widget<DecoratedBox>(
                  find.descendant(
                    of: find.byType(CanopyChip),
                    matching: find.byType(DecoratedBox),
                  ),
                )
                .decoration
            as BoxDecoration;
    expect(deco.color, _tone.withValues(alpha: 0.15));
    expect(tester.widget<Text>(find.text('Care')).style!.color, _tone);
    expect(find.byIcon(LucideIcons.droplet), findsOneWidget);
  });

  testWidgets('grouped card with 3 rows renders exactly 2 dividers', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(const CanopyGroupedCard(rows: [Text('a'), Text('b'), Text('c')])),
    );
    expect(find.byType(CanopyGroupedCardDivider), findsNWidgets(2));
    expect(find.text('c'), findsOneWidget);
  });

  group('CanopyPressable', () {
    testWidgets('scale style is < 1 while held and 1 after release', (
      tester,
    ) async {
      var taps = 0;
      await tester.pumpWidget(
        _wrap(
          CanopyPressable(
            style: CanopyPressStyle.scale,
            onTap: () => taps++,
            child: const SizedBox(width: 120, height: 60),
          ),
        ),
      );
      expect(_scaleOf(tester), 1);
      final g = await tester.startGesture(
        tester.getCenter(find.byType(CanopyPressable)),
      );
      // tap-down lands after the press deadline; the spring's first frame is
      // elapsed zero, so give it a few frames.
      await tester.pump(const Duration(milliseconds: 120));
      await tester.pump(const Duration(milliseconds: 16));
      await tester.pump(const Duration(milliseconds: 200));
      expect(_scaleOf(tester), lessThan(1));
      expect(_scaleOf(tester), greaterThanOrEqualTo(0.98));
      await g.up();
      await tester.pumpAndSettle();
      expect(_scaleOf(tester), 1);
      expect(taps, 1);
    });

    testWidgets('disableAnimations: no scale transform, dims instead', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          CanopyPressable(
            style: CanopyPressStyle.scale,
            onTap: () {},
            child: const SizedBox(width: 120, height: 60),
          ),
          disableAnimations: true,
        ),
      );
      final g = await tester.startGesture(
        tester.getCenter(find.byType(CanopyPressable)),
      );
      await tester.pump(const Duration(milliseconds: 200));
      expect(
        find.descendant(
          of: find.byType(CanopyPressable),
          matching: find.byType(Transform),
        ),
        findsNothing,
      );
      final opacity = tester.widget<Opacity>(
        find.descendant(
          of: find.byType(CanopyPressable),
          matching: find.byType(Opacity),
        ),
      );
      expect(opacity.opacity, 0.7);
      await g.up();
      await tester.pump();
    });

    testWidgets('highlight style paints surface3 while pressed', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          CanopyPressable(
            onTap: () {},
            child: const SizedBox(width: 120, height: 60),
          ),
        ),
      );
      final surface3 = tester
          .element(find.byType(CanopyPressable))
          .canopy
          .surface3;
      Color? painted() => tester
          .widgetList<ColoredBox>(
            find.descendant(
              of: find.byType(CanopyPressable),
              matching: find.byType(ColoredBox),
            ),
          )
          .map((b) => b.color)
          .where((c) => c == surface3)
          .firstOrNull;
      expect(painted(), isNull);
      final g = await tester.startGesture(
        tester.getCenter(find.byType(CanopyPressable)),
      );
      await tester.pump(const Duration(milliseconds: 50));
      expect(painted(), surface3);
      await g.up();
      await tester.pump();
      expect(painted(), isNull);
    });

    testWidgets('exposes button + expanded semantics', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        _wrap(
          CanopyPressable(
            onTap: () {},
            expanded: true,
            semanticLabel: 'Boards',
            child: const SizedBox(width: 120, height: 60),
          ),
        ),
      );
      final data = tester
          .getSemantics(find.bySemanticsLabel('Boards'))
          .getSemanticsData();
      expect(data.flagsCollection.isButton, isTrue);
      expect(data.flagsCollection.isExpanded, Tristate.isTrue);
      handle.dispose();
    });

    testWidgets('null onTap is inert and not a button', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        _wrap(
          const CanopyPressable(
            onTap: null,
            style: CanopyPressStyle.scale,
            semanticLabel: 'Inert',
            child: SizedBox(width: 120, height: 60),
          ),
        ),
      );
      final g = await tester.startGesture(
        tester.getCenter(find.byType(CanopyPressable)),
      );
      await tester.pump(const Duration(milliseconds: 300));
      expect(_scaleOf(tester), 1);
      await g.up();
      final data = tester
          .getSemantics(find.bySemanticsLabel('Inert'))
          .getSemanticsData();
      expect(data.flagsCollection.isButton, isFalse);
      handle.dispose();
    });
  });

  for (final brightness in Brightness.values) {
    for (final scale in [1.0, 2.0]) {
      for (final width in [320.0, 375.0]) {
        testWidgets('no overflow ${brightness.name} ${width}w x$scale', (
          tester,
        ) async {
          tester.view.physicalSize = Size(width, 640);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.reset);
          final handle = tester.ensureSemantics();
          await tester.pumpWidget(
            MaterialApp(
              theme: AppTheme.build(brightness, AppDensity.cozy),
              home: MediaQuery(
                data: MediaQueryData(
                  size: Size(width, 640),
                  textScaler: TextScaler.linear(scale),
                ),
                child: Scaffold(
                  body: Builder(
                    builder: (context) {
                      final c = context.canopy;
                      return SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          children: [
                            CanopyGroupedCard(
                              rows: [
                                for (final t in [c.leaf, c.clay, c.berry])
                                  CanopyPressable(
                                    onTap: () {},
                                    child: Padding(
                                      padding: const EdgeInsets.all(12),
                                      child: Row(
                                        children: [
                                          CanopyAccentTile(
                                            icon: LucideIcons.leaf,
                                            tone: t,
                                          ),
                                          const SizedBox(width: 12),
                                          const Expanded(
                                            child: Text(
                                              'A fairly long board title that wraps',
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                            // Chips live on a card in the product, so contrast
                            // is judged there, for every tone.
                            CanopyCard(
                              child: Wrap(
                                spacing: 6,
                                runSpacing: 6,
                                children: [
                                  for (final t in [
                                    c.leaf,
                                    c.clay,
                                    c.berry,
                                    c.sky,
                                  ])
                                    CanopyChip(
                                      label: 'Identification and more',
                                      tone: t,
                                    ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
              ),
            ),
          );
          expect(tester.takeException(), isNull);
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          await expectLater(tester, meetsGuideline(textContrastGuideline));
          handle.dispose();
        });
      }
    }
  }
}
