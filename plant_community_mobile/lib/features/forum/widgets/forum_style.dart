import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../shared/widgets/canopy_accents.dart';

/// The forum's shared look, so each screen and section does not pick its
/// own: one header row, one item title, one detail style, one chevron size.

/// Height of every section header row. The collapsible category headers are
/// tap targets and need 48pt, so the plain ones match it and all headers sit
/// the same distance from the content above and below them.
const double forumHomeHeaderHeight = 48;

/// Gap above a header row. With the title centred in [forumHomeHeaderHeight]
/// this puts about 32pt of air above the title's text.
const double forumHomeSectionGap = 20;

/// Size of every trailing chevron in the forum.
const double forumChevronSize = 20;

/// Counts, dates and other details: Geist, never Geist Mono, on `ink2` so it
/// passes 4.5:1 on a card in both modes. Tabular figures keep columns of
/// numbers from shifting.
TextStyle forumMeta(BuildContext context) => AppTypography.meta.copyWith(
  color: context.canopy.ink2,
  fontFeatures: const [FontFeature.tabularFigures()],
);

/// The title of a row or card: Geist 15/600, the same step the Home tab's
/// feature cards use.
TextStyle? forumItemTitle(BuildContext context) =>
    Theme.of(context).textTheme.titleMedium;

/// A plain (not collapsible) section heading, announced as a header.
class ForumHomeHeader extends StatelessWidget {
  const ForumHomeHeader(this.title, {super.key});

  final String title;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: forumHomeHeaderHeight),
      child: Align(
        alignment: AlignmentDirectional.centerStart,
        child: Semantics(
          header: true,
          child: Text(
            title,
            style: AppTypography.h3.copyWith(
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}

/// The forum's plain list row, for use inside a `CanopyGroupedCard`: an
/// optional leading icon, the item title, an optional excerpt, a detail line
/// and the trailing chevron, all top-aligned. Search results and a member's
/// recent activity share it so a topic looks the same wherever it is listed.
class ForumListRow extends StatelessWidget {
  const ForumListRow({
    super.key,
    required this.title,
    required this.onTap,
    this.meta = '',
    this.body = '',
    this.icon,
  });

  final String title;
  final String meta;
  final String body;
  final IconData? icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final icon = this.icon;
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: 12,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (icon != null) ...[
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: Icon(icon, size: forumChevronSize, color: canopy.ink2),
              ),
              const SizedBox(width: AppSpacing.md),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: forumItemTitle(context),
                  ),
                  if (body.isNotEmpty)
                    Text(
                      body,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.bodySm.copyWith(color: canopy.ink2),
                    ),
                  if (meta.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(meta, style: forumMeta(context)),
                  ],
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Padding(
              padding: const EdgeInsets.only(top: 1),
              child: Icon(
                LucideIcons.chevronRight,
                size: forumChevronSize,
                color: canopy.ink2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The forum's empty state: an accent tile, one title and an optional line
/// under it, centred. One shape for every list that can be empty.
class ForumEmptyState extends StatelessWidget {
  const ForumEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.body = '',
    this.tone,
  });

  final IconData icon;
  final String title;
  final String body;

  /// The tile's accent; the leaf green when not given.
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xl2,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CanopyAccentTile(icon: icon, tone: tone ?? canopy.leaf, size: 48),
          const SizedBox(height: AppSpacing.md),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (body.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              body,
              textAlign: TextAlign.center,
              style: AppTypography.bodySm.copyWith(color: canopy.ink2),
            ),
          ],
        ],
      ),
    );
  }
}
