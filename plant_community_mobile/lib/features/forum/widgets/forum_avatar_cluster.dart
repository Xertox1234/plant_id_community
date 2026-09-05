import 'package:flutter/material.dart';

import '../models/models.dart';
import 'author_identity.dart';

/// Overlapping avatars for a group conversation's first few members (todo
/// 350) — the inbox row's leading slot, where a direct thread shows the
/// other member's single [AuthorAvatar]. Shows at most [max] avatars.
class AuthorAvatarCluster extends StatelessWidget {
  const AuthorAvatarCluster({
    super.key,
    required this.authors,
    this.radius = 14,
    this.max = 3,
  });

  final List<ForumAuthor> authors;
  final double radius;
  final int max;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final shown = authors.take(max).toList(growable: false);
    if (shown.isEmpty) {
      return CircleAvatar(
        radius: radius + 6,
        backgroundColor: theme.colorScheme.primaryContainer,
        child: Icon(
          Icons.group,
          color: theme.colorScheme.onPrimaryContainer,
          size: radius * 1.4,
        ),
      );
    }
    // Each avatar overlaps the previous by a quarter so three fit the same
    // 40 px slot a single radius-20 avatar takes.
    final step = radius * 1.5;
    final size = radius * 2 + 4;
    return Semantics(
      label: '${authors.length} members',
      // The initials inside each avatar are decoration here; without this a
      // screen reader would read "A B C" before (or instead of) the count.
      excludeSemantics: true,
      child: SizedBox(
        width: size + step * (shown.length - 1),
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
          ],
        ),
      ),
    );
  }
}
