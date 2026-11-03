import 'package:flutter/material.dart';
import 'package:flutter/physics.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/green_thumb_extension.dart';
import 'canopy_surfaces.dart';

/// Small shared Canopy pieces for the forum home (and anything that wants a
/// tone-tinted identity): [CanopyAccentTile], [CanopyChip],
/// [CanopyGroupedCard] and [CanopyPressable].
///
/// Colours come in as a `tone` (one of the accent tokens, e.g. via
/// `CanopyTone.colorOf(context.canopy)`) — never a literal — so light mode
/// receives the darkened accents automatically.

/// A tinted icon tile: [tone] at 15% over the surface, a 30% hairline, and the
/// icon in [tone]. The quiet counterpart of the gradient [CanopyTile].
class CanopyAccentTile extends StatelessWidget {
  const CanopyAccentTile({
    super.key,
    required this.icon,
    required this.tone,
    this.size = 40,
  });

  final IconData icon;
  final Color tone;
  final double size;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: SizedBox(
        width: size,
        height: size,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: tone.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: tone.withValues(alpha: 0.30)),
          ),
          child: Center(
            child: Icon(icon, size: size * 0.5, color: tone),
          ),
        ),
      ),
    );
  }
}

/// A pill label in a [tone]: 15% fill, text (and optional icon) in [tone].
/// Never fixed-size: long labels wrap to a second line before clipping.
class CanopyChip extends StatelessWidget {
  const CanopyChip({
    super.key,
    required this.label,
    required this.tone,
    this.icon,
  });

  final String label;
  final Color tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(AppSpacing.rPill),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 12, color: tone),
              const SizedBox(width: 4),
            ],
            Flexible(
              child: Text(
                label,
                style: AppTypography.micro.copyWith(
                  color: tone,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One [CanopyCard] holding [rows] separated by `line` hairlines. No outer
/// padding: each row owns its own, so a pressed row can fill edge to edge.
class CanopyGroupedCard extends StatelessWidget {
  const CanopyGroupedCard({super.key, required this.rows});

  final List<Widget> rows;

  @override
  Widget build(BuildContext context) {
    return CanopyCard(
      padding: EdgeInsets.zero,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < rows.length; i++) ...[
            if (i > 0) const CanopyGroupedCardDivider(),
            rows[i],
          ],
        ],
      ),
    );
  }
}

/// The 1px `line` rule between [CanopyGroupedCard] rows.
class CanopyGroupedCardDivider extends StatelessWidget {
  const CanopyGroupedCardDivider({super.key});

  @override
  Widget build(BuildContext context) =>
      SizedBox(height: 1, child: ColoredBox(color: context.canopy.line));
}

/// How a [CanopyPressable] responds to a press.
enum CanopyPressStyle {
  /// `surface3` shows under the row while pressed.
  highlight,

  /// The child eases to 0.98 on a spring and back on release.
  scale,
}

/// Press feedback for a row or tile, with button semantics.
///
/// Under reduced motion (`disableAnimations`) both styles become a plain dim
/// to 70% opacity — no movement.
class CanopyPressable extends StatefulWidget {
  const CanopyPressable({
    super.key,
    required this.child,
    required this.onTap,
    this.style = CanopyPressStyle.highlight,
    this.semanticLabel,
    this.expanded,
  });

  final Widget child;
  final VoidCallback? onTap;
  final CanopyPressStyle style;
  final String? semanticLabel;

  /// Passed through to semantics for disclosure rows (a collapsible section).
  final bool? expanded;

  @override
  State<CanopyPressable> createState() => _CanopyPressableState();
}

class _CanopyPressableState extends State<CanopyPressable>
    with SingleTickerProviderStateMixin {
  static const _spring = SpringDescription(
    mass: 1,
    stiffness: 420,
    damping: 30,
  );
  static const _pressedScale = 0.98;

  // 0 = rest, 1 = fully pressed. Bounded, so the spring's slight undershoot
  // on release is clamped: no overshoot past rest.
  late final AnimationController _press;
  bool _pressed = false;

  @override
  void initState() {
    super.initState();
    _press = AnimationController(vsync: this);
  }

  @override
  void dispose() {
    _press.dispose();
    super.dispose();
  }

  void _setPressed(bool value) {
    if (_pressed == value) return;
    setState(() => _pressed = value);
    if (widget.style == CanopyPressStyle.scale &&
        !MediaQuery.disableAnimationsOf(context)) {
      _press.animateWith(
        SpringSimulation(_spring, _press.value, value ? 1 : 0, 0),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onTap != null;
    final reduce = MediaQuery.disableAnimationsOf(context);

    Widget content = ConstrainedBox(
      constraints: const BoxConstraints(minHeight: kMinInteractiveDimension),
      child: widget.child,
    );

    if (reduce) {
      content = Opacity(opacity: _pressed ? 0.7 : 1, child: content);
    } else if (widget.style == CanopyPressStyle.highlight) {
      content = ColoredBox(
        color: _pressed ? context.canopy.surface3 : Colors.transparent,
        child: content,
      );
    } else {
      content = AnimatedBuilder(
        animation: _press,
        child: content,
        builder: (context, child) => Transform.scale(
          scale: 1 - (1 - _pressedScale) * _press.value,
          child: child,
        ),
      );
    }

    return Semantics(
      button: enabled,
      enabled: enabled,
      expanded: widget.expanded,
      label: widget.semanticLabel,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        onTapDown: enabled ? (_) => _setPressed(true) : null,
        onTapUp: enabled ? (_) => _setPressed(false) : null,
        onTapCancel: enabled ? () => _setPressed(false) : null,
        child: content,
      ),
    );
  }
}
