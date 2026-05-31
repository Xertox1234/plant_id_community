import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/grain_overlay.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';

Widget _wrap({required bool showGrain, required Widget child}) {
  final theme = AppTheme.build(
    AppPaletteChoice.loam, Brightness.light, AppDensity.cozy,
  ).copyWith(
    extensions: [
      GreenThumbExtension.fromColors(
        colors: AppPalettes.loam.light,
        density: AppDensity.cozy,
        brightness: Brightness.light,
      ).copyWith(showGrain: showGrain),
    ],
  );
  return MaterialApp(theme: theme, home: Scaffold(body: GrainOverlay(child: child)));
}

void main() {
  testWidgets('renders child regardless of showGrain', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: true, child: const Text('hello')));
    expect(find.text('hello'), findsOneWidget);
  });

  testWidgets('shows Stack overlay when showGrain is true', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: true, child: const SizedBox()));
    // When showGrain is true, a Stack is returned with grain overlay
    // Check for the IgnorePointer widget that wraps the grain image (ignoring: true)
    final ignorePointers = find.byWidgetPredicate(
      (widget) => widget is IgnorePointer && widget.ignoring,
    );
    expect(ignorePointers, findsOneWidget);
  });

  testWidgets('returns child directly when showGrain is false', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: false, child: const SizedBox()));
    // When showGrain is false, child is returned directly without Stack
    // Count the number of IgnorePointer(ignoring: true) — should be 0
    final grainIgnorePointers = find.byWidgetPredicate(
      (widget) => widget is IgnorePointer && widget.ignoring,
    );
    expect(grainIgnorePointers, findsNothing);
  });
}
