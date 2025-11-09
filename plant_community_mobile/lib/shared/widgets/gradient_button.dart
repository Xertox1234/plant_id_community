import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_spacing.dart';

/// A button with gradient background, matching the design from HomePage.tsx
///
/// Example:
/// ```dart
/// GradientButton(
///   onPressed: () => print('Pressed'),
///   label: 'Get Started',
///   icon: Icons.arrow_forward,
/// )
/// ```
class GradientButton extends StatelessWidget {
  /// The text label for the button
  final String label;

  /// Callback when button is pressed
  final VoidCallback? onPressed;

  /// Optional icon to display on the right side of the label
  final IconData? icon;

  /// Whether the button should take full width
  final bool fullWidth;

  /// Button size variant
  final GradientButtonSize size;

  const GradientButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.fullWidth = false,
    this.size = GradientButtonSize.large,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Get gradient colors based on theme (matching React design)
    final gradient = isDark
        ? const LinearGradient(
            colors: [
              AppColors.green700,   // dark:from-green-700
              AppColors.emerald700, // dark:to-emerald-700
            ],
          )
        : const LinearGradient(
            colors: [
              AppColors.green600,   // from-green-600
              AppColors.emerald600, // to-emerald-600
            ],
          );

    // Get button dimensions based on size
    final buttonPadding = switch (size) {
      GradientButtonSize.small => const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
      GradientButtonSize.medium => const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md,
        ),
      GradientButtonSize.large => const EdgeInsets.symmetric(
          horizontal: AppSpacing.xl,
          vertical: AppSpacing.lg,
        ),
    };

    final fontSize = switch (size) {
      GradientButtonSize.small => 14.0,
      GradientButtonSize.medium => 16.0,
      GradientButtonSize.large => 18.0,
    };

    final iconSize = switch (size) {
      GradientButtonSize.small => 18.0,
      GradientButtonSize.medium => 20.0,
      GradientButtonSize.large => 24.0,
    };

    final button = Container(
      decoration: BoxDecoration(
        gradient: onPressed != null ? gradient : null,
        color: onPressed == null ? Colors.grey : null,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          // Hover effect (darker on hover, matching React design)
          // hover:from-green-700 hover:to-emerald-700
          splashColor: isDark
              ? AppColors.green800.withValues(alpha: 0.3)
              : AppColors.green700.withValues(alpha: 0.3),
          highlightColor: isDark
              ? AppColors.emerald800.withValues(alpha: 0.2)
              : AppColors.emerald700.withValues(alpha: 0.2),
          child: Padding(
            padding: buttonPadding,
            child: Row(
              mainAxisSize: fullWidth ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: fontSize,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (icon != null) ...[
                  SizedBox(width: AppSpacing.sm),
                  Icon(
                    icon,
                    color: Colors.white,
                    size: iconSize,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );

    if (fullWidth) {
      return SizedBox(
        width: double.infinity,
        child: button,
      );
    }

    return button;
  }
}

/// Button size variants
enum GradientButtonSize {
  small,
  medium,
  large,
}
