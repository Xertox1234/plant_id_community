import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/auth_service.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../widgets/topic_card.dart';
import 'forum_composer_screen.dart';

/// Topics within a board, cursor-paginated with a "Load more" footer.
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

    return Scaffold(
      appBar: AppBar(title: Text(boardTitle ?? 'Topics')),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => ref.invalidate(boardTopicsProvider(boardSlug)),
          child: topicsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => _ErrorRetry(
              message: 'Could not load topics.',
              onRetry: () => ref.invalidate(boardTopicsProvider(boardSlug)),
            ),
            data: (paged) => _TopicsList(
              paged: paged,
              onOpenTopic: (topic) => context.pushNamed(
                'forumTopic',
                pathParameters: {'id': '${topic.id}'},
                extra: topic.title,
              ),
              onLoadMore: () =>
                  ref.read(boardTopicsProvider(boardSlug).notifier).loadMore(),
            ),
          ),
        ),
      ),
      floatingActionButton: isAuthenticated
          ? FloatingActionButton.extended(
              onPressed: () => _openComposer(context, ref),
              icon: const Icon(Icons.add),
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
    }
  }
}

class _TopicsList extends StatelessWidget {
  const _TopicsList({
    required this.paged,
    required this.onOpenTopic,
    required this.onLoadMore,
  });

  final PagedList<ForumTopicListItem> paged;
  final void Function(ForumTopicListItem topic) onOpenTopic;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 120),
          Center(child: Text('No topics yet. Be the first to post!')),
        ],
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.xl3,
      ),
      itemCount: paged.items.length + (paged.hasMore ? 1 : 0),
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (index >= paged.items.length) {
          return _LoadMoreButton(
            isLoading: paged.isLoadingMore,
            onLoadMore: onLoadMore,
          );
        }
        final topic = paged.items[index];
        return TopicCard(
          topic: topic,
          onTap: () => onOpenTopic(topic),
          onAuthorTap: () => context.pushNamed(
            'forumUserProfile',
            pathParameters: {'username': topic.author.username},
          ),
        );
      },
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
    return Center(
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
