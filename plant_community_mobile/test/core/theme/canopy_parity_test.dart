import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/constants/app_spacing.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_typography.dart';
import 'package:plant_community_mobile/core/theme/canopy_palette.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

/// Cross-platform token parity: the Dart palette vs. the canonical contract.
///
/// `design/canopy-tokens.json` is generated from `web/src/index.css` — the
/// canonical design reference — by `scripts/design/extract_canopy_tokens.mjs`,
/// whose oklab maths is itself pinned to Chromium's painted pixels by
/// `scripts/design/verify_canopy_tokens_in_browser.mjs`.
///
/// This test is one of the two halves that keep the platforms honest:
///
///  - here: Dart drifting from the contract fails;
///  - `web/src/__tests__/canopyTokens.test.ts`: the CSS drifting from the
///    contract (without regenerating) fails.
///
/// Neither can pass by coincidence — they compare different artefacts against
/// the same committed JSON. A Vitest/jsdom test could NOT stand in for the
/// browser check: jsdom does not implement `color-mix`.
void main() {
  final tokens = _loadContract();

  Color colorFor(String mode, String role) {
    final raw =
        (tokens['modes'][mode]['colors'][role] as Map<String, dynamic>)['dart']
            as String;
    return Color(int.parse(raw.substring(2), radix: 16));
  }

  /// Every semantic colour role in the contract, mapped to its Dart field.
  Map<String, Color> rolesOf(CanopyColors c) => {
    'ground': c.ground,
    'surface': c.surface,
    'surface-2': c.surface2,
    'surface-3': c.surface3,
    'ink': c.ink,
    'ink-2': c.ink2,
    'ink-3': c.ink3,
    'primary': c.primary,
    'on-primary': c.onPrimary,
    'secondary': c.secondary,
    'tertiary': c.tertiary,
    'clay': c.clay,
    'on-clay': c.onClay,
    'leaf': c.leaf,
    'berry': c.berry,
    'sky': c.sky,
    'ok': c.ok,
    'warn': c.warn,
    'error': c.error,
    'on-error': c.onError,
    'line': c.line,
    'line-2': c.line2,
  };

  group('Canopy colour parity with web/src/index.css', () {
    for (final (mode, colors) in [
      ('dark', CanopyPalette.dark),
      ('light', CanopyPalette.light),
    ]) {
      test('$mode mode matches every semantic token', () {
        final dart = rolesOf(colors);
        final contract =
            (tokens['modes'][mode]['colors'] as Map<String, dynamic>).keys
                .toSet();

        // A role added to the CSS contract but not mirrored in Dart would
        // otherwise go unnoticed — compare the SETS, not just the values.
        expect(
          dart.keys.toSet(),
          contract,
          reason:
              'Dart and the canonical contract disagree on WHICH roles exist. '
              'Re-run scripts/design/extract_canopy_tokens.mjs and mirror any '
              'new role in CanopyColors.',
        );

        for (final entry in dart.entries) {
          expect(
            entry.value,
            colorFor(mode, entry.key),
            reason:
                '$mode/${entry.key} has drifted from web/src/index.css. '
                'Do not hand-tune Dart: change the CSS, re-run '
                'scripts/design/extract_canopy_tokens.mjs, then update '
                'canopy_palette.dart.',
          );
        }
      });
    }
  });

  group('Canopy scale parity', () {
    test('radius scale matches the canonical --radius-* tokens', () {
      final radius = tokens['radius'] as Map<String, dynamic>;
      expect(AppSpacing.rXs, _px(radius['xs']));
      expect(AppSpacing.rSm, _px(radius['sm']));
      expect(AppSpacing.rMd, _px(radius['md']));
      expect(AppSpacing.rLg, _px(radius['lg']));
      expect(AppSpacing.rXl, _px(radius['xl']));
      expect(AppSpacing.rPill, _px(radius['pill']));
    });

    test('every density matches the canonical density block', () {
      final density = tokens['density'] as Map<String, dynamic>;
      for (final (name, value) in [
        ('cozy', AppDensity.cozy),
        ('comfortable', AppDensity.comfortable),
        ('compact', AppDensity.compact),
      ]) {
        final ext = GreenThumbExtension.fromColors(
          colors: CanopyPalette.dark,
          density: value,
          brightness: Brightness.dark,
        );
        final expected = density[name] as Map<String, dynamic>;
        expect(ext.padCard, _px(expected['padCard']), reason: '$name padCard');
        expect(
          ext.padScreen,
          _px(expected['padScreen']),
          reason: '$name padScreen',
        );
        expect(ext.gapY, _px(expected['gap']), reason: '$name gap');
      }
    });

    test('display type scale matches .gt-display/.gt-h1/.gt-h2/.gt-h3', () {
      final display = tokens['display'] as Map<String, dynamic>;
      for (final (name, style) in [
        ('display', AppTypography.display),
        ('h1', AppTypography.h1),
        ('h2', AppTypography.h2),
        ('h3', AppTypography.h3),
      ]) {
        final spec = display[name] as Map<String, dynamic>;
        final size = _rem(spec['fontSize'] as String);
        expect(style.fontSize, size, reason: '$name font-size');
        expect(style.height, spec['lineHeight'], reason: '$name line-height');
        expect(
          style.fontWeight!.value,
          spec['fontWeight'],
          reason: '$name weight',
        );
        // letter-spacing is authored in em; Flutter wants logical pixels.
        expect(
          style.letterSpacing,
          closeTo(size * _em(spec['letterSpacing'] as String), 0.001),
          reason: '$name letter-spacing',
        );
        // The web headings are ROMAN. Flutter shipped an italic display face
        // that the canonical system never had — this pins the fix.
        expect(
          style.fontStyle ?? FontStyle.normal,
          spec['fontStyle'] == 'italic' ? FontStyle.italic : FontStyle.normal,
          reason: '$name font-style',
        );
      }
    });

    test('body text scale matches the canonical --text-* rungs', () {
      final text = tokens['text'] as Map<String, dynamic>;
      for (final (name, style) in [
        ('micro', AppTypography.micro),
        ('meta', AppTypography.meta),
        ('body-sm', AppTypography.bodySm),
        ('body', AppTypography.body),
        ('body-lg', AppTypography.bodyLg),
        ('lead', AppTypography.lead),
      ]) {
        final spec = text[name] as Map<String, dynamic>;
        expect(style.fontSize, _px(spec['size']), reason: '$name size');
        expect(
          style.height,
          double.parse(spec['lineHeight'] as String),
          reason: '$name line-height',
        );
      }
    });
  });

  group('ColorScheme carries no Material-derived colour', () {
    // Material 3 invents the four `*Container` pairs from the seed when they
    // are not supplied, and those inventions are not Canopy colours — a
    // mauve-pink error banner and lilac avatar discs shipped that way. Every
    // role a screen can reach must trace back to the contract.
    for (final brightness in Brightness.values) {
      test('${brightness.name}: container roles are tinted Canopy accents', () {
        final colors = CanopyPalette.of(brightness);
        final scheme = AppTheme.build(brightness, AppDensity.cozy).colorScheme;

        for (final (name, actual, source, alpha)
            in <(String, Color, Color, double)>[
              (
                'primaryContainer',
                scheme.primaryContainer,
                colors.primary,
                0.20,
              ),
              (
                'secondaryContainer',
                scheme.secondaryContainer,
                colors.secondary,
                0.15,
              ),
              (
                'tertiaryContainer',
                scheme.tertiaryContainer,
                colors.tertiary,
                0.15,
              ),
              ('errorContainer', scheme.errorContainer, colors.error, 0.10),
            ]) {
          expect(
            actual,
            source.withValues(alpha: alpha),
            reason:
                '$name must be the Canopy accent at $alpha, not a '
                'Material-derived colour',
          );
        }

        // The foregrounds are ink — the web writes `text-ink` on every tinted
        // surface rather than a computed "on-container" colour.
        for (final (name, actual) in <(String, Color)>[
          ('onPrimaryContainer', scheme.onPrimaryContainer),
          ('onSecondaryContainer', scheme.onSecondaryContainer),
          ('onTertiaryContainer', scheme.onTertiaryContainer),
          ('onErrorContainer', scheme.onErrorContainer),
        ]) {
          expect(actual, colors.ink, reason: '$name must be the ink token');
        }
      });
    }
  });

  group('Speaker surfaces stay distinguishable', () {
    // The DM bubbles are the one place two surfaces must differ from EACH
    // OTHER, not just from the ground. Routing "mine" through the tinted
    // `primaryContainer` put it 36/765 from surface-3 in dark mode — the two
    // speakers were nearly the same colour, and no colour-token test would
    // have noticed because both tokens were individually correct.
    int distance(Color a, Color b) =>
        (((a.r - b.r).abs() + (a.g - b.g).abs() + (a.b - b.b).abs()) * 255)
            .round();

    for (final brightness in Brightness.values) {
      test('${brightness.name}: own and other bubbles are far apart', () {
        final scheme = AppTheme.build(brightness, AppDensity.cozy).colorScheme;
        expect(
          distance(scheme.secondary, scheme.surfaceContainerHighest),
          greaterThan(200),
          reason: 'the two DM bubble fills must be clearly different',
        );
      });
    }
  });

  group('Canopy defaults parity', () {
    test('Flutter defaults to the same mode and density as the web', () {
      final defaults = tokens['defaults'] as Map<String, dynamic>;
      expect(defaults['mode'], 'dark');
      expect(defaults['density'], 'cozy');
      // The web's ThemeContext seeds mode='dark', density='cozy'; these are the
      // Flutter counterparts, asserted so the two cannot drift apart silently.
      expect(AppTheme.defaultThemeMode, ThemeMode.dark);
      expect(AppTheme.defaultDensity, AppDensity.cozy);
    });
  });
}

