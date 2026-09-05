import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';

/// The "Your season" 2×2 stat grid for `GET me/stats/` (todo 341 wave 4) —
/// the mobile twin of the web `SeasonStatsGrid`. The stats are ALL-TIME by
/// design (spec §9), so no sublabel here may claim a season window.
class ForumStatsGrid extends StatelessWidget {
  const ForumStatsGrid({super.key, required this.stats});

  final ForumMyStats stats;

  @override
  Widget build(BuildContext context) {
    final badgeTarget = stats.badgeTarget;
    final hasBadgeTrack = badgeTarget > 0 && stats.badgeName.isNotEmpty;
    return Column(
      children: [
        // IntrinsicHeight bounds the row so `stretch` can equalise the two
        // tiles: the grid lives in a vertical ListView, where a bare
        // stretched Row has infinite height to stretch into.
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: _StatTile(
                  icon: Icons.document_scanner_outlined,
                  value: stats.identificationsShared,
                  label: 'Identifications',
                  // Badge progress lives on this tile — its value IS the
                  // badge's tracked metric.
                  sublabel: !hasBadgeTrack
                      ? 'all time'
                      : stats.badgeComplete
                      ? '${stats.badgeName} badge complete'
                      : '${badgeTarget - stats.badgeProgress} to '
                            '${stats.badgeName} badge',
                  progress: hasBadgeTrack
                      ? (stats.badgeProgress / badgeTarget).clamp(0.0, 1.0)
                      : null,
                  progressLabel: '${stats.badgeName} badge progress',
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: _StatTile(
                  icon: Icons.forum_outlined,
                  value: stats.posts,
                  label: 'Posts',
                  sublabel: 'all time',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: _StatTile(
                  icon: Icons.check_circle_outline,
                  value: stats.solutionsAccepted,
                  label: 'Solutions',
                  sublabel: 'accepted answers',
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: _StatTile(
                  icon: Icons.local_fire_department_outlined,
                  value: stats.streakDays,
                  label: 'Day streak',
                  sublabel: stats.streakDays == 0
                      ? 'Post to start a streak'
                      : stats.streakDays == 1
                      ? 'day in a row'
                      : 'days in a row',
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.icon,
    required this.value,
    required this.label,
    required this.sublabel,
    this.progress,
    this.progressLabel,
  });

  final IconData icon;
  final int value;
  final String label;
  final String sublabel;

  /// 0–1 badge progress, or `null` for no bar.
  final double? progress;
  final String? progressLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final progress = this.progress;
    return Semantics(
      container: true,
      label: '$label: $value, $sublabel',
      excludeSemantics: true,
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 18, color: theme.colorScheme.secondary),
              const SizedBox(height: AppSpacing.xs),
              Text(
                '$value',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(label, style: theme.textTheme.labelLarge),
              Text(
                sublabel,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (progress != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Semantics(
                  label: progressLabel,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(AppSpacing.rPill),
                    child: LinearProgressIndicator(
                      value: progress,
                      minHeight: 6,
                      backgroundColor:
                          theme.colorScheme.surfaceContainerHighest,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Earned badges as a wrap of chips (todo 348 on the server; todo 341 wave
/// 4 here). Shared by the forum home's stats section and the public
/// profile. Each chip's tooltip is the badge's description; the semantics
/// label carries both. Renders nothing for an empty list.
class ForumBadgeChips extends StatelessWidget {
  const ForumBadgeChips({super.key, required this.badges});

  final List<ForumBadge> badges;

  @override
  Widget build(BuildContext context) {
    if (badges.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.xs,
      children: [
        for (final badge in badges)
          Semantics(
            label: badge.description.isNotEmpty
                ? '${badge.name} badge: ${badge.description}'
                : '${badge.name} badge',
            excludeSemantics: true,
            child: Tooltip(
              message: badge.description.isNotEmpty
                  ? badge.description
                  : badge.name,
              child: Chip(
                avatar: Icon(
                  Icons.workspace_premium_outlined,
                  size: 18,
                  color: theme.colorScheme.onSecondaryContainer,
                ),
                label: Text(badge.name),
                backgroundColor: theme.colorScheme.secondaryContainer,
                labelStyle: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSecondaryContainer,
                ),
                side: BorderSide.none,
              ),
            ),
          ),
      ],
    );
  }
}
