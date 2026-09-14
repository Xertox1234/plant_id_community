import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_typography.dart';

void main() {
  group('AppTypography font families', () {
    test('display uses BricolageGrotesque', () {
      expect(AppTypography.display.fontFamily, 'BricolageGrotesque');
    });
    test('display is roman — the web headings carry no font-style', () {
      expect(
        AppTypography.display.fontStyle ?? FontStyle.normal,
        FontStyle.normal,
      );
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
    test('label is the canonical mono eyebrow (.gt-label)', () {
      // Was a Geist 600 / 0.06em treatment; the canonical web `.gt-label` is
      // mono at 0.08em, and it is now the app's ONLY eyebrow style.
      expect(AppTypography.label.fontFamily, 'GeistMono');
      expect(AppTypography.label.fontSize, 11.0);
      expect(AppTypography.label.letterSpacing, closeTo(0.08 * 11, 0.01));
    });
    test('h1–h3 use BricolageGrotesque, roman not italic', () {
      for (final style in [
        AppTypography.h1,
        AppTypography.h2,
        AppTypography.h3,
      ]) {
        expect(style.fontFamily, 'BricolageGrotesque');
        // The canonical `.gt-*` rules carry NO font-style. The italic display
        // face was a Flutter-only invention.
        expect(style.fontStyle ?? FontStyle.normal, FontStyle.normal);
      }
    });
  });
}
