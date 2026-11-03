import 'package:flutter/material.dart';

import '../../../../core/constants/app_brand.dart';
import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/brand_mark.dart';
import '../../../../shared/widgets/canopy_label.dart';

/// Quiet, centred footer for the end of the forum home: the brand mark (its
/// deep-pine tile in both modes), the name, the eyebrow and a copyright line
/// whose year comes from the clock ([now] is a test seam). No links.
class ForumHomeFooter extends StatelessWidget {
  const ForumHomeFooter({super.key, this.now});

  final DateTime? now;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final year = (now ?? DateTime.now()).year;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const BrandMark(size: 30),
          const SizedBox(height: AppSpacing.sm),
          Text(
            AppBrand.name,
            textAlign: TextAlign.center,
            style: AppTypography.h3.copyWith(
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 2),
          const CanopyLabel('The plant clinic'),
          const SizedBox(height: AppSpacing.sm),
          Text(
            '© $year ${AppBrand.name}',
            textAlign: TextAlign.center,
            style: AppTypography.meta.copyWith(color: canopy.ink3),
          ),
        ],
      ),
    );
  }
}
