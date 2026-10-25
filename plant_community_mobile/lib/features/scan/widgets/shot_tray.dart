import 'dart:io';

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../capture_steps.dart';

/// One slot per step in [mode]: a thumbnail and a check once shot. Tapping a
/// filled slot retakes it; tapping an empty one jumps to that step.
class ShotTray extends StatelessWidget {
  const ShotTray({
    super.key,
    required this.mode,
    required this.currentRole,
    required this.shots,
    required this.onRetake,
    required this.onJump,
  });

  final ScanMode mode;
  final CaptureRole currentRole;
  final Map<CaptureRole, String> shots;
  final ValueChanged<CaptureRole> onRetake;
  final ValueChanged<CaptureRole> onJump;

  static const double slotSize = 56;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (final role in stepsFor(mode))
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
            child: _Slot(
              key: ValueKey('tray-${role.name}'),
              role: role,
              path: shots[role],
              current: role == currentRole,
              onTap: () =>
                  shots.containsKey(role) ? onRetake(role) : onJump(role),
            ),
          ),
      ],
    );
  }
}

class _Slot extends StatelessWidget {
  const _Slot({
    super.key,
    required this.role,
    required this.path,
    required this.current,
    required this.onTap,
  });

  final CaptureRole role;
  final String? path;
  final bool current;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final canopy = context.canopy;
    final radius = BorderRadius.circular(AppSpacing.rSm);
    final filled = path != null;
    final placeholder = ColoredBox(
      color: cs.surface.withValues(alpha: 0.6),
      child: Icon(
        filled ? LucideIcons.image : LucideIcons.plus,
        size: 20,
        color: canopy.ink2,
      ),
    );
    return Semantics(
      button: true,
      label: filled
          ? 'Retake ${role.chipLabel.toLowerCase()} photo'
          : '${role.chipLabel} photo, not taken',
      onTap: onTap,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: ShotTray.slotSize,
          height: ShotTray.slotSize,
          decoration: BoxDecoration(
            borderRadius: radius,
            border: Border.all(
              color: current ? cs.primary : canopy.line2,
              width: current ? 2 : 1,
            ),
          ),
          child: ClipRRect(
            borderRadius: radius,
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (filled)
                  Image.file(
                    File(path!),
                    fit: BoxFit.cover,
                    cacheWidth: 168,
                    errorBuilder: (_, _, _) => placeholder,
                  )
                else
                  placeholder,
                if (filled)
                  Positioned(
                    right: 3,
                    bottom: 3,
                    child: DecoratedBox(
                      key: const ValueKey('tray-check'),
                      decoration: BoxDecoration(
                        color: cs.primary,
                        shape: BoxShape.circle,
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(2),
                        child: Icon(
                          LucideIcons.check,
                          size: 12,
                          color: cs.onPrimary,
                        ),
                      ),
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
