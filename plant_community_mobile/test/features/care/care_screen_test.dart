import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/care/care_screen.dart';
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

  testWidgets('coming soon notice present', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.textContaining('coming soon'), findsOneWidget);
  });

  testWidgets('no crashes on pump', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(tester.takeException(), isNull);
  });
}
