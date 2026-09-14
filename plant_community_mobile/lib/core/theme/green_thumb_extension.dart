import 'dart:ui';
import 'package:flutter/material.dart';
import '../constants/app_spacing.dart';
import 'canopy_palette.dart';

/// Layout density. Mirrors the web's `[data-density]` blocks; `cozy` is the
/// default on both platforms.
enum AppDensity { comfortable, cozy, compact }

/// The Canopy tokens that `ColorScheme` has no slot for — plus the gradient
/// materials and density-dependent spacing.
///
/// `ColorScheme` carries the roles Material understands (surface, primary,
/// error…); everything Canopy-specific lives here: the second and third ink
/// rungs, the accent set, the tokenised borders, the three shadow levels and
/// the gradient materials that make a Canopy surface look lit rather than flat.
///
/// Read it with `Theme.of(context).extension<GreenThumbExtension>()`, falling
/// back to [fallback] — several widget tests pump a bare `ThemeData`.
///
/// (The name is legacy: "Green Thumb" was this app's previous design system.
/// The values are Canopy. Renaming the class touches 21 files for no visual
/// change, so it is deliberately left for a separate mechanical pass.)
class GreenThumbExtension extends ThemeExtension<GreenThumbExtension> {
  const GreenThumbExtension({
    required this.ground,
    required this.surface2,
    required this.surface3,
    required this.ink2,
    required this.ink3,
    required this.line,
    required this.line2,
    required this.clay,
    required this.onClay,
    required this.berry,
    required this.sky,
    required this.leaf,
    required this.statusOk,
    required this.statusWarn,
    required this.gradCard,
    required this.gradCardStops,
    required this.gradCta,
    required this.sweep,
    required this.ambient,
    required this.shadow1,
    required this.shadow2,
    required this.shadow3,
    required this.padCard,
    required this.padScreen,
    required this.gapY,
  });

  /// Page ground — behind the whole app, under every surface.
  final Color ground;

  /// Raised and highest surfaces (`--gt-surface-2` / `--gt-surface-3`).
  final Color surface2, surface3;

  /// Secondary and muted ink.
  final Color ink2, ink3;

  /// Tokenised borders. Both carry alpha and are meant to sit over a surface.
  final Color line, line2;

  /// Warm accent with its own foreground.
  final Color clay, onClay;

  /// Small-element accents.
  final Color berry, sky, leaf;

  /// Status accents. `error` stays on `ColorScheme.error`.
  final Color statusOk, statusWarn;

  /// `--gt-grad-card` — three stops on a 150° axis at [gradCardStops].
  final List<Color> gradCard;
  final List<double> gradCardStops;

  /// `--gt-grad-cta` — two stops on a 135° axis.
  final List<Color> gradCta;

  /// `--gt-grad-sweep` — the lit highlight over each card (carries its alpha).
  final Color sweep;

  /// `--gt-grad-ambient` — the glow behind the app; 2 radials dark, 1 light.
  final List<Color> ambient;

  /// The three shadow levels.
  final List<BoxShadow> shadow1, shadow2, shadow3;

  /// Density-dependent spacing.
  final double padCard, padScreen, gapY;

  /// On-colour for the [leaf] badge background. `leaf` is a light green in dark
  /// mode, so its foreground must be a fixed dark ink — using `onSurface`
  /// renders light-on-light there (audit L7).
  static const Color onLeaf = CanopyRamp.abyss;

  /// `linear-gradient(150deg, …)` — the material every raised surface uses.
  ///
  /// CSS angles are measured clockwise from "to top", so 150° points down and
  /// to the right: direction `(sin150, -cos150)` = `(0.5, 0.866)` in screen
  /// coordinates. Flutter's `Alignment` axis is that vector mirrored about the
  /// box centre. Like CSS, the visual angle skews on a non-square box.
  LinearGradient get cardGradient => LinearGradient(
    begin: const Alignment(-0.5, -0.866),
    end: const Alignment(0.5, 0.866),
    colors: gradCard,
    stops: gradCardStops,
  );

