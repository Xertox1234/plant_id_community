import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/splash/splash_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';

/// Minimal router that renders SplashScreen and handles the /home redirect
/// so that the progress-timer navigation doesn't throw "GoRouter not found".
GoRouter _buildRouter() => GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (context, _) => const SplashScreen()),
    GoRoute(
      path: '/home',
      builder: (context, _) => const Scaffold(body: Text('Home')),
    ),
  ],
);

ThemeData get _theme => AppTheme.build(Brightness.light, AppDensity.cozy);

void main() {
  testWidgets('CanopyGround present in widget tree', (tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: _theme, home: const SplashScreen()),
    );
    expect(find.byType(CanopyGround), findsOneWidget);
    // The product mark, not a bespoke spinning disc.
    expect(find.byType(BrandMark), findsOneWidget);
    expect(find.text('Houseplant MD'), findsOneWidget);
    expect(find.text('PlantID'), findsNothing);
    // Drain pending timers — use router to allow context.go() to succeed
    await tester.pumpWidget(
      MaterialApp.router(theme: _theme, routerConfig: _buildRouter()),
    );
    await tester.pump(const Duration(seconds: 3));
  });

  testWidgets('no full-bleed gradient backdrop on the Scaffold body', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(theme: _theme, home: const SplashScreen()),
    );
    // The guard is about the BACKDROP: the splash takes its ground from the
    // theme, not a bespoke full-screen gradient. Small gradient boxes are
    // expected now — the brand mark's tile and badge are gradient-filled — so
    // this checks SIZE, not the mere presence of a gradient.
    final screen = tester.view.physicalSize / tester.view.devicePixelRatio;
    final fullBleedGradients = find
        .byWidgetPredicate(
          (w) =>
              w is Container &&
              w.decoration is BoxDecoration &&
              (w.decoration! as BoxDecoration).gradient is LinearGradient,
        )
        .evaluate()
        .where((e) {
          final size = tester.getSize(find.byWidget(e.widget));
          return size.width >= screen.width * 0.9;
        });
    expect(fullBleedGradients, isEmpty);
    // Drain pending timers
    await tester.pumpWidget(
      MaterialApp.router(theme: _theme, routerConfig: _buildRouter()),
    );
    await tester.pump(const Duration(seconds: 3));
  });
}
