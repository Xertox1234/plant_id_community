import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/forum_author.dart';

/// A small chip showing an author's trust level (Basic/Member/Regular/Leader).
///
/// Level 0 ("New") and `null` render nothing — matching the web's `>= 1` gate
/// so brand-new authors are intentionally un-badged. Note this is unrelated to
/// the unread-topic "New" badge on topic rows.
class TrustBadge extends StatelessWidget {
  const TrustBadge(this.trustLevel, {super.key});

  final int? trustLevel;

  @override
  Widget build(BuildContext context) {
    final level = trustLevel;
    if (level == null || level < 1) return const SizedBox.shrink();
    final label = trustLevelLabel(level);
    if (label == null) return const SizedBox.shrink();

    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: theme.colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Text(
        label,
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSecondaryContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
