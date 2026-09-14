import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/canopy_palette.dart';
import '../../core/theme/green_thumb_extension.dart';

/// The Canopy materials — Flutter counterparts of the web's `.canopy-ground`,
/// `.canopy-card` and `Tile`.
///
/// Canopy's thesis is that "liveliness comes from light, not noise" (spec §1):
/// a raised surface is never a flat fill, it is a gradient lit from the
/// top-left. These widgets are the only correct way to build one — a
/// `Container(color: surface2)` is a flat surface and will read as off-system.

/// The ambient glow behind the whole app (`--gt-grad-ambient`).
///
/// Paints under [child], filling the viewport, pointer-transparent. Dark mode
/// layers two radials (a sage bloom off the top-left, a forest wash at the
/// right); light mode has a single white bloom.
///
/// **Intentional platform difference:** the web drifts this layer on a 70s
/// loop. That is not ported — a continuously repainting full-screen gradient is
/// a real battery cost on a phone, and the design does not depend on the
/// motion. The gradient itself is identical.
///
/// Replaces `GrainOverlay`, which had no web counterpart and once shipped as an
/// opaque sheet over every screen (the grain PNG has no alpha channel).
class CanopyGround extends StatelessWidget {
  const CanopyGround({required this.child, super.key});

  final Widget child;

  /// Geometry per mode, read off `--gt-grad-ambient` in `web/src/index.css`.
  ///
  /// A CSS percentage position maps to a Flutter [Alignment] as `2p - 1`, and
  /// the radius is a fraction of the box's shortest side — the CSS gradients
  /// are ellipses (`90rem 60rem`), so the radius approximates their larger
  /// axis. Light mode is NOT the dark geometry: it is a single, smaller bloom
  /// at a different origin (`70rem 40rem at 15% -20%` vs `90rem 60rem at 18%
  /// -12%`), which is why these are two separate lists rather than one shared
  /// constant with the colours swapped.
  static const _darkLayers = <({Alignment center, double radius, double stop})>[
    // radial-gradient(90rem 60rem at 18% -12%, …)
    (center: Alignment(-0.64, -1.24), radius: 1.5, stop: 0.6),
    // radial-gradient(70rem 50rem at 105% 42%, …)
    (center: Alignment(1.1, -0.16), radius: 1.2, stop: 0.62),
  ];
  static const _lightLayers =
      <({Alignment center, double radius, double stop})>[
        // radial-gradient(70rem 40rem at 15% -20%, …)
        (center: Alignment(-0.7, -1.4), radius: 1.2, stop: 0.6),
      ];

  @override
  Widget build(BuildContext context) {
    final ext = context.canopy;
    final layers = Theme.of(context).brightness == Brightness.dark
        ? _darkLayers
        : _lightLayers;
    return Stack(
      children: [
        Positioned.fill(
          child: IgnorePointer(
            child: RepaintBoundary(
              child: Stack(
                children: [
                  for (var i = 0; i < ext.ambient.length; i++)
                    if (i < layers.length)
                      _AmbientLayer(
                        color: ext.ambient[i],
                        center: layers[i].center,
                        radius: layers[i].radius,
                        stop: layers[i].stop,
                      ),
                ],
              ),
            ),
          ),
        ),
        child,
      ],
    );
  }
}

class _AmbientLayer extends StatelessWidget {
  const _AmbientLayer({
    required this.color,
    required this.center,
    required this.radius,
    required this.stop,
  });

  final Color color;
  final Alignment center;
  final double radius;
  final double stop;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      gradient: RadialGradient(
        center: center,
        radius: radius,
        colors: [color, color.withValues(alpha: 0)],
        stops: [0.0, stop],
      ),
    ),
    child: const SizedBox.expand(),
  );
}

