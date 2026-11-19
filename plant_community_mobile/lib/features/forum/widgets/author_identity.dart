import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../core/theme/app_typography.dart';

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
    this.showTrustBadge = true,
    this.showAvatar = true,
  });

  final ForumAuthor author;
  final VoidCallback? onTap;
  final double avatarRadius;
  final TextStyle? nameStyle;

  /// Whether to render the [TrustBadge] after the name. Defaults to `true`
  /// (matches `PostCard`). `TopicCard` passes `false`: a topic row's meta
  /// line carries the name and the topic's status, not the author's rank.
  final bool showTrustBadge;

  /// Whether to lead with the avatar. `TopicCard` passes `false`: its row
  /// already leads with the avatar, in a slot every row shares, and only the
  /// name belongs in the meta line.
  final bool showAvatar;

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
        if (showAvatar) ...[
          AuthorAvatar(author: author, radius: avatarRadius),
          const SizedBox(width: AppSpacing.sm),
        ],
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
        if (showTrustBadge) ...[
          const SizedBox(width: AppSpacing.xs),
          TrustBadge(author.trustLevel),
        ],
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

/// An author's avatar image, or their initial on a `primaryContainer` disc
/// when they have none. Public so the DM inbox (todo 339) can lead a
/// conversation row with the same avatar rendering as every post.
class AuthorAvatar extends StatelessWidget {
  const AuthorAvatar({super.key, required this.author, this.radius = 16});
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
    final ext = context.canopy;
    return CircleAvatar(
      radius: radius,
      backgroundColor: ext.surface3,
      child: Text(
        initial,
        // Geist, not the mono label face: an "I" in mono reads as a glyph
        // from another font beside the name it stands for.
        // The initial grows with the disc (11pt at the smallest, as before)
        // so a 56pt profile avatar does not carry an 11pt letter.
        style: AppTypography.micro.copyWith(
          fontSize: (radius * 0.7).clamp(11.0, 24.0),
          color: theme.colorScheme.onSurface,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
