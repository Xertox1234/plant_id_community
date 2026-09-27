import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/blog_post.dart';
import '../providers/blog_providers.dart';
import '../services/blog_api.dart';
import 'blog_format.dart';

/// Published blog posts, newest first, with a "Load more" footer (todo 385).
///
/// [tag] narrows the list to one tag; the care guides open it with
/// `care-guide` (todo 386). [title] overrides the app bar title.
class BlogListScreen extends ConsumerWidget {
  const BlogListScreen({super.key, this.tag, this.title});

  final String? tag;
  final String? title;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feed = ref.watch(blogPostsProvider(tag));
    return Scaffold(
      appBar: AppBar(title: Text(title ?? 'Blog')),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => ref.invalidate(blogPostsProvider(tag)),
          child: feed.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => _ErrorRetry(
              message: 'Could not load posts.',
              onRetry: () => ref.invalidate(blogPostsProvider(tag)),
            ),
            data: (feed) => _PostList(
              feed: feed,
              mediaUrl: ref.read(blogApiProvider).mediaUrl,
              onOpen: (post) => context.pushNamed(
                'blogPost',
                pathParameters: {'slug': post.slug},
                extra: post.title,
              ),
              onLoadMore: () =>
                  ref.read(blogPostsProvider(tag).notifier).loadMore(),
            ),
          ),
        ),
      ),
    );
  }
}

class _PostList extends StatelessWidget {
  const _PostList({
    required this.feed,
    required this.mediaUrl,
    required this.onOpen,
    required this.onLoadMore,
  });

  final BlogFeed feed;
  final String Function(String url) mediaUrl;
  final void Function(BlogPostSummary post) onOpen;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (feed.items.isEmpty) {
      // A ListView, not a bare Center, so pull-to-refresh still works.
      return ListView(
        children: const [
          SizedBox(height: 120),
          Center(child: Text('No posts yet.')),
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
      itemCount: feed.items.length + (feed.hasMore ? 1 : 0),
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (index >= feed.items.length) {
          return _LoadMoreButton(
            isLoading: feed.isLoadingMore,
            onLoadMore: onLoadMore,
          );
        }
        final post = feed.items[index];
        return _PostCard(
          post: post,
          mediaUrl: mediaUrl,
          onTap: () => onOpen(post),
        );
      },
    );
  }
}

class _PostCard extends StatelessWidget {
  const _PostCard({
    required this.post,
    required this.mediaUrl,
    required this.onTap,
  });

  final BlogPostSummary post;
  final String Function(String url) mediaUrl;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final thumb = post.thumbnail;
    final meta = blogMetaLine(post.publishDate, post.readingTime);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (thumb != null) ...[
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: SizedBox(
                    width: 72,
                    height: 72,
                    // Decorative: the title beside it names the post.
                    child: ExcludeSemantics(
                      child: CachedNetworkImage(
                        imageUrl: mediaUrl(thumb.url),
                        fit: BoxFit.cover,
                        placeholder: (context, _) => ColoredBox(
                          color: theme.colorScheme.surfaceContainerHigh,
                        ),
                        errorWidget: (context, _, _) => ColoredBox(
                          color: theme.colorScheme.surfaceContainerHigh,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(post.title, style: theme.textTheme.titleMedium),
                    if (post.excerpt.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        post.excerpt,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodyMedium,
                      ),
                    ],
                    if (meta.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(meta, style: theme.textTheme.bodySmall),
                    ],
                  ],
                ),
              ),
            ],
          ),
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
    // Scrollable so the RefreshIndicator above it can still be pulled.
    return ListView(
      children: [
        const SizedBox(height: 120),
        Center(child: Text(message)),
        const SizedBox(height: AppSpacing.sm),
        Center(
          child: OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
        ),
      ],
    );
  }
}
