import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../frame_quality.dart';

/// Spec copy for a corrective hint; null for [FrameHint.none] and
/// [FrameHint.good], where the step prompt shows instead. Without a flash
/// there is no torch to tap, so the dark hint is just "Too dark".
String? hintCopy(FrameHint? hint, {required bool hasFlash}) => switch (hint) {
  FrameHint.moveCloser => 'Move closer',
  FrameHint.tooDark => hasFlash ? 'Too dark, tap ⚡' : 'Too dark',
  FrameHint.holdSteady => 'Hold steady',
  FrameHint.none || FrameHint.good || null => null,
};

/// The pill under the step title: the stabilized hint, or the step [prompt]
/// when there is nothing to correct. Announced as a live region.
class HintChip extends StatelessWidget {
  const HintChip({
    super.key,
    required this.hint,
    required this.prompt,
    required this.hasFlash,
  });

  final FrameHint? hint;
  final String prompt;
  final bool hasFlash;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final copy = hintCopy(hint, hasFlash: hasFlash);
    final locked = hint == FrameHint.good;
    final IconData? icon = switch (hint) {
      FrameHint.tooDark => hasFlash ? LucideIcons.zap : LucideIcons.moon,
      FrameHint.holdSteady => LucideIcons.hand,
      FrameHint.moveCloser => LucideIcons.zoomIn,
      FrameHint.good => LucideIcons.check,
      _ => null,
    };
    final fg = locked ? cs.onPrimary : cs.onSurface;
    final text = copy ?? prompt;
    final duration = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 160);

    return Semantics(
      liveRegion: true,
      child: AnimatedSwitcher(
        duration: duration,
        child: DecoratedBox(
          key: ValueKey(text + (locked ? '#locked' : '')),
          decoration: BoxDecoration(
            color: locked
                ? cs.primary.withValues(alpha: 0.92)
                : cs.surface.withValues(alpha: 0.78),
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 16, color: fg),
                  const SizedBox(width: AppSpacing.sm),
                ],
                Flexible(
                  child: Text(
                    text,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.button.copyWith(color: fg),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
