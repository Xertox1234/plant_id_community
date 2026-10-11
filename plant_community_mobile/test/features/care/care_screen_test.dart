import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/features/care/care_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(Brightness.light, AppDensity.cozy),
  home: child,
);

void main() {
  testWidgets('renders 4 care category cards', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.text('Watering'), findsOneWidget);
    expect(find.text('Sunlight'), findsOneWidget);
    expect(find.text('Soil & Fertilising'), findsOneWidget);
    expect(find.text('Temperature'), findsOneWidget);
  });

  testWidgets('eyebrow CARE GUIDES present', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.text('CARE GUIDES'), findsOneWidget);
  });

  // Was "coming soon notice present": the guides are built now (todo 386),
  // so the notice is gone and the cards navigate instead.
  testWidgets('no coming-soon notice: the guides exist', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.textContaining('coming soon'), findsNothing);
  });

  testWidgets('every card shows a chevron AND navigates to the care guides', (
    tester,
  ) async {
    for (final title in [
      'Watering',
      'Sunlight',
      'Soil & Fertilising',
      'Temperature',
    ]) {
      final router = GoRouter(
        initialLocation: AppRoutes.care,
        routes: [
          GoRoute(
            path: AppRoutes.care,
            builder: (context, state) => const CareScreen(),
          ),
          GoRoute(
            path: AppRoutes.blog,
            builder: (context, state) => Text(
              'blog tag=${state.uri.queryParameters['tag']} '
              'title=${state.extra}',
            ),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        MaterialApp.router(
          theme: AppTheme.build(Brightness.light, AppDensity.cozy),
          routerConfig: router,
        ),
      );
      await tester.pumpAndSettle();

      final tile = find.ancestor(
        of: find.text(title),
        matching: find.byType(ListTile),
      );
      expect(
        find.descendant(
          of: tile,
          matching: find.byIcon(LucideIcons.chevronRight),
        ),
        findsOneWidget,
      );
      expect(tester.widget<ListTile>(tile).onTap, isNotNull);

      await tester.ensureVisible(tile);
      await tester.tap(tile);
      await tester.pumpAndSettle();
      expect(
        find.text('blog tag=$careGuideTag title=$title guides'),
        findsOneWidget,
      );
    }
    expect(careGuideTag, 'care-guide');
  });

  testWidgets('no crashes on pump', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(tester.takeException(), isNull);
  });
}
