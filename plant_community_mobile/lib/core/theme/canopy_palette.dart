import 'package:flutter/material.dart';

/// Canopy — the cross-platform design language, Flutter side.
///
/// ## Where these numbers come from
///
/// Every value here is the RESOLVED form of a token in `web/src/index.css`,
/// which is the canonical reference (see
/// `docs/superpowers/specs/2026-08-13-canopy-design.md`). About a third of the
/// canonical values are authored as `color-mix(in oklab, …)` and so exist as a
/// literal nowhere — the browser computes them. Flutter cannot express an oklab
/// blend (`Color.lerp` interpolates in sRGB and gives a visibly different
/// colour), so those are resolved ahead of time by
/// `scripts/design/extract_canopy_tokens.mjs` into `design/canopy-tokens.json`.
///
/// **Do not hand-tune a colour here.** Change `web/src/index.css`, re-run the
/// generator, and update this file to match. `canopy_parity_test.dart` compares
/// every field below against that JSON and fails on any drift, in either
/// direction. The generator's own maths is pinned to what Chromium actually
/// paints by `scripts/design/verify_canopy_tokens_in_browser.mjs`.
///
/// ## Why a single palette
///
/// The four palettes this replaced (Loam / Garden / Forest / Heritage) were a
/// Flutter-only invention. The design spec §2 retired the palette switcher for
/// "one identity"; the web has shipped exactly one palette since. See
/// `AppPaletteChoice`'s removal and the migration in `palette_notifier.dart`.
class CanopyColors {
  const CanopyColors({
    required this.ground,
    required this.surface,
    required this.surface2,
    required this.surface3,
    required this.ink,
    required this.ink2,
    required this.ink3,
    required this.line,
    required this.line2,
    required this.primary,
    required this.onPrimary,
    required this.secondary,
    required this.tertiary,
    required this.clay,
    required this.onClay,
    required this.leaf,
    required this.berry,
    required this.sky,
    required this.ok,
    required this.warn,
    required this.error,
    required this.onError,
    required this.gradCard,
    required this.gradCardStops,
    required this.gradCta,
    required this.sweep,
    required this.ambient,
    required this.shadowColor,
    required this.shadowAlphas,
  });

  /// Page ground — behind everything. `--gt-ground` → `scaffoldBackgroundColor`.
  final Color ground;

  /// App-frame canvas. `--gt-surface` → `ColorScheme.surface`.
  final Color surface;

  /// Raised surface. `--gt-surface-2` → `ColorScheme.surfaceContainerLow`.
  final Color surface2;

  /// Highest surface / hover fill. `--gt-surface-3` → `surfaceContainerHigh`.
  final Color surface3;

  /// Primary, secondary and muted ink.
  final Color ink, ink2, ink3;

  /// Hairline and emphasised borders. Both carry alpha — they are designed to
  /// sit OVER a surface, so never use them as an opaque fill.
  final Color line, line2;

  /// CTA fill and its foreground. Dark mode: mint on abyss (NOT a green button).
  final Color primary, onPrimary;

  /// Soft accent ink; also the app-wide focus ring colour.
  final Color secondary;

  /// Warm accent. `clay` is the same hue but carries its own foreground.
  final Color tertiary, clay, onClay;

  /// Small-element accents: sage, bloom (coral) and orchid.
  final Color leaf, berry, sky;

  /// Status roles. `error` pairs with [onError].
  final Color ok, warn, error, onError;

  /// `--gt-grad-card`: the material every raised surface is filled with.
  /// Three stops on a 150° axis, placed at [gradCardStops].
  final List<Color> gradCard;
  final List<double> gradCardStops;

  /// `--gt-grad-cta`: two stops on a 135° axis, the primary button fill.
  final List<Color> gradCta;

  /// `--gt-grad-sweep`: the lit highlight laid over every card, a radial from
  /// the top-left fading to transparent. Already carries its alpha.
  final Color sweep;

  /// `--gt-grad-ambient`: the slow canopy glow behind the whole app. Dark mode
  /// has two overlapping radials, light mode one.
  final List<Color> ambient;

  /// Shadow colour and the per-level alpha pairs `[[tight, spread], …]` for
  /// shadow levels 1–3. Dark mode's shadows are roughly twice the opacity of
  /// light mode's — a shadow has to work against a near-black ground.
  final Color shadowColor;
  final List<List<double>> shadowAlphas;
}

/// The ten named Canopy hues (`--canopy-*`, spec §3.1). Semantic roles below
/// are built from these; prefer a role over a raw hue in UI code.
abstract final class CanopyRamp {
  static const abyss = Color(0xFF051F20);
  static const pine = Color(0xFF0B2B26);
  static const moss = Color(0xFF163832);
  static const forest = Color(0xFF235347);
  static const sage = Color(0xFF8EB69B);
  static const mint = Color(0xFFDAF1DE);
  static const pollen = Color(0xFFE7B75F);
  static const bloom = Color(0xFFE88E76);
  static const orchid = Color(0xFFB7A5E0);
  static const red = Color(0xFFDE6B5A);
}

