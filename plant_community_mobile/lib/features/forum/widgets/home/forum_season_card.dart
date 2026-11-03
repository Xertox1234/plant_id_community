import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_label.dart';
import '../../../../shared/widgets/canopy_surfaces.dart';
import '../../models/models.dart';
import '../forum_stats_grid.dart';

/// "Your season": the member's all-time numbers in one card (the redesigned
/// twin of `ForumStatsGrid`, same `meStatsProvider` data). Four equal stats
/// split by hairlines, a labelled progress bar for the next badge, and the
/// earned badges beneath. The stats are all-time, so nothing here claims a
/// season window.
class ForumSeasonCard extends StatelessWidget {
  const ForumSeasonCard({super.key, required this.stats});

  final ForumMyStats stats;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canopy = context.canopy;
    final target = stats.badgeTarget;
    final hasTrack = target > 0 && stats.badgeName.isNotEmpty;
    final progressText = stats.badgeComplete
        ? '${stats.badgeName} badge · complete'
        : '${stats.badgeName} badge · ${stats.badgeProgress} / $target IDs';

    return CanopyCard(
      child: Stack(
        children: [
          Positioned(
            right: -12,
            top: -8,
            child: ExcludeSemantics(
              child: Icon(
                LucideIcons.leaf,
                size: 96,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.06),
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CanopyLabel('Your season'),
              const SizedBox(height: AppSpacing.sm),
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _Stat(value: stats.identificationsShared, label: 'IDs'),
                    const _Rule(),
                    _Stat(value: stats.posts, label: 'Posts'),
                    const _Rule(),
                    _Stat(value: stats.solutionsAccepted, label: 'Solutions'),
                    const _Rule(),
                    _Stat(
                      value: stats.streakDays,
                      label: 'Day streak',
                      color: canopy.clay,
                    ),
                  ],
                ),
              ),
              if (hasTrack) ...[
                const SizedBox(height: AppSpacing.md),
                Text(
                  progressText,
                  style: AppTypography.meta.copyWith(color: canopy.ink2),
                ),
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

class _Rule extends StatelessWidget {
  const _Rule();

  @override
  Widget build(BuildContext context) =>
      SizedBox(width: 1, child: ColoredBox(color: context.canopy.line));
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label, this.color});

  final int value;
  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    return Expanded(
      child: Semantics(
        container: true,
        label: '$label: $value',
        excludeSemantics: true,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Column(
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  '$value',
                  style: AppTypography.h2.copyWith(
                    color: color ?? Theme.of(context).colorScheme.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                label,
                textAlign: TextAlign.center,
                style: AppTypography.meta.copyWith(color: canopy.ink3),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
