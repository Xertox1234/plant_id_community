import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import 'trust_badge.dart';

/// Shared tappable author identity: avatar + name + trust badge. Used by
/// both `PostCard` and `TopicCard` so the two stop duplicating their own
/// inline author rendering.
///
/// Renders with **no `InkWell` at all** (not an attached no-op handler) when
/// [onTap] is null or [author] is deleted — more directly testable
/// (`find.byType(InkWell)` findsNothing) than a handler that early-returns.
///
/// This widget does not navigate itself — it only exposes [onTap], matching
/// how `TopicCard.onTap`/`PostCard.onEdit` already work (dumb widgets,
/// navigation owned by the screen).
class AuthorIdentity extends StatelessWidget {
  const AuthorIdentity({
    super.key,
    required this.author,
    this.onTap,
    this.avatarRadius = 16,
    this.nameStyle,
  });

  final ForumAuthor author;
  final VoidCallback? onTap;
  final double avatarRadius;
  final TextStyle? nameStyle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final content = Row(
      // Required, not optional: TopicCard embeds this inside a Flexible
      // alongside stat chips and a Spacer. A default MainAxisSize.max Row
      // would claim its entire flex share regardless of name length and
      // disturb that layout.
      mainAxisSize: MainAxisSize.min,
      children: [
        _Avatar(author: author, radius: avatarRadius),
        const SizedBox(width: AppSpacing.sm),
        Flexible(
          child: Text(
            author.name,
            overflow: TextOverflow.ellipsis,
            style:
                nameStyle ??
                theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
        ),
        const SizedBox(width: AppSpacing.xs),
        TrustBadge(author.trustLevel),
      ],
    );

    final canTap = onTap != null && !author.isDeleted;
    return canTap
        ? InkWell(
            borderRadius: BorderRadius.circular(AppSpacing.rXs),
            onTap: onTap,
            child: content,
          )
        : content;
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.author, required this.radius});
  final ForumAuthor author;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final avatar = author.avatar;
    if (avatar != null && avatar.isNotEmpty) {
      return CircleAvatar(
        radius: radius,
        backgroundImage: CachedNetworkImageProvider(avatar),
      );
    }
    final initial = author.name.isNotEmpty
        ? author.name.characters.first.toUpperCase()
        : '?';
    return CircleAvatar(
      radius: radius,
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