double _px(Object? value) =>
    double.parse((value as String).replaceAll('px', ''));
double _rem(String value) => double.parse(value.replaceAll('rem', '')) * 16;
double _em(String value) => double.parse(value.replaceAll('em', ''));

/// Load the canonical contract, failing LOUDLY if it cannot be read.
///
/// A parity test that silently skips when its fixture is missing is worse than
/// no test: it reports green while checking nothing. `flutter test` runs with
/// the package directory as CWD, so the contract sits one level up.
Map<String, dynamic> _loadContract() {
  final file = File('../design/canopy-tokens.json');
  if (!file.existsSync()) {
    throw StateError(
      'Canonical token contract not found at ${file.absolute.path}.\n'
      'It is generated from web/src/index.css — run:\n'
      '    node scripts/design/extract_canopy_tokens.mjs\n'
      'This test MUST NOT be skipped: it is the only thing keeping the Flutter '
      'palette in step with the canonical web design.',
    );
  }
  final decoded = jsonDecode(file.readAsStringSync());
  if (decoded is! Map<String, dynamic> || decoded['modes'] == null) {
    throw StateError(
      'Canonical token contract at ${file.absolute.path} is malformed '
      '(no "modes" key). Re-run scripts/design/extract_canopy_tokens.mjs.',
    );
  }
  return decoded;
}
