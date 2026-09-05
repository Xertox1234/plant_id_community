import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
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
    return SizedBox(
      height: 92,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: experts.length,
        separatorBuilder: (_, _) => const SizedBox(width: AppSpacing.sm),
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

class _ExpertTile extends StatelessWidget {
  const _ExpertTile({required this.expert, this.onTap});

  final ForumExpert expert;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final author = expert.author;
    return Semantics(
      label: '${author.name}${expert.online ? ', online' : ''}',
      button: onTap != null,
      excludeSemantics: true,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppSpacing.rSm),
        onTap: onTap,
        child: SizedBox(
          width: 72,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: AppSpacing.xs),
              Stack(
                clipBehavior: Clip.none,
                children: [
                  AuthorAvatar(author: author, radius: 24),
                  if (expert.online)
                    Positioned(right: -1, bottom: -1, child: _OnlineDot()),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                author.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: theme.textTheme.labelSmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The presence marker: a primary-colour disc ringed in the surface colour
/// so it reads against any avatar. Exposed for tests via its key.
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
        border: Border.all(color: scheme.surface, width: 2),
      ),
    );
  }
}
