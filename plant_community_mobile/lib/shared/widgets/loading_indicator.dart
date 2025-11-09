import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_spacing.dart';

/// A customizable loading indicator with various styles
///
/// Example:
/// ```dart
/// LoadingIndicator() // Default circular progress
/// LoadingIndicator.linear() // Linear progress bar
/// LoadingIndicator.withMessage(message: 'Loading plants...')
/// ```
class LoadingIndicator extends StatelessWidget {
  /// Optional message to display below the indicator
  final String? message;

  /// The type of loading indicator to display
  final LoadingIndicatorType type;

  /// Size of the loading indicator
  final double size;

  /// Color of the loading indicator (defaults to theme primary color)
  final Color? color;

  const LoadingIndicator({
    super.key,
    this.message,
    this.type = LoadingIndicatorType.circular,
    this.size = 40.0,
    this.color,
  });

  /// Creates a linear progress indicator
  const LoadingIndicator.linear({
    super.key,
    this.message,
    this.color,
  })  : type = LoadingIndicatorType.linear,
        size = 4.0;

  /// Creates a loading indicator with a message
  const LoadingIndicator.withMessage({
    super.key,
    required this.message,
    this.type = LoadingIndicatorType.circular,
    this.size = 40.0,
    this.color,
  });

  /// Creates a full-screen loading overlay
  const LoadingIndicator.overlay({
    super.key,
    this.message,
    this.size = 60.0,
    this.color,
  }) : type = LoadingIndicatorType.overlay;

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? AppColors.green600;

    if (type == LoadingIndicatorType.overlay) {
      return Container(
        color: Colors.black.withValues(alpha: 0.5),
        child: Center(
          child: Card(
            margin: const EdgeInsets.all(AppSpacing.xl),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xl2),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: size,
                    height: size,
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(effectiveColor),
                      strokeWidth: 4.0,
                    ),
                  ),
                  if (message != null) ...[
                    const SizedBox(height: AppSpacing.lg),
                    Text(
                      message!,
                      style: Theme.of(context).textTheme.bodyLarge,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
    }

    if (type == LoadingIndicatorType.linear) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LinearProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(effectiveColor),
            backgroundColor: effectiveColor.withValues(alpha: 0.2),
            minHeight: size,
          ),
          if (message != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              message!,
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
          ],
        ],
      );
    }

    // Circular indicator (default)
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: size,
            height: size,
            child: CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(effectiveColor),
              strokeWidth: 3.0,
            ),
          ),
          if (message != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              message!,
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
          ],
        ],
      ),
    );
  }
}

/// Types of loading indicators
enum LoadingIndicatorType {
  /// Circular progress indicator (default)
  circular,

  /// Linear progress bar
  linear,

  /// Full-screen overlay with loading indicator
  overlay,
}

/// Extension to easily show loading dialog
extension LoadingDialogExtension on BuildContext {
  /// Show a loading dialog that blocks interaction
  ///
  /// Call Navigator.pop(context) to dismiss
  void showLoadingDialog({String? message}) {
    showDialog(
      context: this,
      barrierDismissible: false,
      builder: (context) => PopScope(
        canPop: false,
        child: LoadingIndicator.overlay(message: message),
      ),
    );
  }
}
