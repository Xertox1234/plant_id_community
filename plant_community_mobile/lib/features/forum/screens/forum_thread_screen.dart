import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../forum_errors.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../widgets/forum_edit_history_sheet.dart';
import '../widgets/forum_report_sheet.dart';
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

    final topic = detail.asData?.value;
    final title = topic?.title ?? initialTitle ?? 'Topic';
    final isLocked = topic?.isLocked ?? false;
    final isSubscribed = topic?.isSubscribed ?? false;
    final isBookmarked = topic?.isBookmarked ?? false;
    // Server authority for the mark/unmark affordance (topic author or a
    // moderator) — never re-derived from the viewer's identity here.
    final canMarkSolution =
        isAuthenticated && (topic?.canMarkSolution ?? false);

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          if (isAuthenticated && detail.hasValue) ...[
            IconButton(
              tooltip: isBookmarked ? 'Remove bookmark' : 'Bookmark',
              icon: Icon(isBookmarked ? Icons.bookmark : Icons.bookmark_border),
              onPressed: () => _toggleBookmark(context, ref),
            ),
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
            onReport: isAuthenticated
                ? (post) => _reportPost(context, ref, post)
                : null,
            onShowHistory: isAuthenticated
                ? (post) => showForumEditHistorySheet(context, postId: post.id)
                : null,
            solvedPostId: topic?.solvedPostId,
            onToggleSolution: canMarkSolution
                ? (post) => _toggleSolution(context, ref, post)
                : null,
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

  Future<void> _toggleBookmark(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(topicDetailProvider(topicId).notifier).toggleBookmark();
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              forumErrorMessage(e, fallback: 'Could not update bookmark.'),
            ),
          ),
        );
      }
    }
  }

  /// Accept [post] as the answer, or clear it when it already is. The
  /// detail's `solvedPostId` is the single source of "is this the answer"
  /// — read fresh here rather than trusting a card's stale render.
  Future<void> _toggleSolution(
    BuildContext context,
    WidgetRef ref,
    ForumPost post,
  ) async {
    final notifier = ref.read(topicDetailProvider(topicId).notifier);
    final isCurrent =
        ref.read(topicDetailProvider(topicId)).asData?.value.solvedPostId ==
        post.id;
    try {
      if (isCurrent) {
        await notifier.clearSolution();
      } else {
        await notifier.markSolution(post.id);
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              forumErrorMessage(
                e,
                fallback: 'Could not update the accepted answer.',
                forbidden:
                    "Only the topic's author or a moderator can accept an "
                    'answer.',
              ),
            ),
          ),
        );
      }
    }
  }

  Future<void> _reportPost(
    BuildContext context,
    WidgetRef ref,
    ForumPost post,
  ) async {
    final choice = await showForumReportSheet(
      context,
      title: 'Report post',
      prompt: 'Why are you reporting this post?',
    );
    if (choice == null || !context.mounted) return;
    try {
      await ref
          .read(topicPostsProvider(topicId).notifier)
          .reportPost(
            postId: post.id,
            reason: choice.reason,
            detail: choice.detail,
          );
      if (!context.mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Reported')));
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            forumErrorMessage(
              e,
              fallback: 'Could not send your report.',
              forbidden: "You can't report this post.",
            ),
          ),
        ),
      );
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

/// Safety bound on the "Jump to answer" chase (viewport steps + cursor
/// pages) for a pathologically long thread.
const _maxJumpSteps = 60;

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
    this.onReport,
    this.onShowHistory,
    this.solvedPostId,
    this.onToggleSolution,
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
  final void Function(ForumPost post)? onReport;
  final void Function(ForumPost post)? onShowHistory;

  /// The accepted answer's post id (todo 341) — drives the card ring and
  /// the "Jump to answer" banner.
  final int? solvedPostId;

  /// Non-null only when the viewer may mark/unmark (topic author or
  /// moderator). Never wired on the opening post below.
  final void Function(ForumPost post)? onToggleSolution;
  final int? highlightPostId;

  @override
  State<_ThreadBody> createState() => _ThreadBodyState();
}

