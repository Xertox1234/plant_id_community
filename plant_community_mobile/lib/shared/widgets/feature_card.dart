import 'package:flutter/material.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../core/constants/app_spacing.dart';

/// A feature card displaying an icon, title, and description
///
/// Ported from HomePage.tsx feature cards
///
/// Example:
/// ```dart
/// FeatureCard(
///   icon: Icons.camera_alt,
///   title: 'Instant Identification',
///   description: 'Snap a photo and instantly identify any plant',
///   type: FeatureType.camera,
/// )
/// ```
class FeatureCard extends StatelessWidget {
  /// The icon to display
  final IconData icon;

  /// The feature title
  final String title;

  /// The feature description
  final String description;

  /// Color for the icon (defaults to camera/green)
  final Color? iconColor;

  /// The feature type (determines default icon color)
  final FeatureType type;

  /// Optional callback when card is tapped
  final VoidCallback? onTap;

  const FeatureCard({
    super.key,
    required this.icon,
    required this.title,
    required this.description,
    this.iconColor,
    this.type = FeatureType.camera,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;
    final effectiveIconColor =
        iconColor ?? FeatureCardColors.getIconColor(context, type);

    return Container(
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(AppSpacing.rMd),
        boxShadow: ext.shadow1,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(AppSpacing.rMd),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
          child: Padding(
            padding: EdgeInsets.all(ext.padCard),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Icon container (flex-shrink-0)
                Container(
                  decoration: BoxDecoration(
                    color: effectiveIconColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
                  ),
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  child: Icon(
                    icon,
                    color: effectiveIconColor,
                    size: 24,
                    semanticLabel: title,
                  ),
                ),
                const SizedBox(width: AppSpacing.lg),
                // Text content
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        description,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).textTheme.bodySmall?.color,
                          height: 1.5, // leading-relaxed
                        ),
                      ),
                    ],
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

/// Predefined feature card colors matching the design
class FeatureCardColors {
  static Color getIconColor(BuildContext context, FeatureType type) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;

    return switch (type) {
      FeatureType.camera => cs.primary,
      FeatureType.care => ext.sky,
      FeatureType.community => ext.berry,
      FeatureType.collection => cs.tertiary,
    };
  }
}

/// Feature types with corresponding colors from design
enum FeatureType {
  camera, // text-green-600 dark:text-green-500
  care, // text-blue-600 dark:text-blue-500
  community, // text-purple-600 dark:text-purple-500
  collection, // text-amber-600 dark:text-amber-500
}
