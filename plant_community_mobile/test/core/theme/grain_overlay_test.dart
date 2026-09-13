import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/grain_overlay.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';

Widget _wrap({required bool showGrain, required Widget child}) {
  final theme =
      AppTheme.build(
        AppPaletteChoice.loam,
        Brightness.light,
        AppDensity.cozy,
      ).copyWith(
        extensions: [
          GreenThumbExtension.fromColors(
            colors: AppPalettes.loam.light,
            density: AppDensity.cozy,
            brightness: Brightness.light,
          ).copyWith(showGrain: showGrain),
        ],
      );
  return MaterialApp(
    theme: theme,
    home: Scaffold(body: GrainOverlay(child: child)),
  );
}

void main() {
  testWidgets('renders child regardless of showGrain', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: true, child: const Text('hello')));
    // NECESSARY BUT NOT SUFFICIENT. find.text searches the widget TREE, not what
    // is visible on screen. This assertion passed for the entire life of the bug
    // below, while the child was completely hidden behind an opaque overlay.
    expect(find.text('hello'), findsOneWidget);
  });

  testWidgets('the grain layer is translucent, not an opaque sheet', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(showGrain: true, child: const Text('hello')));

    // The regression this guards: grain.png is an 8-bit GRAYSCALE png with no
    // alpha channel, so the widget itself has to supply the transparency. It
    // once used `color:` + `colorBlendMode:`, which tint the image's own pixels
    // and never blend it with the backdrop — leaving a solid sheet that hid every
    // screen using GrainOverlay, with only the Scaffold FAB still visible.
    final opacity = tester.widget<Opacity>(
      find.ancestor(of: find.byType(Image), matching: find.byType(Opacity)),
    );
    expect(
      opacity.opacity,
      lessThan(0.2),
      reason:
          'the grain must be a texture, not a scrim; near-1.0 hides the page',
    );

    final image = tester.widget<Image>(find.byType(Image));
    expect(
      image.repeat,
      ImageRepeat.repeat,
      reason:
          'tile at native size — BoxFit.cover stretched one 256px tile across '
          'the whole screen',
    );
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
