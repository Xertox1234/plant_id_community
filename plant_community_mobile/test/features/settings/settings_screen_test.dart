import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/config/palette_notifier.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/settings/settings_screen.dart';

/// Fake palette notifier that updates state WITHOUT writing to
/// FlutterSecureStorage — a real write throws MissingPluginException in a
/// widget test (no platform), and `setPalette` does an unguarded
/// `unawaited(_storage.write(...))`.
class _FakePaletteNotifier extends PaletteNotifier {
  @override
  PaletteSettings build() => const PaletteSettings.defaults();

  @override
  void setPalette(AppPaletteChoice choice) =>
      state = state.copyWith(palette: choice);

  @override
  void setDensity(AppDensity density) =>
      state = state.copyWith(density: density);
}

Widget _wrap(Widget child) => ProviderScope(
  overrides: [paletteProvider.overrideWith(_FakePaletteNotifier.new)],
  child: MaterialApp(
    theme: AppTheme.build(
      AppPaletteChoice.loam,
      Brightness.light,
      AppDensity.cozy,
    ),
    home: child,
  ),
);

void main() {
  testWidgets('renders 4 palette swatches', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    // Each palette name appears as text on a swatch.
    expect(find.text('Loam'), findsOneWidget);
    expect(find.text('Garden'), findsOneWidget);
    expect(find.text('Forest'), findsOneWidget);
    expect(find.text('Heritage'), findsOneWidget);
  });

  testWidgets('density SegmentedButton renders 3 segments', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    expect(find.text('Comfortable'), findsOneWidget);
    expect(find.text('Cozy'), findsOneWidget);
    expect(find.text('Compact'), findsOneWidget);
  });

  testWidgets('tapping Garden swatch does not crash', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    await tester.tap(find.text('Garden'));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
