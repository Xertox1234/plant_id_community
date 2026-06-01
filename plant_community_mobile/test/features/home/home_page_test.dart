import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/home/home_page.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/core/theme/grain_overlay.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap() => ProviderScope(
  child: MaterialApp(
    theme: AppTheme.build(
      AppPaletteChoice.loam,
      Brightness.light,
      AppDensity.cozy,
    ),
    home: const HomePage(),
  ),
);

void main() {
  testWidgets('ClayButton present for Get Started CTA', (tester) async {
    await tester.pumpWidget(_wrap());
    expect(find.byType(ClayButton), findsOneWidget);
  });

  testWidgets('GrainOverlay present in widget tree', (tester) async {
    await tester.pumpWidget(_wrap());
    expect(find.byType(GrainOverlay), findsOneWidget);
  });

  testWidgets('eyebrow label PLANT IDENTIFICATION present', (tester) async {
    await tester.pumpWidget(_wrap());
    expect(find.text('PLANT IDENTIFICATION'), findsOneWidget);
  });
}
