import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_typography.dart';

void main() {
  group('AppTypography font families', () {
    test('display uses BricolageGrotesque', () {
      expect(AppTypography.display.fontFamily, 'BricolageGrotesque');
    });
    test('display is italic', () {
      expect(AppTypography.display.fontStyle, FontStyle.italic);
    });
    test('display weight is 600', () {
      expect(AppTypography.display.fontWeight, FontWeight.w600);
    });
    test('body uses Geist', () {
      expect(AppTypography.body.fontFamily, 'Geist');
    });
    test('mono uses GeistMono', () {
      expect(AppTypography.mono.fontFamily, 'GeistMono');
    });
    test('eyebrow is uppercase Geist SemiBold 11px', () {
      expect(AppTypography.eyebrow.fontFamily, 'Geist');
      expect(AppTypography.eyebrow.fontWeight, FontWeight.w600);
      expect(AppTypography.eyebrow.fontSize, 11.0);
      expect(AppTypography.eyebrow.letterSpacing, closeTo(0.06 * 11, 0.01));
    });
    test('h1–h3 use BricolageGrotesque italic', () {
      for (final style in [AppTypography.h1, AppTypography.h2, AppTypography.h3]) {
        expect(style.fontFamily, 'BricolageGrotesque');
        expect(style.fontStyle, FontStyle.italic);
      }
    });
  });
}
