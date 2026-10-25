import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';

/// Full-screen "Checking your plant…" cover shown while a scan uploads.
///
/// Absorbs every touch so the controls underneath cannot be used. A null
/// [progress] (nothing reported yet) draws an indeterminate bar.
class SubmitOverlay extends StatelessWidget {
  const SubmitOverlay({super.key, required this.progress});

  final double? progress;

  static const copy = 'Checking your plant…';

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // A ModalBarrier absorbs every touch aimed at the controls below.
          ModalBarrier(
            dismissible: false,
            color: cs.scrim.withValues(alpha: 0.8),
          ),
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    copy,
                    textAlign: TextAlign.center,
                    style: AppTypography.h2.copyWith(color: cs.onSurface),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  LinearProgressIndicator(
                    key: const Key('scan-submit-progress'),
                    value: progress?.clamp(0.0, 1.0).toDouble(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
