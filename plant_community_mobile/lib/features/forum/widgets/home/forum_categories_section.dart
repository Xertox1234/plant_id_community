import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_accents.dart';
import '../../forum_format.dart';
import '../../models/models.dart';
import '../../utils/board_identity.dart';

/// Gap between one category and the next.
const double _categoryGap = AppSpacing.lg;

/// The forum index: per category a header, then one grouped card of its
/// forums. The whole row is the tap target (>= 48pt), and its press feedback
/// is a `surface3` highlight rather than a scale (design spec §8.1).
///
/// Locked forums and links are only drawn when [onLockedTap] / [onLinkTap] are
/// given; a category with nothing left to draw is skipped. The collapse
/// chevron shows only when [onToggleCollapse] is given.
class ForumCategoriesSection extends StatelessWidget {
  const ForumCategoriesSection({
    super.key,
    required this.categories,
    required this.onForumTap,
    this.onLockedTap,
    this.onLinkTap,
    this.collapsed = const {},
    this.onToggleCollapse,
  });

  final List<ForumCategory> categories;
  final void Function(ForumBoard forum) onForumTap;
  final void Function(ForumBoard forum)? onLockedTap;
  final void Function(ForumLink link)? onLinkTap;
  final Set<int> collapsed;
  final void Function(ForumCategory category)? onToggleCollapse;

  @override
  Widget build(BuildContext context) {
    final blocks = <Widget>[];
    for (final category in categories) {
      final forums = [
        for (final f in category.forums)
          if (!f.isLocked || onLockedTap != null) f,
      ];
      final showLinks = onLinkTap != null && category.links.isNotEmpty;
      if (forums.isEmpty && !showLinks) continue;
      blocks.add(
        Padding(
          key: ValueKey('category-${category.id}'),
          padding: EdgeInsets.only(top: blocks.isEmpty ? 0 : _categoryGap),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _CategoryHeader(category: category),
              if (forums.isNotEmpty)
                CanopyGroupedCard(
                  rows: [
                    for (final forum in forums)
                      _ForumRow(
                        forum: forum,
                        onTap: () => forum.isLocked
                            ? onLockedTap?.call(forum)
                            : onForumTap(forum),
                      ),
                  ],
                ),
            ],
          ),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: blocks,
    );
  }
}

class _CategoryHeader extends StatelessWidget {
  const _CategoryHeader({required this.category});

  final ForumCategory category;

  @override
  Widget build(BuildContext context) {
    final icon = category.icon.trim();
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Semantics(
        header: true,
        child: Text(
          icon.isEmpty ? category.title : '$icon ${category.title}',
          style: AppTypography.h3.copyWith(
            color: Theme.of(context).colorScheme.onSurface,
          ),
        ),
      ),
    );
  }
}

String _count(int n, String singular) => '$n $singular${n == 1 ? '' : 's'}';

class _ForumRow extends StatelessWidget {
  const _ForumRow({required this.forum, required this.onTap});

  final ForumBoard forum;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canopy = context.canopy;
    final identity = boardIdentityOf(forum);
    final last = forum.lastPostAt == null
        ? ''
        : ' · ${forumRelativeTime(forum.lastPostAt)}';
    final counts =
        '${_count(forum.topicCount, 'topic')} · '
        '${_count(forum.postCount, 'post')}$last';
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      // One label for the row; the visible texts are excluded below so they
      // are not announced a second time.
      semanticLabel: [
        forum.title,
        if (forum.description.isNotEmpty) forum.description,
        counts,
        if (forum.hasUnread) 'unread',
      ].join(', '),
      child: ExcludeSemantics(
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: 12,
          ),
          child: Row(
            children: [
              CanopyAccentTile(
                icon: identity.icon,
                emoji: identity.emoji,
                tone: identity.tone.colorOf(canopy),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      forum.title,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (forum.description.isNotEmpty)
                      Text(
                        forum.description,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.bodySm.copyWith(
                          color: canopy.ink2,
                        ),
                      ),
                    const SizedBox(height: 2),
                    Text(
                      counts,
                      style: AppTypography.label.copyWith(color: canopy.ink3),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              if (forum.hasUnread) ...[
                SizedBox.square(
                  dimension: 8,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: canopy.leaf,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
              ],
              Icon(LucideIcons.chevronRight, size: 18, color: canopy.ink3),
            ],
          ),
        ),
      ),
    );
  }
}
