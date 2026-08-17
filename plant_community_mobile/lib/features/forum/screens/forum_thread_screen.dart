import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../widgets/post_card.dart';
import 'forum_composer_screen.dart';

/// A topic thread: the opening post + replies (oldest-first, cursor "Load
/// More"), with reactions and a reply action.
class ForumThreadScreen extends ConsumerWidget {
  const ForumThreadScreen({
    super.key,
    required this.topicId,
    this.initialTitle,
  });

  final int topicId;
  final String? initialTitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(topicDetailProvider(topicId));
    final postsAsync = ref.watch(topicPostsProvider(topicId));
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );

    final title = detail.asData?.value.title ?? initialTitle ?? 'Topic';
    final isLocked = detail.asData?.value.isLocked ?? false;

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: postsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _ErrorRetry(
            message: 'Could not load this thread.',
            onRetry: () => ref.invalidate(topicPostsProvider(topicId)),
          ),
          data: (paged) => _ThreadBody(
            topicId: topicId,
            paged: paged,
            canReact: isAuthenticated,
            onReact: isAuthenticated
                ? (postId, type) => ref
                      .read(topicPostsProvider(topicId).notifier)
                      .toggleReaction(postId, type)
                : null,
            onLoadMore: () =>
                ref.read(topicPostsProvider(topicId).notifier).loadMore(),
            onOpenLink: (href) => _showLink(context, href),
            onEdit: (post) => _openEdit(context, ref, post),
            onDelete: (post) => _confirmDelete(context, ref, post),
          ),
        ),
      ),
      floatingActionButton: (isAuthenticated && !isLocked)
          ? FloatingActionButton.extended(
              onPressed: () => _openReply(context, ref),
              icon: const Icon(Icons.reply),
              label: const Text('Reply'),
            )
          : null,
    );
  }

  Future<void> _openReply(BuildContext context, WidgetRef ref) async {
    final result = await context.pushNamed<bool>(
      'forumCompose',
      extra: ForumComposeArgs.reply(topicId: topicId),
    );
    if (result == true) {
      // A new reply is oldest-first-ordered onto the LAST cursor page, so a
      // plain `invalidate` (page 1 only) would leave it invisible on a
      // multi-page thread (todo 291) — walk every page instead.
      try {
        await ref
            .read(topicPostsProvider(topicId).notifier)
            .refreshAfterReply();
      } catch (_) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Reply posted, but the thread could not be refreshed.',
              ),
            ),
          );
        }
      }
      ref.invalidate(topicDetailProvider(topicId));
    }
  }

  /// Open the composer in edit mode (todo 292). Unlike [_openReply], a
  /// successful publish pops the updated [ForumPost] itself (not a bare
  /// `true`) — [TopicPosts.applyEditedPost] splices it into the already-
  /// loaded page rather than invalidating and losing any pages the user had
  /// loaded via `loadMore` on a long thread.
  Future<void> _openEdit(
    BuildContext context,
    WidgetRef ref,
    ForumPost post,
  ) async {
    final result = await context.pushNamed<ForumPost>(
      'forumCompose',
      extra: ForumComposeArgs.edit(post: post),
    );
    if (result != null) {
      ref.read(topicPostsProvider(topicId).notifier).applyEditedPost(result);
      // Same as _openReply below: refresh the single-object topic detail
      // (reply metadata etc.) — cheap, and unrelated to the paged-state
      // preservation applyEditedPost exists for (code review).
      ref.invalidate(topicDetailProvider(topicId));
    }
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    ForumPost post,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete post?'),
        content: const Text('This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(topicPostsProvider(topicId).notifier).deletePost(post.id);
      // reply_count/last_post_at live on the topic detail, not the paged
      // post list — refresh it so a deletion is reflected immediately
      // rather than only on the next visit (code review).
      ref.invalidate(topicDetailProvider(topicId));
    } on ApiException catch (e) {
      // The backend's 409 message is already specific and non-retry-implying
      // ("Topic is closed or locked.", "Opening posts cannot be deleted via
      // the API.") — surfaced verbatim, same reasoning as the edit composer's
      // 409 handling (todo 292 AC3).
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not delete this post.')),
        );
      }
    }
  }

  void _showLink(BuildContext context, String href) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(href)));
  }
}

class _ThreadBody extends StatelessWidget {
  const _ThreadBody({
    required this.topicId,
    required this.paged,
    required this.canReact,
    required this.onReact,
    required this.onLoadMore,
    required this.onOpenLink,
    required this.onEdit,
    required this.onDelete,
  });

  final int topicId;
  final PagedList<ForumPost> paged;
  final bool canReact;
  final void Function(int postId, String type)? onReact;
  final Future<void> Function() onLoadMore;
  final void Function(String href) onOpenLink;
  final void Function(ForumPost post) onEdit;
  final void Function(ForumPost post) onDelete;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty) {
      return const Center(child: Text('No posts yet.'));
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
        final post = paged.items[index];
        return PostCard(
          post: post,
          onOpenLink: onOpenLink,
          onReact: onReact == null ? null : (type) => onReact!(post.id, type),
          onEdit: () => onEdit(post),
          onDelete: () => onDelete(post),
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
