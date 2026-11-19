import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_label.dart';
import '../../../../shared/widgets/canopy_surfaces.dart';
import '../../models/models.dart';
import '../forum_stats_grid.dart';
import '../forum_style.dart';

/// "Your season": the member's all-time numbers in one card (the redesigned
/// twin of `ForumStatsGrid`, same `meStatsProvider` data). Four equal,
/// left-aligned stats, a labelled progress bar for the next badge, and the
/// earned badges beneath. The stats are all-time, so nothing here claims a
/// season window.
class ForumSeasonCard extends StatelessWidget {
  const ForumSeasonCard({super.key, required this.stats});

  final ForumMyStats stats;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final target = stats.badgeTarget;
    final hasTrack = target > 0 && stats.badgeName.isNotEmpty;
    final progressText = stats.badgeComplete
        ? '${stats.badgeName} badge · complete'
        : '${stats.badgeName} badge · ${stats.badgeProgress} of $target IDs';

    return CanopyCard(
      child: Stack(
        children: [
          Positioned(
            right: -22,
            top: -26,
            child: ExcludeSemantics(
              child: Icon(
                LucideIcons.leaf,
                size: 80,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.06),
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ink2, not the default ink3: 11pt ink3 on a card is under
              // 4.5:1 in both modes.
              CanopyLabel('Your season', color: context.canopy.ink2),
              const SizedBox(height: AppSpacing.sm),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Stat(value: stats.identificationsShared, label: 'IDs'),
                  _Stat(value: stats.posts, label: 'Posts'),
                  _Stat(value: stats.solutionsAccepted, label: 'Solutions'),
                  _Stat(value: stats.streakDays, label: 'Day streak'),
                ],
              ),
              if (hasTrack) ...[
                const SizedBox(height: AppSpacing.md),
                Text(progressText, style: forumMeta(context)),
                const SizedBox(height: 6),
                Semantics(
                  label: '${stats.badgeName} badge progress',
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(AppSpacing.rPill),
                    child: LinearProgressIndicator(
                      value: (stats.badgeProgress / target).clamp(0.0, 1.0),
                      minHeight: 6,
                      backgroundColor:
                          theme.colorScheme.surfaceContainerHighest,
                    ),
                  ),
                ),
              ],
              if (stats.badges.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                ForumBadgeChips(badges: stats.badges),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label});

  final int value;
  final String label;

  @override
  Widget build(BuildContext context) {
    // Left-aligned, so the first number sits on the card's text edge like
    // the eyebrow above it and the badge line below.
    return Expanded(
      child: Semantics(
        container: true,
        label: '$label: $value',
        excludeSemantics: true,
        child: Padding(
          padding: const EdgeInsetsDirectional.only(end: AppSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: AlignmentDirectional.centerStart,
                child: Text(
                  '$value',
                  style: AppTypography.h2.copyWith(
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ),
              // A quarter of a 320pt card at 2.0x is narrower than
              // "Solutions": wrapped, the word would split mid-word. Scale
              // the label down instead, as the number above does.
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: AlignmentDirectional.centerStart,
                child: Text(label, style: forumMeta(context)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
