import 'dart:ui';
import 'package:flutter/material.dart';
import 'app_palettes.dart';

enum AppDensity { comfortable, cozy, compact }

class GreenThumbExtension extends ThemeExtension<GreenThumbExtension> {
  const GreenThumbExtension({
    required this.clay,
    required this.onClay,
    required this.berry,
    required this.sky,
    required this.leaf,
    required this.ink2,
    required this.ink3,
    required this.statusOk,
    required this.statusWarn,
    required this.shadow1,
    required this.shadow2,
    required this.shadow3,
    required this.padCard,
    required this.padScreen,
    required this.gapY,
    required this.showGrain,
  });

  final Color clay, onClay, berry, sky, leaf;
  final Color ink2, ink3;
  final Color statusOk, statusWarn;
  final List<BoxShadow> shadow1, shadow2, shadow3;
  final double padCard, padScreen, gapY;
  final bool showGrain;

  factory GreenThumbExtension.fromColors({
    required GreenThumbColors colors,
    required AppDensity density,
    required Brightness brightness,
  }) {
    final (padCard, padScreen, gapY) = switch (density) {
      AppDensity.comfortable => (18.0, 18.0, 14.0),
      AppDensity.cozy => (16.0, 16.0, 12.0),
      AppDensity.compact => (12.0, 14.0, 10.0),
    };

    final shadowColor = brightness == Brightness.light
        ? const Color(0xFF1B2218)
        : Colors.black;

    return GreenThumbExtension(
      clay: colors.clay,
      onClay: colors.onClay,
      berry: colors.berry,
      sky: colors.sky,
      leaf: colors.leaf,
      ink2: colors.ink2,
      ink3: colors.ink3,
      statusOk: colors.ok,
      statusWarn: colors.warn,
      shadow1: [
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.04),
          offset: const Offset(0, 1),
          blurRadius: 0,
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.05),
          offset: const Offset(0, 2),
          blurRadius: 6,
        ),
      ],
      shadow2: [
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.05),
          offset: const Offset(0, 2),
          blurRadius: 0,
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.08),
          offset: const Offset(0, 8),
          blurRadius: 22,
        ),
      ],
      shadow3: [
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.06),
          offset: const Offset(0, 4),
          blurRadius: 0,
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.14),
          offset: const Offset(0, 18),
          blurRadius: 40,
        ),
      ],
      padCard: padCard,
      padScreen: padScreen,
      gapY: gapY,
      showGrain: true,
    );
  }

  static GreenThumbExtension get fallback {
    return const GreenThumbExtension(
      clay: Color(0xFF5C6B58),
      onClay: Color(0xFFE8F0E5),
      berry: Color(0xFFB85C5C),
      sky: Color(0xFF6B8FA8),
      leaf: Color(0xFF7BA05B),
      ink2: Color(0xFF6B7D6B),
      ink3: Color(0xFF9EAA9E),
      statusOk: Color(0xFF4A8C4A),
      statusWarn: Color(0xFFCC8C3C),
      shadow1: [
        BoxShadow(
          color: Color(0x0A1B2218),
          offset: Offset(0, 1),
          blurRadius: 0,
        ),
        BoxShadow(
          color: Color(0x0D1B2218),
          offset: Offset(0, 2),
          blurRadius: 6,
        ),
      ],
      shadow2: [
        BoxShadow(
          color: Color(0x0D1B2218),
          offset: Offset(0, 2),
          blurRadius: 0,
        ),
        BoxShadow(
          color: Color(0x141B2218),
          offset: Offset(0, 8),
          blurRadius: 22,
        ),
      ],
      shadow3: [
        BoxShadow(
          color: Color(0x0F1B2218),
          offset: Offset(0, 4),
          blurRadius: 0,
        ),
        BoxShadow(
          color: Color(0x241B2218),
          offset: Offset(0, 18),
          blurRadius: 40,
        ),
      ],
      padCard: 18,
      padScreen: 18,
      gapY: 14,
      showGrain: false,
    );
  }

  @override
  GreenThumbExtension copyWith({
    Color? clay,
    Color? onClay,
    Color? berry,
    Color? sky,
    Color? leaf,
    Color? ink2,
    Color? ink3,
    Color? statusOk,
    Color? statusWarn,
    List<BoxShadow>? shadow1,
    List<BoxShadow>? shadow2,
    List<BoxShadow>? shadow3,
    double? padCard,
    double? padScreen,
    double? gapY,
    bool? showGrain,
  }) {
    return GreenThumbExtension(
      clay: clay ?? this.clay,
      onClay: onClay ?? this.onClay,
      berry: berry ?? this.berry,
      sky: sky ?? this.sky,
      leaf: leaf ?? this.leaf,
      ink2: ink2 ?? this.ink2,
      ink3: ink3 ?? this.ink3,
      statusOk: statusOk ?? this.statusOk,
      statusWarn: statusWarn ?? this.statusWarn,
      shadow1: shadow1 ?? this.shadow1,
      shadow2: shadow2 ?? this.shadow2,
      shadow3: shadow3 ?? this.shadow3,
      padCard: padCard ?? this.padCard,
      padScreen: padScreen ?? this.padScreen,
      gapY: gapY ?? this.gapY,
      showGrain: showGrain ?? this.showGrain,
    );
  }

  @override
  GreenThumbExtension lerp(GreenThumbExtension? other, double t) {
    if (other == null) return this;
    return GreenThumbExtension(
      clay: Color.lerp(clay, other.clay, t)!,
      onClay: Color.lerp(onClay, other.onClay, t)!,
      berry: Color.lerp(berry, other.berry, t)!,
      sky: Color.lerp(sky, other.sky, t)!,
      leaf: Color.lerp(leaf, other.leaf, t)!,
      ink2: Color.lerp(ink2, other.ink2, t)!,
      ink3: Color.lerp(ink3, other.ink3, t)!,
      statusOk: Color.lerp(statusOk, other.statusOk, t)!,
      statusWarn: Color.lerp(statusWarn, other.statusWarn, t)!,
      shadow1: BoxShadow.lerpList(shadow1, other.shadow1, t)!,
      shadow2: BoxShadow.lerpList(shadow2, other.shadow2, t)!,
      shadow3: BoxShadow.lerpList(shadow3, other.shadow3, t)!,
      padCard: lerpDouble(padCard, other.padCard, t)!,
      padScreen: lerpDouble(padScreen, other.padScreen, t)!,
      gapY: lerpDouble(gapY, other.gapY, t)!,
      showGrain: t < 0.5 ? showGrain : other.showGrain,
    );
  }
}