/// A raised Canopy surface: gradient fill + lit sweep + tokenised border.
///
/// The Flutter equivalent of the web's `.canopy-card`. `CardThemeData` cannot
/// express a gradient, so stock `Card` gets a flat mid-surface fallback and
/// this is what real cards should use.
///
/// Set [onTap] for a row/card that navigates: that adds the ink response and
/// the brighter [GreenThumbExtension.line2] border that the web's
/// `.canopy-interactive` applies on hover. Flutter has no hover on touch, so
/// the pressed state carries that job.
class CanopyCard extends StatefulWidget {
  const CanopyCard({
    super.key,
    required this.child,
    this.onTap,
    this.radius = AppSpacing.rMd,
    this.padding,
    this.elevation = 1,
    this.semanticLabel,
    this.accentBorder,
  });

  final Widget child;
  final VoidCallback? onTap;
  final double radius;

  /// Replaces the tokenised hairline with a 1.5px accent, for a card the
  /// design calls out — an accepted solution, a selected option. The web does
  /// this with `border-color: var(--gt-secondary)` on the same surface, so the
  /// gradient fill and sweep stay; only the edge changes.
  final Color? accentBorder;

  /// Defaults to the density's card padding (`ext.padCard`).
  final EdgeInsetsGeometry? padding;

  /// Shadow level 0–3, matching `--gt-shadow-1..3`. 0 paints no shadow.
  final int elevation;

  final String? semanticLabel;

  @override
  State<CanopyCard> createState() => _CanopyCardState();
}

class _CanopyCardState extends State<CanopyCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final ext = context.canopy;
    final shadow = switch (widget.elevation) {
      <= 0 => const <BoxShadow>[],
      1 => ext.shadow1,
      2 => ext.shadow2,
      _ => ext.shadow3,
    };
    final radius = BorderRadius.circular(widget.radius);

    Widget content = Padding(
      padding: widget.padding ?? EdgeInsets.all(ext.padCard),
      child: widget.child,
    );

    if (widget.onTap != null) {
      content = Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: widget.onTap,
          onHighlightChanged: (v) => setState(() => _pressed = v),
          borderRadius: radius,
          // The app-wide focus accent — the web rings everything in secondary.
          focusColor: ext.sweep,
          splashColor: ext.leaf.withValues(alpha: 0.10),
          highlightColor: ext.leaf.withValues(alpha: 0.06),
          child: content,
        ),
      );
    }

    return Semantics(
      label: widget.semanticLabel,
      button: widget.onTap != null,
      child: DecoratedBox(
        decoration: ext.cardDecoration(
          radius: widget.radius,
          borderColor: widget.accentBorder ?? (_pressed ? ext.line2 : ext.line),
          borderWidth: widget.accentBorder != null ? 1.5 : 1.0,
          shadow: shadow,
        ),
        // The sweep is a SECOND layer: a BoxDecoration takes one gradient, and
        // the card needs the linear fill with the radial highlight over it.
        child: DecoratedBox(
          decoration: ext.cardSweepDecoration(radius: widget.radius),
          child: ClipRRect(borderRadius: radius, child: content),
        ),
      ),
    );
  }
}

/// An accent icon tile (`--gt-tile-*`) — the web's `Tile` primitive.
///
/// A small gradient square behind an icon, used to give a row or stat a
/// colour identity. The foreground is always the dark abyss ink: every tile
/// gradient is light in both modes.
class CanopyTile extends StatelessWidget {
  const CanopyTile({
    super.key,
    required this.icon,
    this.tone = CanopyTileTone.sage,
    this.size = CanopyTileSize.md,
  });

  final IconData icon;
  final CanopyTileTone tone;
  final CanopyTileSize size;

  @override
  Widget build(BuildContext context) {
    final (box, radius, iconSize) = switch (size) {
      CanopyTileSize.sm => (36.0, AppSpacing.rTileSm, AppSpacing.iconSM),
      CanopyTileSize.md => (46.0, AppSpacing.rTileMd, AppSpacing.iconLG),
    };
    return Container(
      width: box,
      height: box,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: tone.colors,
        ),
        borderRadius: BorderRadius.circular(radius),
      ),
      child: Icon(icon, size: iconSize, color: CanopyRamp.abyss),
    );
  }
}

/// Tile box sizes, mirroring the web's `TILE_BOX` (36px / 46px).
enum CanopyTileSize { sm, md }
