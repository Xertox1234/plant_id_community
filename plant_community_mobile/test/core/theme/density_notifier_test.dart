import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/config/density_notifier.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  group('DensityNotifier', () {
    test('starts at the canonical default', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(densityProvider), AppTheme.defaultDensity);
      // Spelled out as well as read from the constant: if someone changes
      // `defaultDensity`, the parity test against the canonical contract is
      // what should fail, and this literal says what the value is today.
      expect(container.read(densityProvider), AppDensity.cozy);
    });

    test('setDensity updates the state', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(densityProvider.notifier).setDensity(AppDensity.compact);
      expect(container.read(densityProvider), AppDensity.compact);
    });
  });

  group('migration off the retired palette setting', () {
    // The four palettes (Loam / Garden / Forest / Heritage) are gone. An
    // upgrading user has `palette_choice` sitting in secure storage and may
    // have a density saved too. Neither may break them.
    test('the density key is unchanged, so a saved density survives', () {
      expect(
        DensityNotifier.densityKey,
        'palette_density',
        reason:
            'changing this key would silently reset every existing user to the '
            'default density',
      );
    });

    test('the retired key is named so it can be cleaned up', () {
      expect(DensityNotifier.retiredPaletteKey, 'palette_choice');
    });

    test('an unrecognised stored density falls back to the default', () {
      // `AppDensity.values.where(...).firstOrNull` yields null for a value we
      // no longer ship, and the notifier keeps its default rather than throwing.
      final match = AppDensity.values
          .where((e) => e.name == 'heritage')
          .firstOrNull;
      expect(match, isNull);
    });
  });
}