/// Stateful for [_highlightKey] and the one-shot highlight scroll, plus the
/// "Jump to answer" chase (todo 341) — everything else about a topic's post
/// list is still driven top-down from [ForumThreadScreen]'s providers.
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

  /// Same single-key discipline for the accepted answer. When the answer IS
  /// the highlighted post, [_highlightKey] wins (a widget takes one key) and
  /// [_answerKey] resolves to it — see [_keyFor]/[_jumpToAnswer].
  final _solutionKey = GlobalKey();

  final _scrollController = ScrollController();
  bool _jumping = false;

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
    // also out of scope. (The "Jump to answer" chase below is the
    // explicit-tap counterpart that DOES walk the list.)
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
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  GlobalKey? _keyFor(ForumPost post) {
    if (post.id == widget.highlightPostId) return _highlightKey;
    if (post.id == widget.solvedPostId) return _solutionKey;
    return null;
  }

  GlobalKey get _answerKey => widget.highlightPostId == widget.solvedPostId
      ? _highlightKey
      : _solutionKey;

  /// `true` once the answer card is built and has been scrolled into view.
  /// The key's context is read and used with no async gap in between — it
  /// is re-read on every pass of the chase below, never held across one.
  Future<bool> _revealAnswerIfBuilt() {
    final answerContext = _answerKey.currentContext;
    if (answerContext == null) return Future<bool>.value(false);
    return Scrollable.ensureVisible(
      answerContext,
      alignment: 0.05,
      duration: const Duration(milliseconds: 300),
    ).then((_) => true);
  }

  /// Scroll the accepted answer into view. A lazy list only attaches the
  /// key once the card is BUILT (docs/rules/flutter.md), so this walks the
  /// list a viewport at a time until it is — pulling the next cursor page
  /// when the answer is not on a loaded one — bounded by [_maxJumpSteps].
  Future<void> _jumpToAnswer() async {
    final solvedId = widget.solvedPostId;
    if (solvedId == null || _jumping) return;
    _jumping = true;
    try {
      for (var i = 0; i < _maxJumpSteps && mounted; i++) {
        if (await _revealAnswerIfBuilt()) return;
        if (!widget.paged.items.any((p) => p.id == solvedId)) {
          // On a later page (or gone): load the next page and re-check.
          if (!widget.paged.hasMore || widget.paged.isLoadingMore) return;
          try {
            await widget.onLoadMore();
          } catch (_) {
            return;
          }
          continue;
        }
        if (!_scrollController.hasClients) return;
        final position = _scrollController.position;
        if (position.pixels >= position.maxScrollExtent) return;
        _scrollController.jumpTo(
          math.min(
            position.pixels + position.viewportDimension,
            position.maxScrollExtent,
          ),
        );
        // Let the list build the newly-visible cards before re-checking.
        await WidgetsBinding.instance.endOfFrame;
      }
    } finally {
      _jumping = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.paged.items.isEmpty) {
      return const Center(child: Text('No posts yet.'));
    }
    final list = ListView.separated(
      controller: _scrollController,
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
        final onToggleSolution = widget.onToggleSolution;
        return PostCard(
          key: _keyFor(post),
          post: post,
          onOpenLink: widget.onOpenLink,
          onReact: widget.onReact == null
              ? null
              : (type) => widget.onReact!(post.id, type),
          onEdit: () => widget.onEdit(post),
          onDelete: () => widget.onDelete(post),
          onReport: widget.onReport == null
              ? null
              : () => widget.onReport!(post),
          onShowHistory: widget.onShowHistory == null
              ? null
              : () => widget.onShowHistory!(post),
          isSolution: post.id == widget.solvedPostId,
          // A question is not its own answer — the endpoint 422s the
          // opening post, so never offer it (mirrors the web).
          onToggleSolution: onToggleSolution == null || post.isOpeningPost
              ? null
              : () => onToggleSolution(post),
          onAuthorTap: () => context.pushNamed(
            'forumUserProfile',
            pathParameters: {'username': post.author.username},
          ),
        );
      },
    );
    if (widget.solvedPostId == null) return list;
    return Column(
      children: [
        _SolvedBanner(onJump: _jumpToAnswer),
        Expanded(child: list),
      ],
    );
  }
}

/// Header strip for a solved topic with the "Jump to answer" affordance.
class _SolvedBanner extends StatelessWidget {
  const _SolvedBanner({required this.onJump});

  final Future<void> Function() onJump;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Material(
      color: scheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.xs,
        ),
        child: Row(
          children: [
            Icon(
              Icons.check_circle,
              size: 18,
              color: scheme.onSecondaryContainer,
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                'This topic has an accepted answer',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSecondaryContainer,
                ),
              ),
            ),
            TextButton(
              onPressed: onJump,
              style: TextButton.styleFrom(
                foregroundColor: scheme.onSecondaryContainer,
                minimumSize: const Size(48, 48),
              ),
              child: const Text('Jump to answer'),
            ),
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
