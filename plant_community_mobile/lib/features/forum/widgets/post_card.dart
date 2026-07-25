import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_format.dart';
import '../models/models.dart';
import 'forum_body_renderer.dart';
import 'reaction_pills.dart';
import 'trust_badge.dart';

/// A single forum post: author identity, moderation/edited markers, the
/// rendered StreamField body, and reactions.
class PostCard extends StatelessWidget {
  const PostCard({
    super.key,
    required this.post,
    this.onReact,
    this.onOpenLink,
  });

  final ForumPost post;

  /// Non-null when the viewer may react (logged in). Called with the type.
  final void Function(String type)? onReact;
  final void Function(String href)? onOpenLink;

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
                _Avatar(author: author),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              author.name,
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xs),
                          TrustBadge(author.trustLevel),
                        ],
                      ),
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

class _Avatar extends StatelessWidget {
  const _Avatar({required this.author});
  final ForumAuthor author;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final avatar = author.avatar;
    if (avatar != null && avatar.isNotEmpty) {
      return CircleAvatar(
        radius: 16,
        backgroundImage: CachedNetworkImageProvider(avatar),
      );
    }
    final initial = author.name.isNotEmpty
        ? author.name.characters.first.toUpperCase()
        : '?';
    return CircleAvatar(
      radius: 16,
      backgroundColor: theme.colorScheme.primaryContainer,
      child: Text(
        initial,
        style: TextStyle(
          color: theme.colorScheme.onPrimaryContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
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
