import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
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
