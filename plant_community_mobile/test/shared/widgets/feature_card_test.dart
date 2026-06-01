import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/shared/widgets/feature_card.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(
    AppPaletteChoice.loam,
    Brightness.light,
    AppDensity.cozy,
  ),
  home: Scaffold(body: child),
);

GreenThumbExtension get _ext => AppTheme.build(
  AppPaletteChoice.loam,
  Brightness.light,
  AppDensity.cozy,
).extension<GreenThumbExtension>()!;

void main() {
  testWidgets('renders title and description', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: Icons.book,
          title: 'Care Guide',
          description: 'Learn plant care tips',
        ),
      ),
    );
    expect(find.text('Care Guide'), findsOneWidget);
    expect(find.text('Learn plant care tips'), findsOneWidget);
  });

  testWidgets('renders icon', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: Icons.camera_alt,
          title: 'Camera',
          description: 'desc',
        ),
      ),
    );
    expect(find.byIcon(Icons.camera_alt), findsOneWidget);
  });

  testWidgets('care type uses ext.sky tint for icon container', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: Icons.book,
          title: 'Care',
          description: 'desc',
          type: FeatureType.care,
        ),
      ),
    );
    final ext = _ext;
    final containers = tester.widgetList<Container>(find.byType(Container));
    final hasSkyTint = containers.any(
      (c) =>
          c.decoration is BoxDecoration &&
          (c.decoration as BoxDecoration).color ==
              ext.sky.withValues(alpha: 0.1),
    );
    expect(hasSkyTint, isTrue);
  });

  testWidgets('community type uses ext.berry tint for icon container', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        const FeatureCard(
          icon: Icons.people,
          title: 'Community',
          description: 'desc',
          type: FeatureType.community,
        ),
      ),
    );
    final ext = _ext;
    final containers = tester.widgetList<Container>(find.byType(Container));
    final hasBerryTint = containers.any(
      (c) =>
          c.decoration is BoxDecoration &&
          (c.decoration as BoxDecoration).color ==
              ext.berry.withValues(alpha: 0.1),
    );
    expect(hasBerryTint, isTrue);
  });

  testWidgets('calls onTap when tapped', (tester) async {
    var tapped = false;
    await tester.pumpWidget(
      _wrap(
        FeatureCard(
          icon: Icons.star,
          title: 'Favorite',
          description: 'desc',
          onTap: () {
            tapped = true;
          },
        ),
      ),
    );
    await tester.tap(find.byType(InkWell));
    expect(tapped, isTrue);
  });

  testWidgets('uses custom icon color when provided', (tester) async {
    await tester.pumpWidget(
      _wrap(
        FeatureCard(
          icon: Icons.star,
          title: 'Custom',
          description: 'desc',
          iconColor: Colors.red,
        ),
      ),
    );
    final containers = tester.widgetList<Container>(find.byType(Container));
    final hasCustomColor = containers.any(
      (c) =>
          c.decoration is BoxDecoration &&
          (c.decoration as BoxDecoration).color ==
              Colors.red.withValues(alpha: 0.1),
    );
    expect(hasCustomColor, isTrue);
  });
}
