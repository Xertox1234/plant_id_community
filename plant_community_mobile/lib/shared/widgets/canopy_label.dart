import 'package:flutter/material.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/green_thumb_extension.dart';

/// The Canopy eyebrow / data label — the web's `.gt-label`.
///
/// Mono, uppercase, tracked `0.08em`, in muted ink. This is the app's ONE
/// small-label treatment: the codebase previously had three (a Geist 600
/// eyebrow at `0.06em`, this mono one, and a `0.18em` variant in `HeroCard`),
/// which is how a design system stops reading as one system.
///
/// Flutter has no `text-transform`, so the uppercasing happens here rather than
/// at every call site — passing an already-uppercased string is harmless.
class CanopyLabel extends StatelessWidget {
  const CanopyLabel(this.text, {super.key, this.color});

  final String text;

  /// Defaults to `ink-3`. Override only for a label that must carry an accent
  /// (a `secondary` eyebrow on a hero card, say).
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: AppTypography.label.copyWith(color: color ?? context.canopy.ink3),
    );
  }
}
