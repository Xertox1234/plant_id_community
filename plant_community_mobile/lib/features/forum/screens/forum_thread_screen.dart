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
    this.highlightPostId,
  });

  final int topicId;
  final String? initialTitle;

  /// Deep-link target from a push tap (todo 311) or a notification-list
  /// open — scrolled into view once, best-effort, by [_ThreadBody].
  final int? highlightPostId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(topicDetailProvider(topicId));
    final postsAsync = ref.watch(topicPostsProvider(topicId));
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );

    final title = detail.asData?.value.title ?? initialTitle ?? 'Topic';
    final isLocked = detail.asData?.value.isLocked ?? false;
    final isSubscribed = detail.asData?.value.isSubscribed ?? false;

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          if (isAuthenticated && detail.hasValue)
            IconButton(
              tooltip: isSubscribed ? 'Unsubscribe' : 'Subscribe',
              icon: Icon(
                isSubscribed
                    ? Icons.notifications_active
                    : Icons.notifications_none,
              ),
              onPressed: () => _toggleSubscription(context, ref),
            ),
        ],
      ),
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
            highlightPostId: highlightPostId,
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

  Future<void> _toggleSubscription(BuildContext context, WidgetRef ref) async {
    try {
      await ref
          .read(topicDetailProvider(topicId).notifier)
          .toggleSubscription();
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not update subscription.')),
        );
      }
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

class _ThreadBody extends StatefulWidget {
  const _ThreadBody({
    required this.topicId,
    required this.paged,
    required this.canReact,
    required this.onReact,
    required this.onLoadMore,
    required this.onOpenLink,
    required this.onEdit,
    required this.onDelete,
    this.highlightPostId,
  });

  final int topicId;
  final PagedList<ForumPost> paged;
  final bool canReact;
  final void Function(int postId, String type)? onReact;
  final Future<void> Function() onLoadMore;
  final void Function(String href) onOpenLink;
  final void Function(ForumPost post) onEdit;
  final void Function(ForumPost post) onDelete;
  final int? highlightPostId;

  @override
  State<_ThreadBody> createState() => _ThreadBodyState();
}

/// Stateful only for [_highlightKey] and the one-shot highlight scroll —
/// everything else about a topic's post list is still driven top-down from
/// [ForumThreadScreen]'s providers.
class _ThreadBodyState extends State<_ThreadBody> {
  /// Only the single highlighted post (if any) ever needs a key — attached
  /// in `itemBuilder` only when `post.id == widget.highlightPostId`. A
  /// per-post `Map<int, GlobalKey>` was tried first and dropped (code
  /// review): it minted a key for every rendered post that nothing else
  /// used, leaked entries for posts that scrolled out or were deleted, and
  /// — if a duplicate post id ever slipped past pagination with no dedup
  /// upstream — two simultaneously-mounted widgets sharing one `GlobalKey`
  /// would be a hard Flutter crash. A single field sidesteps all three.
  final _highlightKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    final targetId = widget.highlightPostId;
    if (targetId == null) return;
    // Exactly one best-effort attempt, post-frame so this frame's build()
    // has already run.
    //
    // KNOWN LIMITATION (todo 311 follow-up): `ListView.separated` builds
    // lazily — `itemBuilder` only runs for items within the viewport plus
    // its ~250px cache extent, so `_highlightKey` only gets attached (and
    // `currentContext` below is only non-null) when the highlighted post's
    // widget has actually been built on this first frame. There is no
    // search for, or scroll toward, a not-yet-built (off-screen) post —
    // that would need index-based/ScrollController-driven scrolling, which
    // is real new work deliberately left out of this fix. Posts in this
    // thread are oldest-first and a `reply_added` push always targets the
    // newest post, so on any thread longer than a screenful the target is
    // very likely off-screen on first frame, and the scroll below silently
    // no-ops — a known, deliberate limitation, not a bug. No visual
    // highlight flash and no cross-page "Load More" chasing either, both
    // also out of scope.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final postContext = _highlightKey.currentContext;
      if (postContext == null) return;
      Scrollable.ensureVisible(
        postContext,
        duration: const Duration(milliseconds: 300),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.paged.items.isEmpty) {
      return const Center(child: Text('No posts yet.'));
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.xl3,
      ),
      itemCount: widget.paged.items.length + (widget.paged.hasMore ? 1 : 0),
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (index >= widget.paged.items.length) {
          return _LoadMoreButton(
            isLoading: widget.paged.isLoadingMore,
            onLoadMore: widget.onLoadMore,
          );
        }
        final post = widget.paged.items[index];
        return PostCard(
          key: post.id == widget.highlightPostId ? _highlightKey : null,
          post: post,
          onOpenLink: widget.onOpenLink,
          onReact: widget.onReact == null
              ? null
              : (type) => widget.onReact!(post.id, type),
          onEdit: () => widget.onEdit(post),
          onDelete: () => widget.onDelete(post),
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
