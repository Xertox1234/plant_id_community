import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
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
///   iconColor: AppColors.green600,
/// )
/// ```
class FeatureCard extends StatelessWidget {
  /// The icon to display
  final IconData icon;

  /// The feature title
  final String title;

  /// The feature description
  final String description;

  /// Color for the icon (defaults to green)
  final Color? iconColor;

  /// Optional callback when card is tapped
  final VoidCallback? onTap;

  const FeatureCard({
    super.key,
    required this.icon,
    required this.title,
    required this.description,
    this.iconColor,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final effectiveIconColor = iconColor ??
        (isDark ? AppColors.green500 : AppColors.green600);

    return Card(
      elevation: AppSpacing.elevationSM,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusLG),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLG),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
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
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
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
    );
  }
}

/// Predefined feature card colors matching the design
class FeatureCardColors {
  static Color getIconColor(BuildContext context, FeatureType type) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return switch (type) {
      FeatureType.camera => isDark ? AppColors.green500 : AppColors.green600,
      FeatureType.care => isDark ? AppColors.blue500 : AppColors.blue600,
      FeatureType.community => isDark ? AppColors.purple500 : AppColors.purple600,
      FeatureType.collection => isDark ? AppColors.amber500 : AppColors.amber600,
    };
  }
}

/// Feature types with corresponding colors from design
enum FeatureType {
  camera,    // text-green-600 dark:text-green-500
  care,      // text-blue-600 dark:text-blue-500
  community, // text-purple-600 dark:text-purple-500
  collection // text-amber-600 dark:text-amber-500
}
