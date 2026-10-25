import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';

/// Gallery (left), shutter (centre) and Skip-or-Done (right). The side slots
/// share the leftover width equally so the shutter stays centred at any text
/// size.
class CaptureControls extends StatelessWidget {
  const CaptureControls({
    super.key,
    required this.showSkip,
    required this.canFinish,
    required this.shutterEnabled,
    required this.onGallery,
    required this.onShutter,
    required this.onSkip,
    required this.onDone,
    required this.galleryKey,
    required this.shutterKey,
    required this.skipKey,
    required this.doneKey,
  });

  final bool showSkip;
  final bool canFinish;
  final bool shutterEnabled;
  final VoidCallback onGallery;
  final VoidCallback onShutter;
  final VoidCallback onSkip;
  final VoidCallback onDone;
  final Key galleryKey, shutterKey, skipKey, doneKey;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Row(
        children: [
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: IconButton.filledTonal(
                key: galleryKey,
                tooltip: 'Choose from photos',
                iconSize: 22,
                constraints: const BoxConstraints(minWidth: 52, minHeight: 52),
                onPressed: onGallery,
                icon: const Icon(LucideIcons.images),
              ),
            ),
          ),
          _Shutter(
            key: shutterKey,
            onPressed: shutterEnabled ? onShutter : null,
          ),
          Expanded(
            child: Align(
              alignment: Alignment.centerRight,
              child: showSkip
                  ? TextButton(
                      key: skipKey,
                      onPressed: onSkip,
                      style: TextButton.styleFrom(
                        foregroundColor: cs.onSurface,
                        minimumSize: const Size(64, 48),
                        textStyle: AppTypography.button,
                      ),
                      child: const Text('Skip', textAlign: TextAlign.center),
                    )
                  : _DoneButton(
                      key: doneKey,
                      onPressed: canFinish ? onDone : null,
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DoneButton extends StatelessWidget {
  const _DoneButton({super.key, required this.onPressed});

  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final enabled = onPressed != null;
    final radius = BorderRadius.circular(AppSpacing.rPill);
    return Semantics(
      button: true,
      enabled: enabled,
      child: Opacity(
        opacity: enabled ? 1 : 0.45,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: context.canopy.ctaGradient,
            borderRadius: radius,
            boxShadow: enabled ? context.canopy.shadow1 : const [],
          ),
          child: Material(
            type: MaterialType.transparency,
            child: InkWell(
              borderRadius: radius,
              onTap: onPressed,
              child: ConstrainedBox(
                constraints: const BoxConstraints(minHeight: 48, minWidth: 72),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.sm,
                  ),
                  child: Center(
                    widthFactor: 1,
                    heightFactor: 1,
                    child: Text(
                      'Done',
                      style: AppTypography.button.copyWith(color: cs.onPrimary),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Shutter extends StatefulWidget {
  const _Shutter({super.key, required this.onPressed});

  final VoidCallback? onPressed;

  @override
  State<_Shutter> createState() => _ShutterState();
}

class _ShutterState extends State<_Shutter> {
  bool _down = false;

  void _setDown(bool v) {
    if (_down != v) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final enabled = widget.onPressed != null;
    final duration = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 120);
    return Semantics(
      button: true,
      enabled: enabled,
      label: 'Take photo',
      onTap: widget.onPressed,
      excludeSemantics: true,
      child: GestureDetector(
        onTapDown: enabled ? (_) => _setDown(true) : null,
        onTapUp: enabled ? (_) => _setDown(false) : null,
        onTapCancel: () => _setDown(false),
        onTap: widget.onPressed,
        child: AnimatedScale(
          scale: _down ? 0.92 : 1,
          duration: duration,
          curve: Easing.emphasizedDecelerate,
          child: Container(
            width: 72,
            height: 72,
            padding: const EdgeInsets.all(5),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: cs.onSurface.withValues(alpha: enabled ? 0.9 : 0.4),
                width: 3,
              ),
            ),
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: cs.onSurface.withValues(alpha: enabled ? 0.95 : 0.35),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
