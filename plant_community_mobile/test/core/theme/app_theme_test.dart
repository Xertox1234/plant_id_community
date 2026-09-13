import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  group('Material 3 NavigationBar theme (todo 384)', () {
    // MainShell renders a NavigationBar. The pre-existing
    // `bottomNavigationBarTheme` styles BottomNavigationBar -- a different,
    // Material 2 widget -- and todo 384 read its presence as proof the nav bar
    // was already themed. It was not: without `navigationBarTheme` the shell
    // renders in stock M3 purple. These assert against the PALETTE, so they
    // track a palette change rather than pinning today's values.
    test('navigationBarTheme is defined, not just the legacy M2 one', () {
      final theme = AppTheme.build(
        AppPaletteChoice.garden,
        Brightness.light,
        AppDensity.cozy,
      );
      expect(
        theme.navigationBarTheme.backgroundColor,
        AppPalettes.garden.light.bg2,
        reason:
            'the shell nav bar must use the Green Thumb surface, not the '
            'M3 default',
      );
    });

    test('selected and unselected destinations resolve to palette colours', () {
      final theme = AppTheme.build(
        AppPaletteChoice.garden,
        Brightness.dark,
        AppDensity.cozy,
      );
      final icons = theme.navigationBarTheme.iconTheme;
      expect(icons, isNotNull);

      final selected = icons!.resolve({WidgetState.selected})?.color;
      final unselected = icons.resolve(<WidgetState>{})?.color;

      expect(selected, AppPalettes.garden.dark.moss);
      expect(unselected, AppPalettes.garden.dark.ink3);
      // A theme that resolved both states the same would leave the user unable
      // to tell which tab they are on.
      expect(selected, isNot(unselected));
    });
  });

  group('AppTheme.build', () {
    test('Garden light primary equals moss light', () {
      final theme = AppTheme.build(
        AppPaletteChoice.garden,
        Brightness.light,
        AppDensity.cozy,
      );
      expect(theme.colorScheme.primary, AppPalettes.garden.light.moss);
    });

    test('Garden dark primary equals moss dark', () {
      final theme = AppTheme.build(
        AppPaletteChoice.garden,
        Brightness.dark,
        AppDensity.cozy,
      );
      expect(theme.colorScheme.primary, AppPalettes.garden.dark.moss);
    });

    test('Loam light primary equals moss light', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam,
        Brightness.light,
        AppDensity.cozy,
      );
      expect(theme.colorScheme.primary, AppPalettes.loam.light.moss);
    });

    test('Forest light and dark produce same primary', () {
      final light = AppTheme.build(
        AppPaletteChoice.forest,
        Brightness.light,
        AppDensity.cozy,
      );
      final dark = AppTheme.build(
        AppPaletteChoice.forest,
        Brightness.dark,
        AppDensity.cozy,
      );
      expect(light.colorScheme.primary, dark.colorScheme.primary);
    });

    test('Heritage dark falls back to Garden dark primary', () {
      final hDark = AppTheme.build(
        AppPaletteChoice.heritage,
        Brightness.dark,
        AppDensity.cozy,
      );
      final gDark = AppTheme.build(
        AppPaletteChoice.garden,
        Brightness.dark,
        AppDensity.cozy,
      );
      expect(hDark.colorScheme.primary, gDark.colorScheme.primary);
    });

    test('GreenThumbExtension is attached', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam,
        Brightness.light,
        AppDensity.cozy,
      );
      expect(theme.extension<GreenThumbExtension>(), isNotNull);
    });

    test('Compact density sets padCard to 12', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam,
        Brightness.light,
        AppDensity.compact,
      );
      final ext = theme.extension<GreenThumbExtension>()!;
      expect(ext.padCard, 12.0);
    });

    test('useMaterial3 is true', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam,
        Brightness.light,
        AppDensity.cozy,
      );
      expect(theme.useMaterial3, isTrue);
    });
  });
}
