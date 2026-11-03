import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_surfaces.dart';
import '../../models/models.dart';
import '../../providers/forum_providers.dart';
import '../forum_avatar_cluster.dart';

/// The forum home's "Who's online" panel (`communityStatsProvider`). Public
/// read; hidden before its first data and on a first-load error, like the
/// experts section, since a missing presence card costs nothing. A refresh
/// keeps the last counts showing.
class ForumWhosOnline extends ConsumerWidget {
  const ForumWhosOnline({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // `.value`, not `asData`: a refresh keeps the last counts on screen.
    final stats = ref.watch(communityStatsProvider).value;
    if (stats == null) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "Who's online",
          style: AppTypography.h3.copyWith(color: theme.colorScheme.onSurface),
        ),
        const SizedBox(height: AppSpacing.sm),
        _Panel(stats: stats),
      ],
    );
  }
}

String _plural(int n, String singular, [String? plural]) =>
    '$n ${n == 1 ? singular : (plural ?? '${singular}s')}';

String _name(ForumAuthor a) =>
    a.displayName.trim().isEmpty ? a.username : a.displayName.trim();

String _firstName(ForumAuthor a) => _name(a).split(RegExp(r'\s+')).first;

/// "Sam, Will and simtest"; past three: "Sam, Will, Iris and 2 others".
String _namesLine(ForumCommunityStats stats) {
  final sample = stats.onlineSample;
  final names = [for (final a in sample.take(3)) _firstName(a)];
  final total = math.max(stats.membersOnline, sample.length);
  final extra = total - names.length;
  if (extra > 0) {
    return '${names.join(', ')} and ${_plural(extra, 'other')}';
  }
  if (names.length <= 1) return names.join();
  return '${names.sublist(0, names.length - 1).join(', ')} and ${names.last}';
}

class _Panel extends StatelessWidget {
  const _Panel({required this.stats});

  final ForumCommunityStats stats;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canopy = context.canopy;
    final newest = stats.newestMember;
    final muted = AppTypography.meta.copyWith(color: canopy.ink2);
    return CanopyCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: AppSpacing.md,
            runSpacing: 2,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Static by design: the ambient background stays still,
                  // and a pulsing dot would be noise on a list screen.
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: canopy.leaf,
                      shape: BoxShape.circle,
                    ),
                    child: const SizedBox(width: 8, height: 8),
                  ),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      stats.membersOnline == 0
                          ? 'No members online right now'
                          : '${_plural(stats.membersOnline, 'member')} online',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
              Text(
                '${stats.registeredMembers} registered',
                style: AppTypography.label.copyWith(color: canopy.ink3),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (stats.membersOnline != 0 && stats.onlineSample.isNotEmpty)
            // A Wrap, not a Row: at large text the names drop under the
            // cluster rather than being squeezed to nothing.
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                AuthorAvatarCluster(authors: stats.onlineSample, max: 5),
                Text(_namesLine(stats), style: muted),
              ],
            ),
          const SizedBox(height: AppSpacing.sm),
          Divider(height: 1, thickness: 1, color: canopy.line),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.md,
            runSpacing: 2,
            children: [
              Text(
                '${_plural(stats.topicCount, 'topic')} · '
                '${_plural(stats.postCount, 'post')}',
                style: AppTypography.label.copyWith(color: canopy.ink3),
              ),
              if (newest != null)
                Text('Newest: ${_name(newest)}', style: muted),
            ],
          ),
        ],
      ),
    );
  }
}
