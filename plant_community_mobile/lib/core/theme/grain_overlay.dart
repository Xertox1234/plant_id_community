import 'package:flutter/material.dart';
import 'green_thumb_extension.dart';

/// Paints a subtle film-grain texture over [child].
///
/// The overlay MUST be translucent. `assets/images/grain.png` is an 8-bit
/// grayscale PNG with **no alpha channel** (colour type 0, no `tRNS`), so every
/// pixel is fully opaque. Painting it `Positioned.fill` over the child hides the
/// page completely.
///
/// The previous implementation tried to soften it with
/// `color: Colors.black.withValues(alpha: 0.35)` + `colorBlendMode:
/// BlendMode.multiply`, which does not do that: `Image.color`/`colorBlendMode`
/// blend the tint into the image's **own pixels** before it is composited. They
/// never blend the image with what is underneath, and multiply against an opaque
/// source leaves alpha at 1.0 — so the result was still a solid sheet, just
/// darker. Shipped that way, every screen using this widget rendered as
/// full-screen static with only the `Scaffold.floatingActionButton` visible,
/// because the FAB is drawn outside `body`.
///
/// Widget tests never caught it: they resolve `GreenThumbExtension.fallback`,
/// which sets `showGrain: false`.
class GrainOverlay extends StatelessWidget {
  const GrainOverlay({required this.child, super.key});

  /// Film grain is a texture, not a scrim. Keep this low single digits.
  static const double grainOpacity = 0.05;

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<GreenThumbExtension>();
    if (ext == null || !ext.showGrain) return child;

    return Stack(
      children: [
        child,
        Positioned.fill(
          child: IgnorePointer(
            // Opacity applies to the composited layer, which is the part the
            // image's missing alpha channel cannot express.
            child: Opacity(
              opacity: grainOpacity,
              child: Image.asset(
                'assets/images/grain.png',
                // Tile at native size. BoxFit.cover stretched one 256px tile
                // across the whole screen, which is not what grain is.
                repeat: ImageRepeat.repeat,
                fit: BoxFit.none,
                alignment: Alignment.topLeft,
                filterQuality: FilterQuality.none,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
