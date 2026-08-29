import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_format.dart';
import '../models/models.dart';
import 'author_identity.dart';
import 'forum_body_renderer.dart';
import 'reaction_pills.dart';

/// A single forum post: author identity, moderation/edited markers, the
/// rendered StreamField body, and reactions.
class PostCard extends StatelessWidget {
  const PostCard({
    super.key,
    required this.post,
    this.onReact,
    this.onOpenLink,
    this.onEdit,
    this.onDelete,
    this.onAuthorTap,
  });

  final ForumPost post;

  /// Non-null when the viewer may react (logged in). Called with the type.
  final void Function(String type)? onReact;
  final void Function(String href)? onOpenLink;

  /// Called when Edit is chosen. The caller (not this widget) gates
  /// visibility on `post.canEdit` — never re-derive ownership here (todo
  /// 292 AC1); this widget only renders what its caller already decided.
  final VoidCallback? onEdit;

  /// Called when Delete is chosen, AFTER the caller's own confirmation —
  /// this widget does not confirm destructive actions itself.
  final VoidCallback? onDelete;

  /// Called when the author identity is tapped — the caller navigates to
  /// the author's public profile. `null` (or a deleted author) renders no
  /// tap affordance at all (see [AuthorIdentity]).
  final VoidCallback? onAuthorTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final author = post.author;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      AuthorIdentity(author: author, onTap: onAuthorTap),
                      if (forumRelativeTime(post.createdAt).isNotEmpty)
                        Text(
                          forumRelativeTime(post.createdAt),
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                    ],
                  ),
                ),
                if (post.isOpeningPost)
                  Icon(
                    Icons.push_pin_outlined,
                    size: 16,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                _PostMenu(post: post, onEdit: onEdit, onDelete: onDelete),
              ],
            ),
            if (post.isPending)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: _PendingChip(),
              ),
            const SizedBox(height: AppSpacing.sm),
            ForumBodyRenderer(post.body, onOpenLink: onOpenLink),
            if (post.isEdited)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: Text(
                  'edited',
                  style: theme.textTheme.labelSmall?.copyWith(
                    fontStyle: FontStyle.italic,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.sm),
            ReactionPills(
              counts: post.reactionCounts,
              reacted: post.reacted,
              onReact: onReact,
            ),
          ],
        ),
      ),
    );
  }
}

/// Overflow menu with Edit/Delete, each gated on its own `can*` flag (todo
/// 292 AC1) — never shown just because a callback exists. Absent entirely
/// when neither applies, so a viewer with no capability sees no menu at all.
class _PostMenu extends StatelessWidget {
  const _PostMenu({required this.post, this.onEdit, this.onDelete});

  final ForumPost post;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final showEdit = onEdit != null && post.canEdit;
    final showDelete = onDelete != null && post.canDelete;
    if (!showEdit && !showDelete) return const SizedBox.shrink();
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert, size: 20),
      tooltip: 'Post options',
      onSelected: (value) {
        if (value == 'edit') onEdit?.call();
        if (value == 'delete') onDelete?.call();
      },
      itemBuilder: (context) => [
        if (showEdit) const PopupMenuItem(value: 'edit', child: Text('Edit')),
        if (showDelete)
          const PopupMenuItem(value: 'delete', child: Text('Delete')),
      ],
    );
  }
}

class _PendingChip extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Text(
        'Awaiting moderation',
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onTertiaryContainer,
        ),
      ),
    );
  }
}
