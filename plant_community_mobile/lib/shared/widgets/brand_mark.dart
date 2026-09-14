import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../core/constants/app_brand.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/canopy_palette.dart';
import '../../core/theme/green_thumb_extension.dart';

/// The Houseplant MD mark — "Leaf, badged" (design spec §2.1).
///
/// A mint→sage leaf on a deep-pine rounded tile, with a coral badge carrying a
/// mint cross at the bottom-right. This is a faithful port of the web's
/// `BrandMark.tsx`, and needs no SVG dependency: the web mark's leaf path IS
/// Lucide's `leaf` glyph, which the app already bundles.
///
/// **Legal constraint (binding).** The red Greek cross on white is a
/// Geneva-Conventions-protected emblem and is enforced against apps. The cross
/// here is Canopy's clinic coral on green, and must NEVER be rendered as a red
/// cross on a white or light ground. Do not "simplify" the badge onto a light
/// background.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 34});

  final double size;

  // Ratios taken from the 64×64 web viewBox so the mark scales exactly.
  static const _tileRadiusRatio = 18 / 64;
  static const _badgeRatio = 23 / 64; // diameter (r=11.5)
  static const _crossLongRatio = 12.4 / 64;
  static const _crossShortRatio = 4.4 / 64;

  @override
  Widget build(BuildContext context) {
    final badge = size * _badgeRatio;
    return Semantics(
      label: AppBrand.name,
      image: true,
      excludeSemantics: true,
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(
          children: [
            // Deep-pine tile.
            Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  // Brand-asset literals, taken verbatim from the web
                  // mark's SVG. Deliberately NOT semantic tokens: the
                  // logo tile must look identical in both modes.
                  colors: [Color(0xFF10362F), CanopyRamp.pine],
                ),
                borderRadius: BorderRadius.circular(size * _tileRadiusRatio),
              ),
            ),
            // Leaf, stroked in the mint→sage gradient.
            Positioned(
              left: size * 0.12,
              top: size * 0.09,
              child: ShaderMask(
                shaderCallback: (bounds) => const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [CanopyRamp.mint, CanopyRamp.sage],
                ).createShader(bounds),
                child: Icon(
                  LucideIcons.leaf,
                  size: size * 0.68,
                  color: Colors.white, // replaced by the shader
                ),
              ),
            ),
            // Clinic badge: coral disc + mint cross.
            Positioned(
              right: size * 0.055,
              bottom: size * 0.055,
              child: SizedBox(
                width: badge,
                height: badge,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    DecoratedBox(
                      decoration: const BoxDecoration(
                        color: CanopyRamp.red,
                        shape: BoxShape.circle,
                      ),
                      child: SizedBox(width: badge, height: badge),
                    ),
                    _CrossBar(
                      width: size * _crossShortRatio,
                      height: size * _crossLongRatio,
                    ),
                    _CrossBar(
                      width: size * _crossLongRatio,
                      height: size * _crossShortRatio,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CrossBar extends StatelessWidget {
  const _CrossBar({required this.width, required this.height});

  final double width;
  final double height;

  @override
  Widget build(BuildContext context) => Container(
    width: width,
    height: height,
    decoration: BoxDecoration(
      color: CanopyRamp.mint,
      borderRadius: BorderRadius.circular(
        (width < height ? width : height) / 2,
      ),
    ),
  );
}

/// The mark plus the product name — the brand block used on splash, auth and
/// the home header. Keeps the lockup identical everywhere instead of each
/// screen pairing its own icon and label.
class BrandLockup extends StatelessWidget {
  const BrandLockup({
    super.key,
    this.markSize = 34,
    this.showTagline = false,
    this.axis = Axis.horizontal,
  });

  final double markSize;
  final bool showTagline;
  final Axis axis;

  @override
  Widget build(BuildContext context) {
    final ext = context.canopy;
    final name = Text(
      AppBrand.name,
      style: AppTypography.h3.copyWith(
        color: Theme.of(context).colorScheme.onSurface,
      ),
    );
    final tagline = Text(
      AppBrand.tagline,
      style: AppTypography.meta.copyWith(color: ext.ink3),
    );

    if (axis == Axis.vertical) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          BrandMark(size: markSize),
          const SizedBox(height: 12),
          name,
          if (showTagline) ...[const SizedBox(height: 4), tagline],
        ],
      );
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        BrandMark(size: markSize),
        const SizedBox(width: 10),
        // Flexible, not a bare Column: at 320pt (iPhone SE) the name and
        // tagline overflow the hero card's content width otherwise.
        Flexible(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [name, if (showTagline) tagline],
          ),
        ),
      ],
    );
  }
}
