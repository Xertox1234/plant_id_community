import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';

void main() {
  final ext = GreenThumbExtension.fromColors(
    colors: AppPalettes.loam.light,
    density: AppDensity.cozy,
    brightness: Brightness.light,
  );

  group('GreenThumbExtension.fromColors', () {
    test('clay comes from palette', () {
      expect(ext.clay, AppPalettes.loam.light.clay);
    });
    test('padCard is cozy value 16', () {
      expect(ext.padCard, 16.0);
    });
    test('padScreen is cozy value 16', () {
      expect(ext.padScreen, 16.0);
    });
    test('gapY is cozy value 12', () {
      expect(ext.gapY, 12.0);
    });
    test('showGrain defaults true', () {
      expect(ext.showGrain, isTrue);
    });
  });

  group('copyWith', () {
    test('overrides specified fields', () {
      final copy = ext.copyWith(showGrain: false, padCard: 18.0);
      expect(copy.showGrain, isFalse);
      expect(copy.padCard, 18.0);
      expect(copy.clay, ext.clay); // unchanged
    });
  });

  group('density padding values', () {
    test('comfortable: padCard=18, padScreen=18, gapY=14', () {
      final e = GreenThumbExtension.fromColors(
        colors: AppPalettes.loam.light,
        density: AppDensity.comfortable,
        brightness: Brightness.light,
      );
      expect(e.padCard, 18.0);
      expect(e.padScreen, 18.0);
      expect(e.gapY, 14.0);
    });
    test('compact: padCard=12, padScreen=14, gapY=10', () {
      final e = GreenThumbExtension.fromColors(
        colors: AppPalettes.loam.light,
        density: AppDensity.compact,
        brightness: Brightness.light,
      );
      expect(e.padCard, 12.0);
      expect(e.padScreen, 14.0);
      expect(e.gapY, 10.0);
    });
  });
}
