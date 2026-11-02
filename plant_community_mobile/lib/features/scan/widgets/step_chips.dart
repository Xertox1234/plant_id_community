import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../capture_steps.dart';

/// One chip per step in [mode] (the current one highlighted, a tap jumps to
/// it), then the mode-switch chip. Scrolls sideways so large text never
/// overflows.
class StepChips extends StatelessWidget {
  const StepChips({
    super.key,
    required this.mode,
    required this.currentRole,
    required this.shotRoles,
    required this.onJump,
    required this.onSwitchMode,
    this.modeChipKey,
  });

  final ScanMode mode;
  final CaptureRole currentRole;
  final Set<CaptureRole> shotRoles;
  final ValueChanged<CaptureRole> onJump;
  final VoidCallback onSwitchMode;
  final Key? modeChipKey;

  @override
  Widget build(BuildContext context) {
    final roles = stepsFor(mode);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Row(
        children: [
          for (final role in roles) ...[
            _ScanChip(
              key: ValueKey('step-chip-${role.name}'),
              label: role.chipLabel,
              selected: role == currentRole,
              done: shotRoles.contains(role),
              onTap: () => onJump(role),
            ),
            const SizedBox(width: AppSpacing.sm),
          ],
          const SizedBox(width: AppSpacing.sm),
          _ScanChip(
            key: modeChipKey,
            label: mode == ScanMode.diagnose
                ? 'Just identify it'
                : "Something's wrong?",
            selected: false,
            done: false,
            outlined: true,
            onTap: onSwitchMode,
          ),
        ],
      ),
    );
  }
}

class _ScanChip extends StatelessWidget {
  const _ScanChip({
    super.key,
    required this.label,
    required this.selected,
    required this.done,
    required this.onTap,
    this.outlined = false,
  });

  final String label;
  final bool selected;
  final bool done;
  final bool outlined;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final fg = selected ? cs.onPrimary : cs.onSurface;
    final radius = BorderRadius.circular(AppSpacing.rPill);
    final duration = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 160);
    return Semantics(
      button: true,
      selected: selected,
      child: AnimatedContainer(
        duration: duration,
        curve: Easing.emphasizedDecelerate,
        decoration: BoxDecoration(
          color: selected
              ? cs.primary
              : cs.surface.withValues(alpha: outlined ? 0.4 : 0.72),
          borderRadius: radius,
          border: outlined
              ? Border.all(color: cs.onSurface.withValues(alpha: 0.6))
              : null,
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: radius,
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 48, minWidth: 48),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (done) ...[
                      Icon(LucideIcons.check, size: 16, color: fg),
                      const SizedBox(width: AppSpacing.xs),
                    ],
                    Text(
                      label,
                      style: AppTypography.uiLabel.copyWith(color: fg),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
