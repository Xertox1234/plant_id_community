import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/splash/splash_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/grain_overlay.dart';

/// Minimal router that renders SplashScreen and handles the /home redirect
/// so that the progress-timer navigation doesn't throw "GoRouter not found".
GoRouter _buildRouter() => GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, _) => const SplashScreen(),
        ),
        GoRoute(
          path: '/home',
          builder: (context, _) => const Scaffold(body: Text('Home')),
        ),
      ],
    );

ThemeData get _theme =>
    AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy);

void main() {
  testWidgets('GrainOverlay present in widget tree', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: _theme,
      home: const SplashScreen(),
    ));
    expect(find.byType(GrainOverlay), findsOneWidget);
    // Drain pending timers — use router to allow context.go() to succeed
    await tester.pumpWidget(MaterialApp.router(
      theme: _theme,
      routerConfig: _buildRouter(),
    ));
    await tester.pump(const Duration(seconds: 3));
  });

  testWidgets('no LinearGradient background on Scaffold body', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: _theme,
      home: const SplashScreen(),
    ));
    final gradientContainers = tester
        .widgetList<Container>(find.byType(Container))
        .where((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).gradient is LinearGradient);
    expect(gradientContainers.isEmpty, isTrue);
    // Drain pending timers
    await tester.pumpWidget(MaterialApp.router(
      theme: _theme,
      routerConfig: _buildRouter(),
    ));
    await tester.pump(const Duration(seconds: 3));
  });
}
