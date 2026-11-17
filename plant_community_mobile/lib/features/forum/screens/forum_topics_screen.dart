import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/routing/main_shell.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../services/auth_service.dart';
import '../../../shared/widgets/canopy_accents.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../utils/board_identity.dart';
import '../widgets/topic_card.dart';
import 'forum_composer_screen.dart';

/// Topics within a board: the board's identity (tile, description, counts),
/// then its topics as one grouped list, cursor-paginated with a "Load more"
/// footer.
class ForumTopicsScreen extends ConsumerWidget {
  const ForumTopicsScreen({
    super.key,
    required this.boardSlug,
    this.boardTitle,
  });

  final String boardSlug;
  final String? boardTitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final topicsAsync = ref.watch(boardTopicsProvider(boardSlug));
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    // Decoration only: the description and counts appear when the boards
    // list is known (it is, coming from the forum home) and are simply
    // absent while it loads or if it failed.
    final board = ref.watch(
      boardsProvider.select(
        (boards) => boards.value?.where((b) => b.slug == boardSlug).firstOrNull,
      ),
    );
    final title = boardTitle ?? board?.title ?? 'Topics';
    final identity = board != null
        ? boardIdentityOf(board)
        : boardIdentity(boardSlug, fallbackLabel: title);
    final tone = identity.tone.colorOf(context.canopy);

    // Both: the header's counts come from the boards list, so a refresh that
    // only refetched the topics would leave "7 topics" above eight rows.
    void refresh() {
      ref.invalidate(boardTopicsProvider(boardSlug));
      ref.invalidate(categoriesProvider);
    }

    return Scaffold(
      appBar: AppBar(
        centerTitle: false,
        titleSpacing: 0,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CanopyAccentTile(
              icon: identity.icon,
              emoji: identity.emoji,
              tone: tone,
              size: 30,
            ),
            const SizedBox(width: 10),
            Flexible(
              child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
          ],
        ),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => refresh(),
          // Always a ListView, whatever the state, so pull-to-refresh works
          // on the skeleton, the error and the empty board too.
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.xs,
              AppSpacing.md,
              // The last row ends clear of the "New topic" button.
              AppSpacing.md + MainShell.fabClearance,
            ),
            children: [
              if (board != null) _BoardIntro(board: board),
              topicsAsync.when(
                loading: () => const _TopicsSkeleton(),
                error: (error, _) => _ErrorRetry(
                  message: 'Could not load topics.',
                  onRetry: refresh,
                ),
                data: (paged) => _TopicsList(
                  paged: paged,
                  emptyIcon: identity.icon,
                  emptyTone: tone,
                  onOpenTopic: (topic) => context.pushNamed(
                    'forumTopic',
                    pathParameters: {'id': '${topic.id}'},
                    extra: topic.title,
                  ),
                  onLoadMore: () => ref
                      .read(boardTopicsProvider(boardSlug).notifier)
                      .loadMore(),
                ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: isAuthenticated
          ? FloatingActionButton.extended(
              onPressed: () => _openComposer(context, ref),
              icon: const Icon(LucideIcons.plus, size: 20),
              label: const Text('New topic'),
            )
          : null,
    );
  }

  Future<void> _openComposer(BuildContext context, WidgetRef ref) async {
    final result = await context.pushNamed<bool>(
      'forumCompose',
      extra: ForumComposeArgs.topic(
        boardSlug: boardSlug,
        boardTitle: boardTitle,
      ),
    );
    if (result == true) {
      ref.invalidate(boardTopicsProvider(boardSlug));
      ref.invalidate(categoriesProvider);
    }
  }
}

String _count(int n, String singular) => '$n $singular${n == 1 ? '' : 's'}';

/// What the board is for and how busy it is, under the title.
class _BoardIntro extends StatelessWidget {
  const _BoardIntro({required this.board});

  final ForumBoard board;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (board.description.isNotEmpty) ...[
            Text(
              board.description,
              style: AppTypography.bodySm.copyWith(color: canopy.ink2),
            ),
            const SizedBox(height: 6),
          ],
          Text(
            '${_count(board.topicCount, 'topic')} · '
            '${_count(board.postCount, 'post')}',
            style: AppTypography.label.copyWith(color: canopy.ink3),
          ),
        ],
      ),
    );
  }
}

class _TopicsList extends StatelessWidget {
  const _TopicsList({
    required this.paged,
    required this.emptyIcon,
    required this.emptyTone,
    required this.onOpenTopic,
    required this.onLoadMore,
  });

  final PagedList<ForumTopicListItem> paged;
  final IconData emptyIcon;
  final Color emptyTone;
  final void Function(ForumTopicListItem topic) onOpenTopic;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty) {
      final canopy = context.canopy;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl2),
        child: Column(
          children: [
            CanopyAccentTile(icon: emptyIcon, tone: emptyTone, size: 48),
            const SizedBox(height: AppSpacing.md),
            Text(
              'No topics yet',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Be the first to post.',
              style: AppTypography.bodySm.copyWith(color: canopy.ink2),
            ),
          ],
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CanopyGroupedCard(
          rows: [
            for (final topic in paged.items)
              TopicRow(
                key: ValueKey(topic.id),
                topic: topic,
                onTap: () => onOpenTopic(topic),
                onAuthorTap: () => context.pushNamed(
                  'forumUserProfile',
                  pathParameters: {'username': topic.author.username},
                ),
              ),
          ],
        ),
        if (paged.hasMore)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.sm),
            child: _LoadMoreButton(
              isLoading: paged.isLoadingMore,
              onLoadMore: onLoadMore,
            ),
          ),
      ],
    );
  }
}

/// Six rows shaped like topic rows: an avatar disc and two lines.
class _TopicsSkeleton extends StatelessWidget {
  const _TopicsSkeleton();

  @override
  Widget build(BuildContext context) {
    final fill = context.canopy.surface3;
    Widget bar(double widthFactor, double height) => FractionallySizedBox(
      alignment: Alignment.centerLeft,
      widthFactor: widthFactor,
      child: SizedBox(
        height: height,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: fill,
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
          ),
        ),
      ),
    );
    Widget row(double width) => Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: 14,
      ),
      child: Row(
        children: [
          SizedBox.square(
            dimension: 34,
            child: DecoratedBox(
              decoration: BoxDecoration(color: fill, shape: BoxShape.circle),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                bar(width, 12),
                const SizedBox(height: 8),
                bar(0.35, 8),
              ],
            ),
          ),
        ],
      ),
    );
    return Semantics(
      container: true,
      label: 'Loading topics',
      child: ExcludeSemantics(
        child: CanopyGroupedCard(
          rows: [
            for (final w in [0.8, 0.55, 0.7, 0.9, 0.6, 0.75]) row(w),
          ],
        ),
      ),
    );
  }
}

class _LoadMoreButton extends StatelessWidget {
  const _LoadMoreButton({required this.isLoading, required this.onLoadMore});
  final bool isLoading;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Center(
        child: isLoading
            ? const CircularProgressIndicator()
            : OutlinedButton(
                onPressed: () async {
                  try {
                    await onLoadMore();
                  } catch (_) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Could not load more.')),
                      );
                    }
                  }
                },
                child: const Text('Load more'),
              ),
      ),
    );
  }
}

class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl2),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(message),
          const SizedBox(height: AppSpacing.sm),
          OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
