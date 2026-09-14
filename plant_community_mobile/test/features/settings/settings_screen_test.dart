import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/config/density_notifier.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/settings/settings_screen.dart';

/// Fake density notifier that updates state WITHOUT writing to
/// FlutterSecureStorage — a real write throws MissingPluginException in a
/// widget test (there is no platform channel).
class _FakeDensityNotifier extends DensityNotifier {
  @override
  AppDensity build() => AppDensity.cozy;

  @override
  void setDensity(AppDensity density) => state = density;
}

Widget _wrap(Widget child) => ProviderScope(
  overrides: [densityProvider.overrideWith(_FakeDensityNotifier.new)],
  child: MaterialApp(
    theme: AppTheme.build(Brightness.light, AppDensity.cozy),
    home: child,
  ),
);

void main() {
  testWidgets('offers no palette choice — Canopy is one identity', (
    tester,
  ) async {
    // The four palettes (Loam / Garden / Forest / Heritage) were a
    // Flutter-only invention; the design spec §2 retired the switcher.
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    for (final name in ['Loam', 'Garden', 'Forest', 'Heritage']) {
      expect(find.text(name), findsNothing, reason: '$name palette is retired');
    }
  });

  testWidgets('shows the canonical product name', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    expect(find.text('Houseplant MD'), findsOneWidget);
    expect(find.text('Plant Community'), findsNothing);
  });

  testWidgets('density SegmentedButton renders 3 segments', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    expect(find.text('Comfortable'), findsOneWidget);
    expect(find.text('Cozy'), findsOneWidget);
    expect(find.text('Compact'), findsOneWidget);
  });
}
