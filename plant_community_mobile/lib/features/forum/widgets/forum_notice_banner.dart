import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';

/// An inline info banner used for the "awaiting moderation" (notify-and-return)
/// notice and similar transient messages. Announced to screen readers via a
/// polite live region.
class ForumNoticeBanner extends StatelessWidget {
  const ForumNoticeBanner({
    super.key,
    required this.message,
    this.icon = Icons.hourglass_top,
  });

  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      liveRegion: true,
      container: true,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: theme.colorScheme.tertiaryContainer,
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
        ),
        child: Row(
          children: [
            Icon(icon, size: 20, color: theme.colorScheme.onTertiaryContainer),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onTertiaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
