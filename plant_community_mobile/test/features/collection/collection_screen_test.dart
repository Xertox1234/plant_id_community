import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/collection/collection_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(
    AppPaletteChoice.loam,
    Brightness.light,
    AppDensity.cozy,
  ),
  home: child,
);

/// Pump on a portrait phone-sized surface. The default 800x600 test surface is
/// wide and short, which makes the aspect-0.8 grid cells very tall and pushes
/// the second grid row + footer out of the laid-out (findable) region.
Future<void> _pump(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(400, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(_wrap(const CollectionScreen()));
}

void main() {
  testWidgets('renders 3 sample plant cards', (tester) async {
    await _pump(tester);
    expect(find.text('Monstera'), findsOneWidget);
    expect(find.text('Golden Barrel'), findsOneWidget);
    expect(find.text('Peace Lily'), findsOneWidget);
  });

  testWidgets('add card present', (tester) async {
    await _pump(tester);
    expect(find.text('Identify a plant'), findsOneWidget);
  });

  testWidgets('eyebrow count text present', (tester) async {
    await _pump(tester);
    expect(find.text('3 PLANTS IDENTIFIED'), findsOneWidget);
  });

  testWidgets('coming soon notice present', (tester) async {
    await _pump(tester);
    expect(find.textContaining('coming soon'), findsOneWidget);
  });
}
