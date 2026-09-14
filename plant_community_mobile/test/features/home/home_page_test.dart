import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/home/home_page.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_label.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/shared/widgets/feature_card.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap() => ProviderScope(
  child: MaterialApp(
    theme: AppTheme.build(Brightness.light, AppDensity.cozy),
    home: const HomePage(),
  ),
);

void main() {
  testWidgets('hero offers a primary and a ghost action, like the web', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    // The web hero pairs a primary CTA with a ghost secondary
    // (`Get Started` / `Join Community` in HomePage.tsx).
    expect(find.text('Identify a plant'), findsOneWidget);
    expect(find.text('Join the forum'), findsOneWidget);
    final ghost = tester.widget<ClayButton>(
      find.byWidgetPredicate(
        (w) => w is ClayButton && w.label == 'Join the forum',
      ),
    );
    expect(ghost.variant, ClayButtonVariant.ghost);
  });

  testWidgets('shows the product mark and name, never a legacy identity', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    expect(find.byType(BrandMark), findsOneWidget);
    expect(find.text('Houseplant MD'), findsOneWidget);
    expect(find.text('Welcome to PlantID'), findsNothing);
  });

  testWidgets('CanopyGround fills the viewport, not the scrolled content', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    expect(find.byType(CanopyGround), findsOneWidget);

    // The glow must be BEHIND the scroller, not inside it. A Stack inside a
    // SingleChildScrollView sizes to its non-positioned child, so a
    // CanopyGround nested under the scroll view is as tall as the content —
    // the glow then stretches and scrolls away instead of staying put, and
    // nothing about `findsOneWidget` would notice. Home's content is several
    // viewports tall, so the heights differ by a lot when this regresses.
    final screen = tester.view.physicalSize / tester.view.devicePixelRatio;
    final groundHeight = tester.getSize(find.byType(CanopyGround)).height;
    final contentHeight = tester
        .getSize(find.byType(SingleChildScrollView))
        .height;
    expect(groundHeight, lessThanOrEqualTo(screen.height));
    expect(groundHeight, greaterThanOrEqualTo(contentHeight));
  });

  testWidgets('eyebrow uses the one canonical label treatment', (tester) async {
    await tester.pumpWidget(_wrap());
    // CanopyLabel uppercases — Flutter has no `text-transform`.
    expect(find.byType(CanopyLabel), findsOneWidget);
    expect(find.text('PLANT IDENTIFICATION COMMUNITY'), findsOneWidget);
  });

  testWidgets('Care feature card has onTap wired', (tester) async {
    await tester.pumpWidget(_wrap());
    final careCard = tester.widget<FeatureCard>(
      find.byWidgetPredicate(
        (w) => w is FeatureCard && w.title == 'Care Instructions',
      ),
    );
    expect(careCard.onTap, isNotNull);
  });
}
