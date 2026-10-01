import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../models/models.dart';
import 'author_identity.dart';

/// Overlapping avatars for a group conversation's first few members (todo
/// 350) — the inbox row's leading slot, where a direct thread shows the
/// other member's single [AuthorAvatar]. Shows at most [max] avatars and
/// folds the rest into a "+N" disc of the same size.
///
/// Mirrors the web `ParticipantStack` (todo 463): the viewer, named by
/// [viewerUsername], is left out — they know what they look like — and the
/// semantics label counts only the others. While the viewer is unknown (the
/// account profile is loading or failed) every member is shown, as on web.
class AuthorAvatarCluster extends StatelessWidget {
  const AuthorAvatarCluster({
    super.key,
    required this.authors,
    this.viewerUsername,
    this.radius = 14,
    this.max = 3,
  });

  /// Every member, the viewer included (the serializer's `participants`).
  final List<ForumAuthor> authors;
  final String? viewerUsername;
  final double radius;
  final int max;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final viewer = viewerUsername;
    final others = viewer == null
        ? authors
        : [
            for (final a in authors)
              if (a.username != viewer) a,
          ];
    final shown = others.take(max).toList(growable: false);
    final extra = others.length - shown.length;
    final slots = shown.length + (extra > 0 ? 1 : 0);
    if (shown.isEmpty) {
      // Nobody else to draw: the viewer is the only member left, or the
      // roster is empty. The bare glyph says nothing to a screen reader, so
      // it carries the same count the avatar stack does (todo 486).
      return Semantics(
        label: viewer == null ? 'No members' : 'No other members',
        excludeSemantics: true,
        child: CircleAvatar(
          radius: radius + 6,
          // Opaque, matching AuthorIdentity's initial disc: avatars overlap by
          // a quarter here, and a translucent disc shows the one beneath it.
          backgroundColor: theme.colorScheme.surfaceContainerHigh,
          child: Icon(
            LucideIcons.users,
            color: theme.colorScheme.onSurface,
            size: radius * 1.4,
          ),
        ),
      );
    }
    // Each avatar overlaps the previous by a quarter so three fit the same
    // 40 px slot a single radius-20 avatar takes.
    final step = radius * 1.5;
    final size = radius * 2 + 4;
    final count = others.length;
    return Semantics(
      label: viewer == null
          ? '$count ${count == 1 ? 'member' : 'members'}'
          : '$count other ${count == 1 ? 'member' : 'members'}',
      // The initials inside each avatar are decoration here; without this a
      // screen reader would read "A B C" before (or instead of) the count.
      excludeSemantics: true,
      child: SizedBox(
        width: size + step * (slots - 1),
        height: size,
        child: Stack(
          children: [
            for (var i = 0; i < shown.length; i++)
              Positioned(
                left: i * step,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: theme.colorScheme.surface,
                      width: 2,
                    ),
                  ),
                  child: AuthorAvatar(author: shown[i], radius: radius),
                ),
              ),
            if (extra > 0)
              Positioned(
                left: shown.length * step,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: theme.colorScheme.surface,
                      width: 2,
                    ),
                  ),
                  child: CircleAvatar(
                    radius: radius,
                    // Opaque for the same reason as the empty-roster disc.
                    backgroundColor: theme.colorScheme.surfaceContainerHigh,
                    child: Text(
                      '+$extra',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurface,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