  /// `linear-gradient(135deg, …)` — the primary CTA fill. 135° is exactly
  /// top-left → bottom-right.
  LinearGradient get ctaGradient => LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: gradCta,
  );

  /// `radial-gradient(120% 90% at 12% -10%, …)` — the sweep laid over a card.
  /// The centre sits just off the top-left corner, so the highlight reads as
  /// light falling on the surface rather than a glow inside it.
  RadialGradient get sweepGradient => RadialGradient(
    center: const Alignment(-0.76, -1.2),
    radius: 1.2,
    colors: [sweep, sweep.withValues(alpha: 0)],
    stops: const [0.0, 0.55],
  );

  /// The complete Canopy card material: gradient fill, lit sweep, hairline
  /// border. This is the Flutter equivalent of the web's `.canopy-card`.
  ///
  /// `Container` takes a single `decoration`, so the sweep is applied by
  /// [cardSweepDecoration] in a stacked child rather than a second background
  /// layer — see `CanopyCard`.
  BoxDecoration cardDecoration({
    double radius = AppSpacing.rMd,
    Color? borderColor,
    double borderWidth = 1.0,
    List<BoxShadow>? shadow,
  }) => BoxDecoration(
    gradient: cardGradient,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: borderColor ?? line, width: borderWidth),
    boxShadow: shadow,
  );

  /// The sweep highlight, to be painted over [cardDecoration].
  BoxDecoration cardSweepDecoration({double radius = AppSpacing.rMd}) =>
      BoxDecoration(
        gradient: sweepGradient,
        borderRadius: BorderRadius.circular(radius),
      );

  factory GreenThumbExtension.fromColors({
    required CanopyColors colors,
    required AppDensity density,
    required Brightness brightness,
  }) {
    // Mirrors the web's `[data-density]` blocks exactly; pinned by
    // canopy_parity_test.dart.
    final (padCard, padScreen, gapY) = switch (density) {
      AppDensity.comfortable => (18.0, 18.0, 14.0),
      AppDensity.cozy => (16.0, 16.0, 12.0),
      AppDensity.compact => (12.0, 14.0, 10.0),
    };

    /// The web's shadows are two layers: a tight 0-blur lip and a soft spread.
    /// Dark mode's are roughly twice the opacity of light mode's — a shadow has
    /// to work against a near-black ground. Previously Flutter used light
    /// mode's alphas in BOTH modes, so dark-mode elevation was invisible.
    List<BoxShadow> level(
      int i,
      double tightOffset,
      double spreadOffset,
      double blur,
    ) {
      final [tight, spread] = colors.shadowAlphas[i];
      return [
        BoxShadow(
          color: colors.shadowColor.withValues(alpha: tight),
          offset: Offset(0, tightOffset),
          blurRadius: 0,
        ),
        BoxShadow(
          color: colors.shadowColor.withValues(alpha: spread),
          offset: Offset(0, spreadOffset),
          blurRadius: blur,
        ),
      ];
    }

    return GreenThumbExtension(
      ground: colors.ground,
      surface2: colors.surface2,
      surface3: colors.surface3,
      ink2: colors.ink2,
      ink3: colors.ink3,
      line: colors.line,
      line2: colors.line2,
      clay: colors.clay,
      onClay: colors.onClay,
      berry: colors.berry,
      sky: colors.sky,
      leaf: colors.leaf,
      statusOk: colors.ok,
      statusWarn: colors.warn,
      gradCard: colors.gradCard,
      gradCardStops: colors.gradCardStops,
      gradCta: colors.gradCta,
      sweep: colors.sweep,
      ambient: colors.ambient,
      shadow1: level(0, 1, 2, 6),
      shadow2: level(1, 2, 8, 22),
      shadow3: level(2, 4, 18, 40),
      padCard: padCard,
      padScreen: padScreen,
      gapY: gapY,
    );
  }

  /// Used when a widget renders outside a themed tree (several widget tests
  /// pump a bare `ThemeData`). Dark Canopy at cozy density — the app defaults —
  /// so a test that forgets the theme still sees real design-system values
  /// rather than a stand-in palette that hides colour bugs.
  static final GreenThumbExtension fallback = GreenThumbExtension.fromColors(
    colors: CanopyPalette.dark,
    density: AppDensity.cozy,
    brightness: Brightness.dark,
  );

  @override
  GreenThumbExtension copyWith({
    Color? ground,
    Color? surface2,
    Color? surface3,
    Color? ink2,
    Color? ink3,
    Color? line,
    Color? line2,
    Color? clay,
    Color? onClay,
    Color? berry,
    Color? sky,
    Color? leaf,
    Color? statusOk,
    Color? statusWarn,
    List<Color>? gradCard,
    List<double>? gradCardStops,
    List<Color>? gradCta,
    Color? sweep,
    List<Color>? ambient,
    List<BoxShadow>? shadow1,
    List<BoxShadow>? shadow2,
    List<BoxShadow>? shadow3,
    double? padCard,
    double? padScreen,
    double? gapY,
  }) {
    return GreenThumbExtension(
      ground: ground ?? this.ground,
      surface2: surface2 ?? this.surface2,
      surface3: surface3 ?? this.surface3,
      ink2: ink2 ?? this.ink2,
      ink3: ink3 ?? this.ink3,
      line: line ?? this.line,
      line2: line2 ?? this.line2,
      clay: clay ?? this.clay,
      onClay: onClay ?? this.onClay,
      berry: berry ?? this.berry,
      sky: sky ?? this.sky,
      leaf: leaf ?? this.leaf,
      statusOk: statusOk ?? this.statusOk,
      statusWarn: statusWarn ?? this.statusWarn,
      gradCard: gradCard ?? this.gradCard,
      gradCardStops: gradCardStops ?? this.gradCardStops,
      gradCta: gradCta ?? this.gradCta,
      sweep: sweep ?? this.sweep,
      ambient: ambient ?? this.ambient,
      shadow1: shadow1 ?? this.shadow1,
      shadow2: shadow2 ?? this.shadow2,
      shadow3: shadow3 ?? this.shadow3,
      padCard: padCard ?? this.padCard,
      padScreen: padScreen ?? this.padScreen,
      gapY: gapY ?? this.gapY,
    );
  }

  @override
  GreenThumbExtension lerp(GreenThumbExtension? other, double t) {
    if (other == null) return this;
    List<Color> lerpColors(List<Color> a, List<Color> b) => a.length == b.length
        ? [for (var i = 0; i < a.length; i++) Color.lerp(a[i], b[i], t)!]
        : (t < 0.5 ? a : b);
    return GreenThumbExtension(
      ground: Color.lerp(ground, other.ground, t)!,
      surface2: Color.lerp(surface2, other.surface2, t)!,
      surface3: Color.lerp(surface3, other.surface3, t)!,
      ink2: Color.lerp(ink2, other.ink2, t)!,
      ink3: Color.lerp(ink3, other.ink3, t)!,
      line: Color.lerp(line, other.line, t)!,
      line2: Color.lerp(line2, other.line2, t)!,
      clay: Color.lerp(clay, other.clay, t)!,
      onClay: Color.lerp(onClay, other.onClay, t)!,
      berry: Color.lerp(berry, other.berry, t)!,
      sky: Color.lerp(sky, other.sky, t)!,
      leaf: Color.lerp(leaf, other.leaf, t)!,
      statusOk: Color.lerp(statusOk, other.statusOk, t)!,
      statusWarn: Color.lerp(statusWarn, other.statusWarn, t)!,
      gradCard: lerpColors(gradCard, other.gradCard),
      gradCardStops: t < 0.5 ? gradCardStops : other.gradCardStops,
      gradCta: lerpColors(gradCta, other.gradCta),
      sweep: Color.lerp(sweep, other.sweep, t)!,
      ambient: lerpColors(ambient, other.ambient),
      shadow1: BoxShadow.lerpList(shadow1, other.shadow1, t)!,
      shadow2: BoxShadow.lerpList(shadow2, other.shadow2, t)!,
      shadow3: BoxShadow.lerpList(shadow3, other.shadow3, t)!,
      padCard: lerpDouble(padCard, other.padCard, t)!,
      padScreen: lerpDouble(padScreen, other.padScreen, t)!,
      gapY: lerpDouble(gapY, other.gapY, t)!,
    );
  }
}

/// Terse access to the Canopy tokens: `context.canopy.ink2`.
extension CanopyThemeAccess on BuildContext {
  GreenThumbExtension get canopy =>
      Theme.of(this).extension<GreenThumbExtension>() ??
      GreenThumbExtension.fallback;
}
