import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_format.dart';
import '../models/models.dart';
import 'author_identity.dart';

/// A topic row in a board listing: title, author, reply/view stats, and
/// pinned/locked/unread markers.
class TopicCard extends StatelessWidget {
  const TopicCard({
    super.key,
    required this.topic,
    this.onTap,
    this.onAuthorTap,
  });

  final ForumTopicListItem topic;
  final VoidCallback? onTap;

  /// Called when the author identity is tapped — the caller navigates to
  /// the author's public profile. `null` (or a deleted author) renders no
  /// tap affordance at all (see [AuthorIdentity]).
  final VoidCallback? onAuthorTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.rMd),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (topic.isPinned)
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpacing.xs),
                      child: Icon(
                        Icons.push_pin,
                        size: 15,
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  if (topic.isLocked)
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpacing.xs),
                      child: Icon(
                        Icons.lock_outline,
                        size: 15,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  if (topic.isSolved)
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpacing.xs),
                      child: Icon(
                        Icons.check_circle,
                        size: 15,
                        color: theme.colorScheme.secondary,
                        semanticLabel: 'Solved',
                      ),
                    ),
                  Expanded(
                    child: Text(
                      topic.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (topic.isUnread) ...[
                    const SizedBox(width: AppSpacing.xs),
                    _UnreadBadge(),
                  ],
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Row(
                children: [
                  Flexible(
                    child: AuthorIdentity(
                      author: topic.author,
                      onTap: onAuthorTap,
                      avatarRadius: 12,
                      showTrustBadge: false,
                      nameStyle: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  _Stat(
                    icon: Icons.chat_bubble_outline,
                    value: topic.replyCount,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  _Stat(
                    icon: Icons.remove_red_eye_outlined,
                    value: topic.viewCount,
                  ),
                  const Spacer(),
                  if (forumRelativeTime(topic.lastPostAt).isNotEmpty)
                    Text(
                      forumRelativeTime(topic.lastPostAt),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.icon, required this.value});
  final IconData icon;
  final int value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurfaceVariant;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 2),
        Text(
          '$value',
          style: theme.textTheme.labelSmall?.copyWith(color: color),
        ),
      ],
    );
  }
}

class _UnreadBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: theme.colorScheme.primary,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Text(
        'New',
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onPrimary,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