/// Accent tile gradients (`--gt-tile-*`), used by icon tiles and progress fills.
enum CanopyTileTone {
  sage([Color(0xFFDAF1DE), Color(0xFF8EB69B)]),
  pollen([Color(0xFFF2D28F), Color(0xFFE7B75F)]),
  bloom([Color(0xFFF5B3A0), Color(0xFFE88E76)]),
  orchid([Color(0xFFD3C7EE), Color(0xFFB7A5E0)]);

  const CanopyTileTone(this.colors);

  /// Light→base pair, painted on a 135° axis.
  final List<Color> colors;
}

abstract final class CanopyPalette {
  /// Dark is the DEFAULT and the design's identity — light is derived from the
  /// same ramp, not inverted (spec §3.4).
  static const CanopyColors dark = CanopyColors(
    ground: Color(0xFF051F20),
    surface: Color(0xFF0B2B26),
    surface2: Color(0xFF163832),
    // color-mix(in oklab, moss 55%, forest)
    surface3: Color(0xFF1C443B),
    ink: Color(0xFFDAF1DE),
    // color-mix(in oklab, sage 85%, mint)
    ink2: Color(0xFF99BFA5),
    // color-mix(in oklab, sage 65%, forest)
    ink3: Color(0xFF68927C),
    // forest at 45% / 75% alpha — a color-mix with `transparent` mixes
    // premultiplied, so the hue is unchanged and only alpha moves.
    line: Color(0x73235347),
    line2: Color(0xBF235347),
    primary: Color(0xFFDAF1DE),
    onPrimary: Color(0xFF051F20),
    secondary: Color(0xFF8EB69B),
    tertiary: Color(0xFFE7B75F),
    clay: Color(0xFFE7B75F),
    onClay: Color(0xFF051F20),
    leaf: Color(0xFF8EB69B),
    berry: Color(0xFFE88E76),
    sky: Color(0xFFB7A5E0),
    ok: Color(0xFF8EB69B),
    warn: Color(0xFFE7B75F),
    error: Color(0xFFDE6B5A),
    onError: Color(0xFF051F20),
    gradCard: [Color(0xFF183B34), Color(0xFF163832), Color(0xFF143530)],
    gradCardStops: [0.0, 0.46, 1.0],
    gradCta: [Color(0xFFDAF1DE), Color(0xFFA4C7AF)],
    sweep: Color(0x17DAF1DE),
    ambient: [Color(0x298EB69B), Color(0x57235347)],
    shadowColor: Color(0xFF000000),
    shadowAlphas: [
      [0.10, 0.18],
      [0.12, 0.26],
      [0.14, 0.38],
    ],
  );

  static const CanopyColors light = CanopyColors(
    ground: Color(0xFFCDE9D4),
    surface: Color(0xFFDAF1DE),
    surface2: Color(0xFFF2FAF4),
    surface3: Color(0xFFE9F5EC),
    ink: Color(0xFF0B2B26),
    ink2: Color(0xFF35594B),
    ink3: Color(0xFF5E8271),
    // sage at 38% / 62% alpha
    line: Color(0x618EB69B),
    line2: Color(0x9E8EB69B),
    primary: Color(0xFF235347),
    onPrimary: Color(0xFFDAF1DE),
    // color-mix(in oklab, forest 60%, sage)
    secondary: Color(0xFF4D7967),
    // Accents are DARKENED for light surfaces so they keep AA contrast; clay
    // and error therefore flip their foregrounds to a light ink.
    tertiary: Color(0xFF8A6011),
    clay: Color(0xFF8A6011),
    onClay: Color(0xFFF2FAF4),
    leaf: Color(0xFF3C6B50),
    berry: Color(0xFFB0503A),
    sky: Color(0xFF6B4FA0),
    ok: Color(0xFF2F6B46),
    warn: Color(0xFF8A6011),
    error: Color(0xFFA63C2A),
    onError: Color(0xFFF2FAF4),
    gradCard: [Color(0xFFFDFFFD), Color(0xFFF2FAF4), Color(0xFFE9F5EC)],
    gradCardStops: [0.0, 0.55, 1.0],
    gradCta: [Color(0xFF163832), Color(0xFF235347)],
    sweep: Color(0xD9FFFFFF),
    ambient: [Color(0xBFFFFFFF)],
    shadowColor: CanopyRamp.pine,
    shadowAlphas: [
      [0.05, 0.08],
      [0.06, 0.12],
      [0.07, 0.18],
    ],
  );

  static CanopyColors of(Brightness brightness) =>
      brightness == Brightness.dark ? dark : light;
}
