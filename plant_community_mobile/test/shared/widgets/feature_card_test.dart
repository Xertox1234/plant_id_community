import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/canopy_palette.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';
import 'package:plant_community_mobile/shared/widgets/feature_card.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(Brightness.dark, AppDensity.cozy),
  home: Scaffold(body: child),
);

void main() {
  testWidgets('renders title, description and icon', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: LucideIcons.bookOpen,
          title: 'Care guide',
          description: 'Learn plant care tips',
        ),
      ),
    );
    expect(find.text('Care guide'), findsOneWidget);
    expect(find.text('Learn plant care tips'), findsOneWidget);
    expect(find.byIcon(LucideIcons.bookOpen), findsOneWidget);
  });

  testWidgets('is built on the Canopy card material, not a flat fill', (
    tester,
  ) async {
    // The card used to paint a flat `cs.surface` container. Canopy surfaces are
    // gradient-lit — a flat one reads as off-system.
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: LucideIcons.camera,
          title: 'Identify',
          description: 'desc',
        ),
      ),
    );
    expect(find.byType(CanopyCard), findsOneWidget);

    final decorated = tester.widgetList<DecoratedBox>(
      find.descendant(
        of: find.byType(CanopyCard),
        matching: find.byType(DecoratedBox),
      ),
    );
    expect(
      decorated.any((d) => (d.decoration as BoxDecoration).gradient != null),
      isTrue,
      reason: 'the card surface must be a gradient, not a flat colour',
    );
  });

  testWidgets('each feature type carries its own accent tile', (tester) async {
    for (final (type, expected) in [
      (FeatureType.camera, CanopyTileTone.sage),
      (FeatureType.care, CanopyTileTone.orchid),
      (FeatureType.community, CanopyTileTone.bloom),
      (FeatureType.collection, CanopyTileTone.pollen),
    ]) {
      await tester.pumpWidget(
        _wrap(
          FeatureCard(
            icon: LucideIcons.leaf,
            title: 'T',
            description: 'd',
            type: type,
          ),
        ),
      );
      final tile = tester.widget<CanopyTile>(find.byType(CanopyTile));
      expect(tile.tone, expected, reason: '${type.name} tile tone');
    }
  });

  testWidgets('accent tiles keep dark ink on their light gradients', (
    tester,
  ) async {
    // Every tile gradient is light in BOTH modes, so the glyph must be the
    // fixed abyss ink — using onSurface renders light-on-light in dark mode.
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(icon: LucideIcons.leaf, title: 'T', description: 'd'),
      ),
    );
    final icon = tester.widget<Icon>(
      find.descendant(of: find.byType(CanopyTile), matching: find.byType(Icon)),
    );
    expect(icon.color, CanopyRamp.abyss);
  });

  testWidgets('calls onTap when tapped, and shows no affordance without it', (
    tester,
  ) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        FeatureCard(
          icon: LucideIcons.star,
          title: 'Favourite',
          description: 'desc',
          onTap: () => tapped = true,
        ),
      ),
    );
    expect(find.byIcon(LucideIcons.chevronRight), findsOneWidget);
    await tester.tap(find.byType(InkWell));
    expect(tapped, isTrue);

    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: LucideIcons.star,
          title: 'Favourite',
          description: 'desc',
        ),
      ),
    );
    expect(find.byIcon(LucideIcons.chevronRight), findsNothing);
  });
}
