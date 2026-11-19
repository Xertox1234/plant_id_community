import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_accents.dart';
import '../../forum_format.dart';
import '../../models/models.dart';
import '../../utils/board_identity.dart';
import '../forum_style.dart';

/// Gap between one category and the next.
const double _categoryGap = forumHomeSectionGap;

/// How long a category's card takes to open or close, as the activity card.
const Duration _collapseDuration = Duration(milliseconds: 250);

/// The forum index: per category a header, then one grouped card of its
/// forums. The whole row is the tap target (>= 48pt), and its press feedback
/// is a `surface3` highlight rather than a scale (design spec §8.1).
///
/// Locked forums and links are only drawn when [onLockedTap] / [onLinkTap] are
/// given, so with both a category of locked forums or links only still draws;
/// a category with nothing left to draw is skipped. Categories collapse
/// only when [onToggleCollapse] is given: then each header is the toggle,
/// and a category in [collapsed] draws its header only. Ids in [collapsed]
/// that match no category are ignored.
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
    final reduce = MediaQuery.disableAnimationsOf(context);
    for (final category in categories) {
      final forums = [
        for (final f in category.forums)
          if (!f.isLocked || onLockedTap != null) f,
      ];
      final showLinks = onLinkTap != null && category.links.isNotEmpty;
      if (forums.isEmpty && !showLinks) continue;
      final toggle = onToggleCollapse;
      // Without a toggle nothing collapses: ids in [collapsed] are ignored.
      final isCollapsed = toggle != null && collapsed.contains(category.id);
      final card = CanopyGroupedCard(
        rows: [
          for (final forum in forums)
            if (forum.isLocked)
              _LockedRow(forum: forum, onTap: () => onLockedTap?.call(forum))
            else
              _ForumRow(forum: forum, onTap: () => onForumTap(forum)),
          if (showLinks)
            for (final link in category.links)
              _LinkRow(link: link, onTap: () => onLinkTap!(link)),
        ],
      );
      blocks.add(
        Padding(
          key: ValueKey('category-${category.id}'),
          padding: EdgeInsets.only(top: blocks.isEmpty ? 0 : _categoryGap),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (toggle == null) ...[
                _CategoryHeader(category: category),
                card,
              ] else ...[
                _CollapsibleHeader(
                  category: category,
                  collapsed: isCollapsed,
                  onTap: () => toggle(category),
                ),
                // Collapsed, the card is not built at all. Under reduced
                // motion it is swapped without AnimatedSize, whose zero
                // duration asserts during layout.
                if (reduce)
                  if (!isCollapsed) card else const SizedBox.shrink()
                else
                  AnimatedSize(
                    duration: _collapseDuration,
                    curve: Easing.emphasizedDecelerate,
                    alignment: Alignment.topCenter,
                    child: isCollapsed
                        ? const SizedBox(width: double.infinity)
                        : card,
                  ),
              ],
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
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: forumHomeHeaderHeight),
      child: Align(
        alignment: AlignmentDirectional.centerStart,
        // Only the title is announced (as a header); the emoji's name is not.
        child: Semantics(
          header: true,
          label: category.title,
          excludeSemantics: true,
          child: Text(
            icon.isEmpty ? category.title : '$icon ${category.title}',
            style: AppTypography.h3.copyWith(
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}

/// A category header that collapses its card: the whole row is the toggle
/// (at least 48pt high), with a chevron that turns, and the unread dot while
/// the category is collapsed and has something unread. The title, its style
/// and spacing are [_CategoryHeader]'s.
class _CollapsibleHeader extends StatelessWidget {
  const _CollapsibleHeader({
    required this.category,
    required this.collapsed,
    required this.onTap,
  });

  final ForumCategory category;
  final bool collapsed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final icon = category.icon.trim();
    final reduce = MediaQuery.disableAnimationsOf(context);
    // The chevron sits on the same edge as the row chevrons in the card below.
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: AppSpacing.md),
      child: Semantics(
        header: true,
        child: CanopyPressable(
          onTap: onTap,
          expanded: !collapsed,
          semanticLabel:
              '${collapsed ? 'Expand' : 'Collapse'} ${category.title}',
          child: ExcludeSemantics(
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    icon.isEmpty ? category.title : '$icon ${category.title}',
                    style: AppTypography.h3.copyWith(
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                ),
                if (collapsed && category.hasUnread) ...[
                  const SizedBox(width: AppSpacing.sm),
                  SizedBox.square(
                    key: const ValueKey('category-unread-dot'),
                    dimension: 8,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: canopy.leaf,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                ],
                const SizedBox(width: AppSpacing.sm),
                AnimatedRotation(
                  turns: collapsed ? -0.25 : 0,
                  duration: reduce ? Duration.zero : _collapseDuration,
                  curve: Easing.emphasizedDecelerate,
                  child: Icon(
                    LucideIcons.chevronDown,
                    size: forumChevronSize,
                    color: canopy.ink2,
                  ),
                ),
              ],
            ),
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
    final canopy = context.canopy;
    final identity = boardIdentityOf(forum);
    final last = forum.lastPostAt == null
        ? ''
        : ' · ${forumListTime(forum.lastPostAt)}';
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CanopyAccentTile(
                icon: identity.icon,
                emoji: identity.emoji,
                tone: identity.tone.colorOf(canopy),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(forum.title, style: forumItemTitle(context)),
                    if (forum.description.isNotEmpty)
                      Text(
                        forum.description,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.bodySm.copyWith(
                          color: canopy.ink2,
                        ),
                      ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(counts, style: forumMeta(context)),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              // Level with the title's first line, not the row's middle.
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (forum.hasUnread) ...[
                      SizedBox.square(
                        key: const ValueKey('unread-dot'),
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
                    Icon(
                      LucideIcons.chevronRight,
                      size: forumChevronSize,
                      color: canopy.ink2,
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

/// A password forum still locked for the viewer (spec §7.4): the lock in the
/// tile, the title and description, nothing else. The feed still sends its
/// counts, last activity, unread flag and colour; none of them is shown.
class _LockedRow extends StatelessWidget {
  const _LockedRow({required this.forum, required this.onTap});

  final ForumBoard forum;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final identity = boardIdentityOf(forum);
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      semanticLabel: [
        forum.title,
        if (forum.description.isNotEmpty) forum.description,
        'password protected',
      ].join(', '),
      child: ExcludeSemantics(
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: 12,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CanopyAccentTile(
                icon: LucideIcons.lock,
                tone: identity.tone.colorOf(canopy),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(forum.title, style: forumItemTitle(context)),
                    if (forum.description.isNotEmpty)
                      Text(
                        forum.description,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.bodySm.copyWith(
                          color: canopy.ink2,
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

class _LinkRow extends StatelessWidget {
  const _LinkRow({required this.link, required this.onTap});

  final ForumLink link;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final tone = boardIdentity(link.slug).tone.colorOf(canopy);
    final clicks = link.clickCount;
    // Mirrors the web row: the count shows only for a tracked link.
    final label = link.trackClicks && clicks != null
        ? 'External link · ${_count(clicks, 'click')}'
        : 'External link';
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      semanticLabel: [
        link.title,
        if (link.description.isNotEmpty) link.description,
        label.replaceFirst(' · ', ', '),
      ].join(', '),
      child: ExcludeSemantics(
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: 12,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CanopyAccentTile(icon: LucideIcons.externalLink, tone: tone),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(link.title, style: forumItemTitle(context)),
                    if (link.description.isNotEmpty)
                      Text(
                        link.description,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.bodySm.copyWith(
                          color: canopy.ink2,
                        ),
                      ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(label, style: forumMeta(context)),
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
