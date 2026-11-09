import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/config/density_notifier.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/settings/settings_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

/// Fake density notifier that updates state WITHOUT writing to
/// FlutterSecureStorage — a real write throws MissingPluginException in a
/// widget test (there is no platform channel).
class _FakeDensityNotifier extends DensityNotifier {
  @override
  AppDensity build() => AppDensity.cozy;

  @override
  void setDensity(AppDensity density) => state = density;
}

Widget _wrap(Widget child, {bool loggedIn = false}) => ProviderScope(
  overrides: [
    densityProvider.overrideWith(_FakeDensityNotifier.new),
    authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: loggedIn)),
  ],
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

  testWidgets('a signed-in user gets an ACCOUNT section with Delete account, '
      'before ABOUT', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen(), loggedIn: true));

    final account = find.text('ACCOUNT');
    final tile = find.text('Delete account');
    await tester.scrollUntilVisible(tile, 200);
    expect(account, findsOneWidget);
    expect(tile, findsOneWidget);
    final about = find.text('ABOUT');
    await tester.scrollUntilVisible(about, 200);
    expect(
      tester.getTopLeft(about).dy,
      greaterThan(tester.getTopLeft(tile).dy),
    );
  });

  testWidgets('signed out, there is no account section', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));

    expect(find.text('ACCOUNT'), findsNothing);
    expect(find.text('Delete account'), findsNothing);
  });
}
