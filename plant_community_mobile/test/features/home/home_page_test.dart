import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/home/home_page.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_label.dart';
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
  testWidgets('hero is diagnosis-first: label, headline, body, one CTA', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    expect(find.text('PLANT HEALTH CHECK'), findsOneWidget);
    expect(find.text("What's wrong with your plant?"), findsOneWidget);
    expect(
      find.text(
        "Photograph the problem. We'll name the plant, find the cause and "
        'tell you what to do.',
      ),
      findsOneWidget,
    );
    expect(find.byKey(HomePage.checkPlantKey), findsOneWidget);
    expect(find.text('Check a sick plant'), findsOneWidget);
    expect(find.byKey(HomePage.justIdentifyKey), findsOneWidget);
    expect(find.text('Join the forum'), findsNothing);
    expect(find.text('Instant Identification'), findsNothing);
    expect(find.text('Diagnose a Sick Plant'), findsNothing);
  });

  testWidgets('"plant?" is the accent-coloured word of the headline', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    final rich = tester.widget<RichText>(
      find.byWidgetPredicate(
        (w) =>
            w is RichText &&
            w.text.toPlainText() == "What's wrong with your plant?",
      ),
    );
    TextSpan? accent;
    rich.text.visitChildren((span) {
      if (span is TextSpan && span.text == 'plant?') accent = span;
      return true;
    });
    expect(accent, isNotNull);
    expect(
      accent!.style?.color,
      Theme.of(tester.element(find.byType(HomePage))).colorScheme.primary,
    );
  });

  group('hero actions open the camera', () {
    Future<List<String>> pumpRouted(WidgetTester tester) async {
      final pushed = <String>[];
      final router = GoRouter(
        routes: [
          GoRoute(path: '/', builder: (_, _) => const HomePage()),
          GoRoute(
            path: '/camera',
            builder: (_, state) {
              pushed.add(state.uri.toString());
              return const Scaffold(body: Text('camera'));
            },
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp.router(
            theme: AppTheme.build(Brightness.light, AppDensity.cozy),
            routerConfig: router,
          ),
        ),
      );
      return pushed;
    }

    testWidgets('Check a sick plant goes to /camera', (tester) async {
      final pushed = await pumpRouted(tester);
      await tester.tap(find.text('Check a sick plant'));
      await tester.pumpAndSettle();
      expect(pushed, ['/camera']);
    });

    testWidgets('Just identify a plant goes to /camera?mode=identify', (
      tester,
    ) async {
      final pushed = await pumpRouted(tester);
      await tester.tap(find.text('Just identify a plant'));
      await tester.pumpAndSettle();
      expect(pushed, ['/camera?mode=identify']);
    });
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
    expect(find.text('PLANT HEALTH CHECK'), findsOneWidget);
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
