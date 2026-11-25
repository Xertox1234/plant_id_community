import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../core/theme/app_typography.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import '../utils/board_identity.dart';
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

/// Corner radius of a member avatar [diameter] points wide. Avatars are
/// rounded squares, matching the app's square icon tiles (`CanopyAccentTile`
/// is 12 on 40): a 34pt avatar gets ~10pt corners. Every avatar, its ring and
/// its loading placeholder use this, so the shape stays one shape.
BorderRadius forumAvatarRadius(double diameter) =>
    BorderRadius.circular(diameter * 0.3);

/// The fill behind an author's initial: one of the four Canopy accents,
/// picked from the username with the web's stable hash so a member keeps one
/// colour everywhere, at 22% over `surface3`. Opaque on purpose: clusters
/// overlap avatars, and a translucent fill would show the one beneath.
/// A deleted author keeps the neutral `surface3`.
///
/// Contrast of `onSurface` on these fills (computed from the token values):
/// 6.0–6.7:1 dark, 9.8–10.1:1 light.
Color forumAvatarFill(BuildContext context, ForumAuthor author) {
  final canopy = context.canopy;
  if (author.isDeleted) return canopy.surface3;
  final tone = CanopyTone
      .values[webHashString(author.username) % CanopyTone.values.length];
  return Color.alphaBlend(
    tone.colorOf(canopy).withValues(alpha: 0.22),
    canopy.surface3,
  );
}

/// An author's avatar image, or their initial on a toned square when they
/// have none. Public so the DM inbox (todo 339) can lead a conversation row
/// with the same avatar rendering as every post.
///
/// [radius] is half the side, as it was when this was a `CircleAvatar`.
class AuthorAvatar extends StatelessWidget {
  const AuthorAvatar({super.key, required this.author, this.radius = 16});
  final ForumAuthor author;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final side = radius * 2;
    final shape = forumAvatarRadius(side);
    final avatar = author.avatar;
    if (avatar != null && avatar.isNotEmpty) {
      return SizedBox.square(
        dimension: side,
        child: DecoratedBox(
          decoration: BoxDecoration(
            // Neutral while the image loads, or if it never does.
            color: context.canopy.surface3,
            borderRadius: shape,
            image: DecorationImage(
              image: CachedNetworkImageProvider(avatar),
              fit: BoxFit.cover,
            ),
          ),
        ),
      );
    }
    final initial = author.name.isNotEmpty
        ? author.name.characters.first.toUpperCase()
        : '?';
    return SizedBox.square(
      dimension: side,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: forumAvatarFill(context, author),
          borderRadius: shape,
        ),
        child: Center(
          // The letter is sized to the square, not to the reader's text
          // scale (as CircleAvatar did): scaled, it would spill out of a
          // 20pt avatar at 2.0x. The name beside it carries the scale.
          child: MediaQuery.withNoTextScaling(
            child: Text(
              initial,
              // Geist, not the mono label face: an "I" in mono reads as a
              // glyph from another font beside the name it stands for.
              // The initial grows with the square (11pt at the smallest, as
              // before) so a 56pt profile avatar does not carry an 11pt
              // letter.
              style: AppTypography.micro.copyWith(
                fontSize: (radius * 0.7).clamp(11.0, 24.0),
                color: theme.colorScheme.onSurface,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
