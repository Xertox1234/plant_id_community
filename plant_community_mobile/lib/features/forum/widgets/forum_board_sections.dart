import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/widgets/canopy_accents.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import 'author_identity.dart';
import 'forum_style.dart';

/// The sections under a board's topic list. Each is absent (no header, no
/// gap) while it loads, when it has nothing to show and when its request
/// fails, so the list never ends in an empty frame.

/// How many rows each section shows.
const int _sectionRows = 3;

/// "Top contributors": the members with the most posts in THIS forum, with
/// their post counts. A tap opens the member's profile.
class ForumTopContributors extends ConsumerWidget {
  const ForumTopContributors({super.key, required this.boardSlug});

  final String boardSlug;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final viewer = ref.watch(forumViewerProvider);
    final contributors =
        ref.watch(boardContributorsProvider(boardSlug, viewer)).value ??
        const <ForumContributor>[];
    if (contributors.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: forumSectionGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const ForumSectionHeader('Top contributors'),
          CanopyGroupedCard(
            rows: [
              for (final c in contributors)
                _ContributorRow(
                  key: ValueKey(c.author.username),
                  contributor: c,
                  onTap: c.author.isDeleted
                      ? null
                      : () => context.pushNamed(
                          'forumUserProfile',
                          pathParameters: {'username': c.author.username},
                        ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ContributorRow extends StatelessWidget {
  const _ContributorRow({super.key, required this.contributor, this.onTap});

  final ForumContributor contributor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final author = contributor.author;
    final posts = contributor.postCount;
    final count = '$posts ${posts == 1 ? 'post' : 'posts'}';
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      semanticLabel: '${author.name}, $count',
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            ExcludeSemantics(child: AuthorAvatar(author: author, radius: 17)),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                author.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: forumItemTitle(context),
              ),
            ),
            const SizedBox(width: 12),
            Text(count, style: forumMeta(context)),
          ],
        ),
      ),
    );
  }
}

/// "Active discussions": the most recently active topics in the OTHER
/// forums (this forum's own are the list above), each with its forum's name.
class ForumActiveDiscussions extends ConsumerWidget {
  const ForumActiveDiscussions({super.key, required this.boardSlug});

  /// The forum being read; its topics are left out.
  final String boardSlug;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final viewer = ref.watch(forumViewerProvider);
    final recent =
        ref.watch(homeRecentTopicsProvider(viewer)).value ??
        const <ForumRecentTopic>[];
    final topics = [
      for (final t in recent)
        if (t.board.slug != boardSlug) t,
    ].take(_sectionRows).toList();
    if (topics.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: forumSectionGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const ForumSectionHeader('Active discussions'),
          CanopyGroupedCard(
            rows: [
              for (final t in topics)
                ForumListRow(
                  key: ValueKey(t.id),
                  title: t.title,
                  meta: [
                    t.board.title,
                    '${t.replyCount} ${t.replyCount == 1 ? 'reply' : 'replies'}',
                    if (forumListTime(t.lastPostAt).isNotEmpty)
                      forumListTime(t.lastPostAt),
                  ].join(' · '),
                  onTap: () => context.pushNamed(
                    'forumTopic',
                    pathParameters: {'id': '${t.id}'},
                    extra: t.title,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
