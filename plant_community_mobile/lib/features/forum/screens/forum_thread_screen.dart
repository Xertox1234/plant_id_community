import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../forum_errors.dart';
import '../forum_format.dart';
import '../live/live_updates_settings.dart';
import '../live/topic_live.dart';
import '../live/topic_missing_out.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../services/forum_api.dart';
import '../services/forum_link_launcher.dart';
import '../widgets/forum_edit_history_sheet.dart';
import '../widgets/forum_report_sheet.dart';
import '../widgets/identification_card.dart';
import '../widgets/live_flash.dart';
import '../widgets/poll_card.dart';
import '../widgets/post_card.dart';
import 'forum_composer_screen.dart';

/// A topic thread: the opening post + replies (oldest-first, cursor "Load
/// More"), with reactions and a reply action. Signed in, with "Live
/// updates" on, new replies, edits, deletes and topic changes arrive live
/// ([TopicLive]); pull to refresh works either way.
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

    final live = ref.watch(topicLiveProvider(topicId));
    final topic = detail.asData?.value;
    final title = topic?.title ?? initialTitle ?? 'Topic';
    final isLocked = topic?.isLocked ?? false;
    final isSubscribed = topic?.isSubscribed ?? false;
    final isBookmarked = topic?.isBookmarked ?? false;
    // Server authority for the mark/unmark affordance (topic author or a
    // moderator) — never re-derived from the viewer's identity here.
    final canMarkSolution =
        isAuthenticated && (topic?.canMarkSolution ?? false);
    // Quote pre-fills a reply, so it follows the reply FAB's own gate.
    final canQuote = isAuthenticated && !isLocked && detail.hasValue;

    return _LiveScope(
      topicId: topicId,
      child: Scaffold(
        appBar: AppBar(
          title: Text(title),
          actions: [
            if (isAuthenticated && detail.hasValue) ...[
              IconButton(
                tooltip: isBookmarked ? 'Remove bookmark' : 'Bookmark',
                // Lucide has no filled bookmark, so the SAVED state is a different
                // glyph, matching the web's BookmarkCheck/Bookmark pair
                // (ThreadDetailPage.tsx). Material's filled/outline pair does
                // not survive the move to an all-outlined icon set.
                icon: Icon(
                  isBookmarked
                      ? LucideIcons.bookmarkCheck
                      : LucideIcons.bookmark,
                ),
                onPressed: () => _toggleBookmark(context, ref),
              ),
              IconButton(
                tooltip: isSubscribed ? 'Unsubscribe' : 'Subscribe',
                icon: Icon(
                  isSubscribed ? LucideIcons.bellRing : LucideIcons.bell,
                ),
                onPressed: () => _toggleSubscription(context, ref),
              ),
            ],
          ],
        ),
        body: SafeArea(
          child: live.gone
              ? const _GoneView()
              : postsAsync.when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
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
                    onLoadMore: () => ref
                        .read(topicPostsProvider(topicId).notifier)
                        .loadMore(),
                    onOpenLink: (href) => _openLink(context, ref, href),
                    onEdit: (post) => _openEdit(context, ref, post),
                    onDelete: (post) => _confirmDelete(context, ref, post),
                    onReport: isAuthenticated
                        ? (post) => _reportPost(context, ref, post)
                        : null,
                    onShowHistory: isAuthenticated
                        ? (post) => showForumEditHistorySheet(
                            context,
                            postId: post.id,
                            topicId: topicId,
                          )
                        : null,
                    solvedPostId: topic?.solvedPostId,
                    onToggleSolution: canMarkSolution
                        ? (post) => _toggleSolution(context, ref, post)
                        : null,
                    highlightPostId: highlightPostId,
                    identification: topic?.identification,
                    poll: topic?.poll,
                    canVote: isAuthenticated,
                    onVote: isAuthenticated
                        ? (optionIds) => _votePoll(context, ref, optionIds)
                        : null,
                    onQuote: canQuote
                        ? (post) => _openReply(context, ref, quoteOf: post)
                        : null,
                    pendingCount: live.pendingCount,
                    flashIds: live.flashIds,
                    slideIds: live.slideIds,
                    onTakePending: () => ref
                        .read(topicLiveProvider(topicId).notifier)
                        .takePending(),
                    onAtBottom: (atBottom) => ref
                        .read(topicLiveProvider(topicId).notifier)
                        .setReaderAtBottom(atBottom),
                    onFlashDone: (postId) => ref
                        .read(topicLiveProvider(topicId).notifier)
                        .clearFlash(postId),
                    onRefresh: () => _refresh(context, ref),
                  ),
                ),
        ),
        floatingActionButton: (isAuthenticated && !isLocked && !live.gone)
            ? FloatingActionButton.extended(
                onPressed: () => _openReply(context, ref),
                icon: const Icon(LucideIcons.reply),
                label: const Text('Reply'),
              )
            : null,
      ),
    );
  }

  /// Pull to refresh, whatever the setting: walk every page (which also
  /// clears and highlights anything behind the pill), then re-read the topic
  /// with a peek, so no view is counted.
  Future<void> _refresh(BuildContext context, WidgetRef ref) async {
    await ref.read(topicLiveProvider(topicId).notifier).takePending();
    if (!context.mounted) return;
    try {
      final fresh = await ref
          .read(forumApiProvider)
          .fetchTopicDetail(topicId, peek: true);
      if (!context.mounted) return;
      ref.read(topicDetailProvider(topicId).notifier).applyPeek(fresh);
    } catch (_) {
      // The thread already refreshed; the topic header keeps what it had.
    }
  }

  /// Open the reply composer; with [quoteOf] (the Quote action, todo 342)
  /// it opens pre-filled with that post's excerpt as a structured
  /// `post_quote` block keyed to the post's id — the server carries the
  /// attribution and notifies the quoted author.
  Future<void> _openReply(
    BuildContext context,
    WidgetRef ref, {
    ForumPost? quoteOf,
  }) async {
    ForumQuoteDraft? quote;
    if (quoteOf != null) {
      quote = forumQuoteDraft(quoteOf);
      if (quote == null) {
        // Image-only / embed-only post: nothing a quote block could carry.
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Nothing to quote in that post.')),
        );
        return;
      }
    }
    // D11: hold live `post.created` events from opening the composer until
    // the refresh walk settles, so the reader's own reply never shows twice,
    // counts in the pill, or uses up the intro toast.
    final live = ref.read(topicLiveProvider(topicId).notifier);
    live.beginOwnReply();
    try {
      await _publishReply(context, ref, quote);
    } finally {
      live.endOwnReply();
    }
  }

  Future<void> _publishReply(
    BuildContext context,
    WidgetRef ref,
    ForumQuoteDraft? quote,
  ) async {
    final result = await context.pushNamed<bool>(
      'forumCompose',
      extra: ForumComposeArgs.reply(topicId: topicId, quote: quote),
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

  /// Cast a poll ballot (todo 341 wave 3). A 409 is branched on STATUS,
  /// never message text, and bypasses [forumErrorMessage]'s in-flight-twin
  /// wording: for a poll it means "already voted" (a stale
  /// `my_vote_option_ids` — another device) or "closed while this thread
  /// was open", and the server's own sentence names which. The single-value
  /// detail is then refetched so the ballot resyncs — cheap, and not a
  /// paged feed.
  Future<void> _votePoll(
    BuildContext context,
    WidgetRef ref,
    List<int> optionIds,
  ) async {
    try {
      await ref.read(topicDetailProvider(topicId).notifier).votePoll(optionIds);
    } catch (e) {
      if (!context.mounted) return;
      final String message;
      if (e is ApiException && e.statusCode == 409) {
        message = e.message.isNotEmpty
            ? e.message
            : 'You have already voted in this poll.';
        ref.invalidate(topicDetailProvider(topicId));
      } else {
        message = forumErrorMessage(
          e,
          fallback: 'Could not record your vote.',
          forbidden: 'Sign in to vote.',
        );
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
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

  /// Opens a post link or video card in the in-app browser (todo 424). Only
  /// absolute http(s) URLs reach the launcher. Anything refused or failing
  /// gets a short message, never the raw URL: VoiceOver spells a URL out
  /// character by character.
  Future<void> _openLink(
    BuildContext context,
    WidgetRef ref,
    String href,
  ) async {
    final uri = openableForumLink(href);
    var opened = false;
    if (uri != null) {
      try {
        opened = await ref.read(forumLinkLauncherProvider)(uri);
      } catch (_) {
        opened = false;
      }
    }
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text("Couldn't open this link.")));
    }
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
    this.identification,
    this.poll,
    this.canVote = false,
    this.onVote,
    this.onQuote,
    this.pendingCount = 0,
    this.flashIds = const {},
    this.slideIds = const {},
    this.onTakePending,
    this.onAtBottom,
    this.onFlashDone,
    this.onRefresh,
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

  /// Header cards (todo 341 wave 3): the plant-ID snapshot and the poll,
  /// rendered once under the opening post — never fetched here.
  final ForumIdentification? identification;
  final ForumPoll? poll;
  final bool canVote;
  final Future<void> Function(List<int> optionIds)? onVote;

  /// Non-null when the viewer may reply (signed in, topic open).
  final void Function(ForumPost post)? onQuote;

  /// Live replies (slice 4): replies behind the "N new replies" pill, the
  /// posts to highlight, and the pill tap, which walks every page and
  /// returns the first new reply's id to scroll to.
  final int pendingCount;
  final Set<int> flashIds;

  /// The flashed posts that were inserted live, and slide open.
  final Set<int> slideIds;
  final Future<int?> Function()? onTakePending;

  /// Reports whether the reader is at the bottom: a live reply slides in
  /// only then.
  final void Function(bool atBottom)? onAtBottom;
  final void Function(int postId)? onFlashDone;

  /// Pull to refresh.
  final Future<void> Function()? onRefresh;

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
  /// [_keyForId] resolves the answer to it — see [_keyFor]/[_chaseTo].
  final _solutionKey = GlobalKey();

  /// Same single-key discipline for the first reply the pill revealed.
  final _firstNewKey = GlobalKey();
  int? _firstNewId;

  final _scrollController = ScrollController();
  bool _jumping = false;
  bool _atBottom = true;

  /// Following a live insert to the bottom: set when it lands, cleared once
  /// its card has full height ([LiveFlash.onSlideDone]) or the reader
  /// drags. A sliding card grows the list after the first scroll, so every
  /// metrics change re-pins the end until then.
  bool _pinned = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_reportAtBottom);
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
  void didUpdateWidget(covariant _ThreadBody oldWidget) {
    super.didUpdateWidget(oldWidget);
    // A reply inserted live while the reader sat at the bottom: follow it.
    final oldLast = oldWidget.paged.items.isEmpty
        ? null
        : oldWidget.paged.items.last.id;
    final newLast = widget.paged.items.isEmpty
        ? null
        : widget.paged.items.last.id;
    if (newLast != null &&
        newLast != oldLast &&
        widget.flashIds.contains(newLast) &&
        _atBottom) {
      _pinned = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _followToBottom());
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  /// Within 48 px of the end counts as the bottom; a list too short to
  /// scroll is always at the bottom.
  void _reportAtBottom() {
    if (!_scrollController.hasClients) return;
    final position = _scrollController.position;
    final atBottom =
        _pinned || position.pixels >= position.maxScrollExtent - 48;
    _atBottom = atBottom;
    widget.onAtBottom?.call(atBottom);
  }

  /// Jumps, never animates: the card sliding open is the motion, and the
  /// end it would animate to moves while it grows.
  void _followToBottom() {
    if (!mounted || !_scrollController.hasClients) return;
    _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
  }

  void _slideDone() {
    if (!_pinned) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _followToBottom();
      _pinned = false;
      _reportAtBottom();
    });
  }

  bool _onScrollNotification(Notification notification) {
    if (notification is ScrollStartNotification &&
        notification.dragDetails != null) {
      _pinned = false; // The reader took over.
    } else if (notification is ScrollMetricsNotification && _pinned) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_pinned) _followToBottom();
      });
    }
    return false;
  }

  GlobalKey? _keyFor(ForumPost post) {
    if (post.id == widget.highlightPostId) return _highlightKey;
    if (post.id == widget.solvedPostId) return _solutionKey;
    if (post.id == _firstNewId) return _firstNewKey;
    return null;
  }

  /// The one key [_keyFor] gives [postId], mirroring its precedence.
  GlobalKey _keyForId(int postId) {
    if (postId == widget.highlightPostId) return _highlightKey;
    if (postId == widget.solvedPostId) return _solutionKey;
    return _firstNewKey;
  }

  /// `true` once [postId]'s card is built and has been scrolled into view.
  /// The key's context is read and used with no async gap in between — it
  /// is re-read on every pass of the chase below, never held across one.
  Future<bool> _revealIfBuilt(int postId) {
    final postContext = _keyForId(postId).currentContext;
    if (postContext == null) return Future<bool>.value(false);
    return Scrollable.ensureVisible(
      postContext,
      alignment: 0.05,
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 300),
    ).then((_) => true);
  }

  Future<void> _jumpToAnswer() async {
    final solvedId = widget.solvedPostId;
    if (solvedId != null) await _chaseTo(solvedId);
  }

  /// The pill tap: walk every page, then reveal the first new reply.
  Future<void> _takePending() async {
    final take = widget.onTakePending;
    if (take == null) return;
    final firstNew = await take();
    if (firstNew == null || !mounted) return;
    setState(() => _firstNewId = firstNew);
    await WidgetsBinding.instance.endOfFrame;
    await _chaseTo(firstNew);
  }

  /// Scroll [postId] into view. A lazy list only attaches the key once the
  /// card is BUILT (docs/rules/flutter.md), so this walks the list a
  /// viewport at a time until it is — pulling the next cursor page when the
  /// post is not on a loaded one — bounded by [_maxJumpSteps].
  Future<void> _chaseTo(int postId) async {
    if (_jumping) return;
    _jumping = true;
    try {
      for (var i = 0; i < _maxJumpSteps && mounted; i++) {
        if (await _revealIfBuilt(postId)) return;
        if (!widget.paged.items.any((p) => p.id == postId)) {
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
    // After layout, so a fresh list, a short one or one that grew reports
    // where the reader actually is, not only after a scroll.
    SchedulerBinding.instance.addPostFrameCallback((_) {
      if (mounted) _reportAtBottom();
    });
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    if (widget.paged.items.isEmpty) {
      return _refreshable(
        ListView(
          controller: _scrollController,
          physics: const AlwaysScrollableScrollPhysics(),
          children: const [
            SizedBox(height: 200, child: Center(child: Text('No posts yet.'))),
          ],
        ),
      );
    }
    final list = ListView.separated(
      controller: _scrollController,
      physics: const AlwaysScrollableScrollPhysics(),
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
        final card = PostCard(
          key: _keyFor(post),
          post: post,
          currentTopicId: widget.topicId,
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
          onQuote: widget.onQuote == null ? null : () => widget.onQuote!(post),
        );
        final shown = widget.flashIds.contains(post.id)
            ? LiveFlash(
                key: ValueKey('live-flash-${post.id}'),
                slide: !reduceMotion && widget.slideIds.contains(post.id),
                onDone: () => widget.onFlashDone?.call(post.id),
                onSlideDone: _slideDone,
                child: card,
              )
            : card;
        // The header cards ride the first item: under it when it is the
        // opening post, above it otherwise (an OP held for moderation).
        return index == 0
            ? _withHeaderCards(shown, leading: !post.isOpeningPost)
            : shown;
      },
    );
    final pending = widget.pendingCount;
    final body = Stack(
      children: [
        _refreshable(list),
        if (pending > 0)
          Positioned(
            left: 0,
            right: 0,
            // Above the Reply button, so the two never overlap.
            bottom: 88,
            child: Center(
              child: _NewRepliesPill(count: pending, onTap: _takePending),
            ),
          ),
      ],
    );
    if (widget.solvedPostId == null) return body;
    return Column(
      children: [
        _SolvedBanner(onJump: _jumpToAnswer),
        Expanded(child: body),
      ],
    );
  }

  Widget _refreshable(Widget list) {
    final onRefresh = widget.onRefresh;
    final listened = NotificationListener<Notification>(
      onNotification: _onScrollNotification,
      child: list,
    );
    if (onRefresh == null) return listened;
    return RefreshIndicator(onRefresh: onRefresh, child: listened);
  }
}

extension on _ThreadBodyState {
  /// [card] plus the identification snapshot and poll cards (todo 341 wave
  /// 3), or just [card] when the topic carries neither.
  Widget _withHeaderCards(Widget card, {required bool leading}) {
    final identification = widget.identification;
    final poll = widget.poll;
    final cards = <Widget>[
      if (identification != null)
        IdentificationCard(
          identification: identification,
          solvedPostId: widget.solvedPostId,
          onJumpToAnswer: widget.solvedPostId == null ? null : _jumpToAnswer,
        ),
      if (poll != null)
        PollCard(poll: poll, canVote: widget.canVote, onVote: widget.onVote),
    ];
    if (cards.isEmpty) return card;
    final ordered = leading ? [...cards, card] : [card, ...cards];
    return Column(
      children: [
        for (var i = 0; i < ordered.length; i++) ...[
          if (i > 0) const SizedBox(height: AppSpacing.sm),
          ordered[i],
        ],
      ],
    );
  }
}

/// The bottom-centre "N new replies" pill (live replies, slice 4).
class _NewRepliesPill extends StatelessWidget {
  const _NewRepliesPill({required this.count, required this.onTap});

  final int count;
  final Future<void> Function() onTap;

  @override
  Widget build(BuildContext context) {
    return FilledButton.tonalIcon(
      onPressed: onTap,
      style: FilledButton.styleFrom(minimumSize: const Size(48, 48)),
      icon: const Icon(LucideIcons.arrowDown, size: 18),
      label: Text('$count new repl${count == 1 ? 'y' : 'ies'}'),
    );
  }
}

/// The topic was removed, or is no longer visible to this reader (4404).
class _GoneView extends StatelessWidget {
  const _GoneView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(AppSpacing.lg),
        child: Text(
          'This topic is no longer available.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

/// The thread's live-replies hooks: the app lifecycle (hidden closes the
/// socket and pauses the signed-out check; shown resumes both) and the two
/// toasts. Wraps the screen's Scaffold, whose messenger shows them.
class _LiveScope extends ConsumerStatefulWidget {
  const _LiveScope({required this.topicId, required this.child});

  final int topicId;
  final Widget child;

  @override
  ConsumerState<_LiveScope> createState() => _LiveScopeState();
}

/// The toasts' shared shape (D14): 10 s, closeable. `persist: false` because
/// a SnackBar with an action otherwise never times out; with accessible
/// navigation on, the messenger keeps it up anyway.
SnackBar _liveToast(Widget content, {SnackBarAction? action}) => SnackBar(
  content: content,
  action: action,
  duration: const Duration(seconds: 10),
  showCloseIcon: true,
  persist: false,
);

class _LiveScopeState extends ConsumerState<_LiveScope> {
  late final AppLifecycleListener _lifecycle;

  /// Off while another route covers the thread or its tab is not shown
  /// (the Overlay and the shell's indexed stack both turn tickers off).
  ValueListenable<TickerModeData>? _onScreen;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onHide: _onHide, onShow: _onShow);
    ref.listenManual(
      topicLiveProvider(widget.topicId).select((s) => s.introSeq),
      (previous, next) {
        if (next > (previous ?? 0)) _showIntro();
      },
    );
    ref.listenManual(topicMissingOutProvider(widget.topicId), (previous, next) {
      if (next > (previous ?? 0)) _showMissingOut();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final onScreen = TickerMode.getValuesNotifier(context);
    if (identical(onScreen, _onScreen)) return;
    _onScreen?.removeListener(_onScreenChanged);
    _onScreen = onScreen..addListener(_onScreenChanged);
    _onScreenChanged();
  }

  @override
  void dispose() {
    _onScreen?.removeListener(_onScreenChanged);
    _lifecycle.dispose();
    super.dispose();
  }

  /// The socket and the signed-out check run only while the topic is on
  /// screen (spec O9), not while it sits under another route or tab.
  ///
  /// Applied after the frame: the ticker mode changes while the tree builds,
  /// and providers may not change then.
  void _onScreenChanged() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final covered = !(_onScreen?.value.enabled ?? true);
      ref.read(topicLiveProvider(widget.topicId).notifier).setCovered(covered);
      ref
          .read(topicMissingOutProvider(widget.topicId).notifier)
          .setCovered(covered);
    });
  }

  void _onHide() {
    ref.read(topicLiveProvider(widget.topicId).notifier).suspend();
    ref.read(topicMissingOutProvider(widget.topicId).notifier).suspend();
  }

  void _onShow() {
    ref.read(topicLiveProvider(widget.topicId).notifier).resume();
    ref.read(topicMissingOutProvider(widget.topicId).notifier).resume();
  }

  /// "Replies now appear live." with Turn off, then "Live updates off" with
  /// Undo. The setting is app-wide (keepAlive), so the actions work even
  /// after the reader has left the topic.
  void _showIntro() {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final setting = ref.read(liveUpdatesSettingProvider.notifier);
    messenger.showSnackBar(
      _liveToast(
        const Text('Replies now appear live.'),
        action: SnackBarAction(
          label: 'Turn off',
          onPressed: () {
            setting.setEnabled(false);
            messenger.showSnackBar(
              _liveToast(
                const Text('Live updates off'),
                action: SnackBarAction(
                  label: 'Undo',
                  onPressed: () => setting.setEnabled(true),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  /// The signed-out toast. A SnackBar takes one action, so Sign in and
  /// Sign up are two buttons in its content. Both auth screens return to
  /// this topic afterwards (`dismissAfterAuth`).
  void _showMissingOut() {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final linkColor = Theme.of(context).colorScheme.inversePrimary;
    void go(String route) {
      messenger.hideCurrentSnackBar();
      context.pushNamed(route);
    }

    messenger.showSnackBar(
      _liveToast(
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'New replies are coming in. Sign in or sign up to follow '
              'along live.',
            ),
            Wrap(
              spacing: AppSpacing.sm,
              children: [
                TextButton(
                  style: TextButton.styleFrom(foregroundColor: linkColor),
                  onPressed: () => go('login'),
                  child: const Text('Sign in'),
                ),
                TextButton(
                  style: TextButton.styleFrom(foregroundColor: linkColor),
                  onPressed: () => go('register'),
                  child: const Text('Sign up'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => widget.child;
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
              LucideIcons.circleCheck,
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
