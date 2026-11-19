import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../shared/widgets/canopy_accents.dart';
import '../../../shared/widgets/canopy_surfaces.dart';
import '../forum_format.dart';
import '../models/models.dart';
import 'author_identity.dart';
import 'forum_style.dart';

/// Padding of one topic row, shared by [TopicCard] and [TopicRow] so both
/// put the avatar and the title on the same edges.
const EdgeInsets _rowPadding = EdgeInsets.symmetric(
  horizontal: AppSpacing.md,
  vertical: 12,
);

/// Radius of the leading avatar; with [_avatarGap] it sets the text edge.
const double _avatarRadius = 17;
const double _avatarGap = 12;

/// A topic as a card of its own (bookmarks). The same row as [TopicRow], on
/// its own surface.
class TopicCard extends StatelessWidget {
  const TopicCard({
    super.key,
    required this.topic,
    this.onTap,
    this.onAuthorTap,
  });

  final ForumTopicListItem topic;
  final VoidCallback? onTap;

  /// Called when the author's name is tapped — the caller navigates to
  /// the author's public profile. `null` (or a deleted author) renders no
  /// tap affordance at all (see [AuthorIdentity]).
  final VoidCallback? onAuthorTap;

  @override
  Widget build(BuildContext context) {
    return CanopyCard(
      onTap: onTap,
      padding: _rowPadding,
      child: _TopicRowContent(topic: topic, onAuthorTap: onAuthorTap),
    );
  }
}

/// A topic as one row of a grouped list (a board's topics): no surface of
/// its own, a `surface3` highlight while pressed.
class TopicRow extends StatelessWidget {
  const TopicRow({
    super.key,
    required this.topic,
    this.onTap,
    this.onAuthorTap,
  });

  final ForumTopicListItem topic;
  final VoidCallback? onTap;
  final VoidCallback? onAuthorTap;

  @override
  Widget build(BuildContext context) {
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      child: Padding(
        padding: _rowPadding,
        child: _TopicRowContent(topic: topic, onAuthorTap: onAuthorTap),
      ),
    );
  }
}

/// The layout every topic row shares. Three fixed edges, whatever the topic's
/// state: the avatar, the text (title, then author and status beneath it) and
/// a trailing column (time over reply count). Status never sits in front of
/// the title, so every title starts on the same edge.
class _TopicRowContent extends StatelessWidget {
  const _TopicRowContent({required this.topic, this.onAuthorTap});

  final ForumTopicListItem topic;
  final VoidCallback? onAuthorTap;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final time = forumListTime(topic.lastPostAt);
    final meta = forumMeta(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // The name beside it is the label, so the disc is silent to a screen
        // reader; a tap on it opens the author like a tap on the name.
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: topic.author.isDeleted ? null : onAuthorTap,
          child: ExcludeSemantics(
            child: AuthorAvatar(author: topic.author, radius: _avatarRadius),
          ),
        ),
        const SizedBox(width: _avatarGap),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                topic.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: forumItemTitle(context),
              ),
              const SizedBox(height: AppSpacing.xs),
              // A Wrap: at large text the status drops below the name
              // instead of squeezing it.
              Wrap(
                spacing: 10,
                runSpacing: 2,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  AuthorIdentity(
                    author: topic.author,
                    onTap: onAuthorTap,
                    showAvatar: false,
                    showTrustBadge: false,
                    nameStyle: AppTypography.bodySm.copyWith(
                      color: canopy.ink2,
                    ),
                  ),
                  if (topic.isPinned)
                    _Status(
                      icon: LucideIcons.pin,
                      label: 'Pinned',
                      color: canopy.ink2,
                    ),
                  if (topic.isLocked)
                    _Status(
                      icon: LucideIcons.lock,
                      label: 'Locked',
                      color: canopy.ink2,
                    ),
                  if (topic.isSolved)
                    _Status(
                      icon: LucideIcons.circleCheck,
                      label: 'Solved',
                      color: canopy.leaf,
                    ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(width: _avatarGap),
        // Dense chrome: capped so a long date at a large text size cannot
        // take the title's width.
        MediaQuery.withClampedTextScaling(
          maxScaleFactor: 1.3,
          child: Padding(
            // Sits the detail text on the title's first line.
            padding: const EdgeInsets.only(top: 3),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (topic.isUnread) ...[
                      Semantics(
                        label: 'Unread',
                        child: SizedBox.square(
                          dimension: 8,
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              color: canopy.clay,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                      ),
                      if (time.isNotEmpty) const SizedBox(width: 6),
                    ],
                    if (time.isNotEmpty) Text(time, style: meta),
                  ],
                ),
                const SizedBox(height: 6),
                Semantics(
                  label:
                      '${topic.replyCount} '
                      '${topic.replyCount == 1 ? 'reply' : 'replies'}',
                  child: ExcludeSemantics(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          LucideIcons.messageCircle,
                          size: 14,
                          color: canopy.ink2,
                        ),
                        const SizedBox(width: 4),
                        Text('${topic.replyCount}', style: meta),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// A status word with its icon, in the meta line ("Solved", "Pinned").
class _Status extends StatelessWidget {
  const _Status({required this.icon, required this.label, required this.color});

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        ExcludeSemantics(child: Icon(icon, size: 13, color: color)),
        const SizedBox(width: 4),
        // Flexible: in a very narrow column the word wraps, never clips.
        Flexible(
          child: Text(
            label,
            style: AppTypography.micro.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}
