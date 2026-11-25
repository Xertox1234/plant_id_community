import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../models/models.dart';
import 'author_identity.dart';

/// A compact horizontal strip of the forum's highest-trust members with a
/// presence dot on each who is online (`GET users/experts/`, todo 301;
/// todo 341 wave 4). The app had no experts surface before this — it lives
/// on the forum home. Tapping opens the member's profile via [onTap].
class ForumExpertsStrip extends StatelessWidget {
  const ForumExpertsStrip({super.key, required this.experts, this.onTap});

  final List<ForumExpert> experts;
  final void Function(ForumExpert expert)? onTap;

  @override
  Widget build(BuildContext context) {
    if (experts.isEmpty) return const SizedBox.shrink();
    // As tall as a tile and no taller: 4 + avatar + 4 + one line of the name
    // at the reader's text size + 4. A fixed height left a hole under the
    // names at 1.0x and clipped them when text was enlarged.
    final nameLine = MediaQuery.textScalerOf(
      context,
    ).scale(AppTypography.meta.fontSize! * AppTypography.meta.height!);
    return SizedBox(
      height: AppSpacing.xs * 3 + _avatarRadius * 2 + nameLine,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: experts.length,
        separatorBuilder: (_, _) => const SizedBox(width: AppSpacing.md),
        itemBuilder: (context, index) {
          final expert = experts[index];
          final onTap = this.onTap;
          return _ExpertTile(
            expert: expert,
            onTap: onTap == null || expert.author.isDeleted
                ? null
                : () => onTap(expert),
          );
        },
      ),
    );
  }
}

/// 40pt avatars, the same size as a forum row's tile.
const double _avatarRadius = 20;

class _ExpertTile extends StatelessWidget {
  const _ExpertTile({required this.expert, this.onTap});

  final ForumExpert expert;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final author = expert.author;
    return Semantics(
      label: '${author.name}${expert.online ? ', online' : ''}',
      button: onTap != null,
      // excludeSemantics drops the InkWell's own tap action, so the node
      // must carry it or a screen reader's double-tap does nothing.
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppSpacing.rSm),
        onTap: onTap,
        // Left-aligned and as wide as the name, so the first avatar starts on
        // the page margin and a name is not cut at 72pt.
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 48, maxWidth: 140),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: AppSpacing.xs),
              Stack(
                clipBehavior: Clip.none,
                children: [
                  AuthorAvatar(author: author, radius: _avatarRadius),
                  if (expert.online)
                    Positioned(right: -1, bottom: -1, child: _OnlineDot()),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                author.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                // ink2, not ink3: the strip sits on the bare ground, where
                // light-mode ink3 is 3.3:1 (spec §5.1).
                style: AppTypography.meta.copyWith(color: context.canopy.ink2),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The presence marker: a primary-colour disc ringed in the ground colour
/// (the experts strip sits directly on the ground) so it reads against any
/// avatar. Exposed for tests via its key.
class _OnlineDot extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      key: const Key('forum-online-dot'),
      width: 14,
      height: 14,
      decoration: BoxDecoration(
        color: scheme.primary,
        shape: BoxShape.circle,
        border: Border.all(color: context.canopy.ground, width: 2),
      ),
    );
  }
}
