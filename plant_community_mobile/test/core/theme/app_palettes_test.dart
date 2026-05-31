import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';

void main() {
  group('GreenThumbPalette', () {
    test('Garden light primary (moss) is correct', () {
      expect(AppPalettes.garden.light.moss, const Color(0xFF2F6B3A));
    });
    test('Garden dark primary (moss) is correct', () {
      expect(AppPalettes.garden.dark.moss, const Color(0xFFA8CC6E));
    });
    test('Loam light bg is correct', () {
      expect(AppPalettes.loam.light.bg, const Color(0xFFF6F0E2));
    });
    test('Loam dark bg is correct', () {
      expect(AppPalettes.loam.dark.bg, const Color(0xFF12100A));
    });
    test('Forest has same light and dark (inherently dark palette)', () {
      expect(AppPalettes.forest.light.bg, AppPalettes.forest.dark.bg);
    });
    test('Heritage dark falls back to Garden dark', () {
      expect(AppPalettes.heritage.dark.moss, AppPalettes.garden.dark.moss);
    });
  });

  group('AppPalettes.forChoice', () {
    test('returns correct palette for each choice', () {
      expect(AppPalettes.forChoice(AppPaletteChoice.garden), AppPalettes.garden);
      expect(AppPalettes.forChoice(AppPaletteChoice.loam), AppPalettes.loam);
      expect(AppPalettes.forChoice(AppPaletteChoice.forest), AppPalettes.forest);
      expect(AppPalettes.forChoice(AppPaletteChoice.heritage), AppPalettes.heritage);
    });
  });
}
