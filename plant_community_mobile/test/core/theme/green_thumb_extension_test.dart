import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/canopy_palette.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  GreenThumbExtension build(
    AppDensity density, {
    Brightness brightness = Brightness.dark,
  }) => GreenThumbExtension.fromColors(
    colors: CanopyPalette.of(brightness),
    density: density,
    brightness: brightness,
  );

  final ext = build(AppDensity.cozy);

  group('GreenThumbExtension.fromColors', () {
    test('accents come from the Canopy palette', () {
      expect(ext.clay, CanopyPalette.dark.clay);
      expect(ext.berry, CanopyPalette.dark.berry);
      expect(ext.sky, CanopyPalette.dark.sky);
      expect(ext.ink2, CanopyPalette.dark.ink2);
      expect(ext.line, CanopyPalette.dark.line);
    });

    test('cozy padding is 16/16/12', () {
      expect(ext.padCard, 16.0);
      expect(ext.padScreen, 16.0);
      expect(ext.gapY, 12.0);
    });

    test('comfortable is 18/18/14 and compact is 12/14/10', () {
      final comfortable = build(AppDensity.comfortable);
      expect(
        [comfortable.padCard, comfortable.padScreen, comfortable.gapY],
        [18.0, 18.0, 14.0],
      );
      final compact = build(AppDensity.compact);
      expect(
        [compact.padCard, compact.padScreen, compact.gapY],
        [12.0, 14.0, 10.0],
      );
    });
  });

  group('shadows', () {
    test('dark shadows are stronger than light ones', () {
      // Regression: Flutter previously used the web's LIGHT-mode alphas in both
      // modes, so elevation was invisible against the near-black dark ground.
      final darkShadow = build(AppDensity.cozy).shadow2;
      final lightShadow = build(
        AppDensity.cozy,
        brightness: Brightness.light,
      ).shadow2;
      expect(
        darkShadow.last.color.a,
        greaterThan(lightShadow.last.color.a),
        reason: 'a shadow must work against the dark ground',
      );
    });

    test('light shadows are tinted pine, dark ones are black', () {
      final darkExt = build(AppDensity.cozy);
      expect(darkExt.shadow1.first.color.withValues(alpha: 1), Colors.black);
      // The web's dark shadow-1 lip is 10% — Flutter previously used 4%.
      expect(darkExt.shadow1.first.color.a, closeTo(0.10, 0.005));
      final lightExt = build(AppDensity.cozy, brightness: Brightness.light);
      // Pine (#0B2B26), not the old #1B2218.
      expect(
        lightExt.shadow1.first.color.withValues(alpha: 1),
        CanopyRamp.pine,
      );
    });

    test('each level is a tight lip plus a soft spread', () {
      for (final shadow in [ext.shadow1, ext.shadow2, ext.shadow3]) {
        expect(shadow, hasLength(2));
        expect(shadow.first.blurRadius, 0, reason: 'the lip has no blur');
        expect(shadow.last.blurRadius, greaterThan(0));
      }
    });
  });

  group('materials', () {
    test('the card gradient has three stops on a 150° axis', () {
      expect(ext.gradCard, hasLength(3));
      expect(ext.gradCardStops, [0.0, 0.46, 1.0]);
      final gradient = ext.cardGradient;
      expect(gradient.begin, const Alignment(-0.5, -0.866));
      expect(gradient.end, const Alignment(0.5, 0.866));
    });

    test('the CTA gradient runs top-left to bottom-right', () {
      expect(ext.ctaGradient.colors, hasLength(2));
      expect(ext.ctaGradient.begin, Alignment.topLeft);
      expect(ext.ctaGradient.end, Alignment.bottomRight);
    });

    test('the sweep fades to fully transparent', () {
      final sweep = ext.sweepGradient;
      expect(sweep.colors.last.a, 0);
      expect(sweep.colors.first.a, greaterThan(0));
    });

    test('dark mode layers two ambient radials, light mode one', () {
      expect(ext.ambient, hasLength(2));
      expect(
        build(AppDensity.cozy, brightness: Brightness.light).ambient,
        hasLength(1),
      );
    });

    test('cardDecoration carries the gradient, border and radius', () {
      final decoration = ext.cardDecoration();
      expect(decoration.gradient, isA<LinearGradient>());
      expect(decoration.border, isNotNull);
      expect(decoration.borderRadius, isNotNull);
    });
  });

  group('fallback', () {
    test('is dark Canopy at cozy — the app defaults', () {
      // A stand-in palette here would hide colour bugs in every widget test
      // that pumps a bare ThemeData.
      expect(GreenThumbExtension.fallback.clay, CanopyPalette.dark.clay);
      expect(GreenThumbExtension.fallback.padCard, 16.0);
    });
  });

  group('copyWith', () {
    test('overrides only the named fields', () {
      final copy = ext.copyWith(padCard: 18.0);
      expect(copy.padCard, 18.0);
      expect(copy.clay, ext.clay);
      expect(copy.gapY, ext.gapY);
    });
  });

  group('lerp', () {
    test('interpolates between the two modes without throwing', () {
      final lightExt = build(AppDensity.cozy, brightness: Brightness.light);
      final mid = ext.lerp(lightExt, 0.5);
      expect(mid.padCard, 16.0);
      expect(mid.gradCard, hasLength(3));
      expect(mid.ambient, isNotEmpty);
    });
  });
}
