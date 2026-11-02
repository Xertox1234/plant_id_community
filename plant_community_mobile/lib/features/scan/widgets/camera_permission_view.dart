import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../shared/widgets/clay_button.dart';
import '../scan_camera.dart';

/// Shown in place of the preview when the camera cannot start. The screen
/// keeps its close button above this view.
class CameraPermissionView extends StatelessWidget {
  const CameraPermissionView({
    super.key,
    required this.error,
    required this.onOpenSettings,
    required this.onChooseFromPhotos,
  });

  final ScanCameraError error;
  final VoidCallback onOpenSettings;
  final VoidCallback onChooseFromPhotos;

  static const String accessOffCopy =
      'Camera access is off. Houseplant MD needs the camera to check your '
      'plant.';
  static const String unavailableCopy =
      "Camera isn't available on this device.";

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final (IconData icon, String copy, Widget? action) = switch (error) {
      ScanCameraError.denied => (
        LucideIcons.cameraOff,
        accessOffCopy,
        ClayButton(label: 'Open Settings', onPressed: onOpenSettings),
      ),
      ScanCameraError.restricted => (
        LucideIcons.cameraOff,
        accessOffCopy,
        null,
      ),
      ScanCameraError.unavailable => (
        LucideIcons.camera,
        unavailableCopy,
        ClayButton(
          label: 'Choose from photos',
          icon: LucideIcons.images,
          onPressed: onChooseFromPhotos,
        ),
      ),
    };
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: context.canopy.ink2),
            const SizedBox(height: AppSpacing.md),
            Text(
              copy,
              textAlign: TextAlign.center,
              style: AppTypography.bodyLg.copyWith(color: cs.onSurface),
            ),
            if (action != null) ...[
              const SizedBox(height: AppSpacing.lg),
              action,
            ],
          ],
        ),
      ),
    );
  }
}
