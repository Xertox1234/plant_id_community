import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../widgets/topic_card.dart';

/// The viewer's bookmarked topics (todo 341), most recently bookmarked
/// first, cursor-paginated with a "Load more" footer. Auth-only route —
/// the backend 401s an anonymous request.
class ForumBookmarksScreen extends ConsumerWidget {
  const ForumBookmarksScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedAsync = ref.watch(bookmarksFeedProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Bookmarks')),
      body: SafeArea(
        child: RefreshIndicator(
          // The screen's OWN feed — a pull-to-refresh is the one place a
          // reset to page 1 is what the user asked for.
          onRefresh: () async => ref.invalidate(bookmarksFeedProvider),
          child: feedAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => _ErrorRetry(
              message: 'Could not load your bookmarks.',
              onRetry: () => ref.invalidate(bookmarksFeedProvider),
            ),
            data: (paged) => _BookmarksList(
              paged: paged,
              onOpenTopic: (topic) => context.pushNamed(
                'forumTopic',
                pathParameters: {'id': '${topic.id}'},
                extra: topic.title,
              ),
              onLoadMore: () =>
                  ref.read(bookmarksFeedProvider.notifier).loadMore(),
            ),
          ),
        ),
      ),
    );
  }
}

class _BookmarksList extends StatelessWidget {
  const _BookmarksList({
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
        children: [
          const SizedBox(height: 120),
          Center(
            child: Column(
              children: [
                Icon(
                  Icons.bookmark_border,
                  size: 40,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                const SizedBox(height: AppSpacing.sm),
                const Text('No bookmarks yet.'),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Tap the bookmark icon on a topic to save it here.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
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
