import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/routing/main_shell.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../../../services/user_profile_service.dart';
import '../../../shared/widgets/brand_mark.dart';
import '../../../shared/widgets/canopy_accents.dart';
import '../../../shared/widgets/clay_button.dart';
import '../../scan/scan_job_api.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../utils/board_identity.dart';
import '../widgets/author_identity.dart';
import '../widgets/forum_board_sections.dart';
import '../widgets/forum_style.dart';
import '../widgets/forum_tips_carousel.dart';
import '../widgets/home/forum_home_footer.dart';
import '../widgets/home/forum_whos_online.dart';
import '../widgets/topic_card.dart';
import 'forum_composer_screen.dart';

/// The server's `?sort=` values with the labels the web list uses, in the
/// order the sort sheet offers them. The first is the server's fallback.
const List<(String, String)> _sortOptions = [
  ('-last_activity_at', 'Active'),
  ('-created_at', 'Newest'),
  ('created_at', 'Oldest'),
  ('-view_count', 'Most viewed'),
  ('-post_count', 'Most replies'),
];

/// Topics within a board: a title that switches forum, the board's identity
/// card (tile, description, counts) in its own tone, the sort and tag
/// filters, then its topics as one grouped list, cursor-paginated with a
/// "Load more" button, and the forum's footer.
class ForumTopicsScreen extends ConsumerStatefulWidget {
  const ForumTopicsScreen({
    super.key,
    required this.boardSlug,
    this.boardTitle,
  });

  final String boardSlug;
  final String? boardTitle;

  @override
  ConsumerState<ForumTopicsScreen> createState() => _ForumTopicsScreenState();
}

class _ForumTopicsScreenState extends ConsumerState<ForumTopicsScreen> {
  /// Every tag seen on this board's topics while the screen is open, with
  /// the topics carrying it. There is no "tags of a forum" endpoint, and a
  /// filtered page only carries the chosen tag, so the chips are remembered
  /// across reloads rather than read off the current page.
  final Map<String, Set<int>> _seenTags = {};

  String get _slug => widget.boardSlug;

  /// The tag chips: most used first, then by name.
  List<String> _tagsAfter(List<ForumTopicListItem>? items) {
    for (final topic in items ?? const <ForumTopicListItem>[]) {
      for (final tag in topic.tags) {
        (_seenTags[tag] ??= {}).add(topic.id);
      }
    }
    return _seenTags.keys.toList()..sort((a, b) {
      final byUse = _seenTags[b]!.length.compareTo(_seenTags[a]!.length);
      return byUse != 0 ? byUse : a.toLowerCase().compareTo(b.toLowerCase());
    });
  }

  @override
  Widget build(BuildContext context) {
    // Keyed on the viewer: a new one never sees the previous one's list.
    final viewer = ref.watch(forumViewerProvider);
    final topicsProvider = boardTopicsProvider(_slug, viewer);
    final topicsAsync = ref.watch(topicsProvider);
    final filterProvider = boardTopicsFilterStateProvider(_slug);
    final filter = ref.watch(filterProvider);
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    // Decoration and the switcher: present when the boards list is known (it
    // is, coming from the forum home) and simply absent while it loads or if
    // it failed.
    final boards = ref.watch(boardsProvider.select((b) => b.value));
    final board = boards?.where((b) => b.slug == _slug).firstOrNull;
    final title = widget.boardTitle ?? board?.title ?? 'Topics';
    final identity = board != null
        ? boardIdentityOf(board)
        : boardIdentity(_slug, fallbackLabel: title);
    final tone = identity.tone.colorOf(context.canopy);
    // A password forum this member has not unlocked (spec §7.4).
    final locked = switch (topicsAsync.error) {
      ApiException(code: 'forum_locked') => true,
      _ => false,
    };
    final tags = _tagsAfter(topicsAsync.value?.items);
    final defaultSort = (board?.defaultSort.isNotEmpty ?? false)
        ? board!.defaultSort
        : _sortOptions.first.$1;
    final sort = filter.sort ?? defaultSort;
    // What the tips may say to this viewer. Each stays unknown (and its tip
    // unshown) until its own request has answered; a guest asks for neither.
    final profile = isAuthenticated
        ? ref.watch(userProfileServiceProvider).asData?.value
        : null;
    final allowance = isAuthenticated
        ? ref.watch(scanAllowanceProvider).asData?.value
        : null;
    final tips = forumTipsFor(
      signedIn: isAuthenticated,
      hasAvatar: profile == null ? null : (profile.avatar?.isNotEmpty ?? false),
      isPremium: allowance?.isPremium,
      premiumDailyChecks: allowance?.premiumDiagnoseLimit,
    );

    // Both: the header's counts come from the boards list, so a refresh that
    // only refetched the topics would leave "7 topics" above eight rows.
    void refresh() {
      ref.invalidate(topicsProvider);
      ref.invalidate(categoriesProvider);
      // The sections under the list are part of the page being refreshed.
      ref.invalidate(boardContributorsProvider);
      ref.invalidate(homeRecentTopicsProvider);
      ref.invalidate(communityStatsProvider);
    }

    return Scaffold(
      appBar: AppBar(
        centerTitle: false,
        titleSpacing: 0,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // The title already names the screen; the mark is decoration.
            const ExcludeSemantics(child: BrandMark(size: 28)),
            const SizedBox(width: 10),
            Flexible(
              child: boards == null || boards.length < 2
                  ? Text(title, maxLines: 1, overflow: TextOverflow.ellipsis)
                  : _ForumSwitcherButton(
                      title: title,
                      onTap: () => _switchForum(context, boards),
                    ),
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
              // ONE Column child, not a section per ListView child (as on the
              // forum home): a lazily built section is disposed off screen,
              // which resets the carousel and refetches the sections under
              // the list on the way back up.
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!locked)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                      child: ForumTipsCarousel(
                        intro: board == null
                            ? null
                            : _BoardIntro(
                                board: board,
                                identity: identity,
                                tone: tone,
                              ),
                        tips: tips,
                        onAction: (route) => context.pushNamed(route),
                      ),
                    )
                  else if (board != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: _BoardIntro(
                        board: board,
                        identity: identity,
                        tone: tone,
                      ),
                    ),
                  if (!locked)
                    _FilterBar(
                      sortLabel: _sortOptions
                          .firstWhere(
                            (o) => o.$1 == sort,
                            orElse: () => _sortOptions.first,
                          )
                          .$2,
                      onSort: () => _chooseSort(context, sort, defaultSort),
                      tags: tags,
                      activeTag: filter.tag,
                      onTag: (tag) =>
                          ref.read(filterProvider.notifier).toggleTag(tag),
                    ),
                  topicsAsync.when(
                    // A change of sort or tag keeps the old rows up until the
                    // new ones land, as a refresh does.
                    skipLoadingOnReload: true,
                    loading: () => const _TopicsSkeleton(),
                    error: (error, _) => locked
                        ? _LockedState(
                            tone: tone,
                            // Replaces this list, so the unlock's own
                            // replacement leaves one forum page, not two.
                            onUnlock: () => context.pushReplacementNamed(
                              'forumUnlock',
                              pathParameters: {'slug': _slug},
                              extra: widget.boardTitle,
                            ),
                          )
                        : _ErrorRetry(
                            message: 'Could not load topics.',
                            onRetry: refresh,
                          ),
                    data: (paged) => _TopicsList(
                      paged: paged,
                      emptyIcon: identity.icon,
                      emptyTone: tone,
                      activeTag: filter.tag,
                      onOpenTopic: (topic) => context.pushNamed(
                        'forumTopic',
                        pathParameters: {'id': '${topic.id}'},
                        extra: topic.title,
                      ),
                      onLoadMore: () =>
                          ref.read(topicsProvider.notifier).loadMore(),
                    ),
                  ),
                  // Under the topics: who posts most here, what is active in
                  // the other forums, who is online (each absent until it has
                  // something to show), then the closing mark.
                  if (!locked) ...[
                    ForumTopContributors(boardSlug: _slug),
                    ForumActiveDiscussions(boardSlug: _slug),
                  ],
                  if (!locked)
                    const Padding(
                      padding: EdgeInsets.only(top: forumSectionGap),
                      child: ForumWhosOnline(),
                    ),
                  const ForumHomeFooter(),
                ],
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: isAuthenticated && !locked
          ? FloatingActionButton.extended(
              onPressed: () => _openComposer(
                context,
                topicsProvider,
                canPoll: board?.canPoll ?? false,
              ),
              icon: const Icon(LucideIcons.plus, size: 15),
              label: const Text('New topic'),
            )
          : null,
    );
  }

  Future<void> _openComposer(
    BuildContext context,
    BoardTopicsProvider topicsProvider, {
    required bool canPoll,
  }) async {
    final result = await context.pushNamed<bool>(
      'forumCompose',
      extra: ForumComposeArgs.topic(
        boardSlug: _slug,
        boardTitle: widget.boardTitle,
        canPoll: canPoll,
      ),
    );
    if (result == true) {
      ref.invalidate(topicsProvider);
      ref.invalidate(categoriesProvider);
    }
  }

  /// The forum switcher: every forum the viewer can see, the open one
  /// ticked. Choosing another replaces this list, so Back still leaves the
  /// forum rather than walking through each one visited.
  Future<void> _switchForum(
    BuildContext context,
    List<ForumBoard> boards,
  ) async {
    final chosen = await showModalBottomSheet<ForumBoard>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => _ForumSwitcherSheet(boards: boards, current: _slug),
    );
    if (chosen == null || chosen.slug == _slug || !context.mounted) return;
    context.pushReplacementNamed(
      'forumBoard',
      pathParameters: {'slug': chosen.slug},
      extra: chosen.title,
    );
  }

  Future<void> _chooseSort(
    BuildContext context,
    String current,
    String defaultSort,
  ) async {
    final chosen = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => _SortSheet(current: current),
    );
    if (chosen == null || !mounted) return;
    // The forum's own order is sent as "no sort", so the server stays the
    // one that decides what the default is.
    ref
        .read(boardTopicsFilterStateProvider(_slug).notifier)
        .setSort(chosen == defaultSort ? null : chosen);
  }
}

String _count(int n, String singular) => '$n $singular${n == 1 ? '' : 's'}';

/// The forum's name in the app bar, as the button that switches forum:
/// the title as plain text, then a small square chevron tile (the shape of
/// the app's other tiles, not a pill).
class _ForumSwitcherButton extends StatelessWidget {
  const _ForumSwitcherButton({required this.title, required this.onTap});

  final String title;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    return Semantics(
      button: true,
      label: '$title. Switch forum',
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.rSm),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Flexible(
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              SizedBox.square(
                dimension: 26,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: canopy.surface2,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: canopy.line2),
                  ),
                  child: Icon(
                    LucideIcons.chevronDown,
                    size: 16,
                    color: canopy.ink2,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The list of forums to switch to, each with its own tile and topic count.
class _ForumSwitcherSheet extends StatelessWidget {
  const _ForumSwitcherSheet({required this.boards, required this.current});

  final List<ForumBoard> boards;
  final String current;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.7,
        ),
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            0,
            AppSpacing.md,
            AppSpacing.md,
          ),
          children: [
            const ForumSectionHeader('Switch forum'),
            for (final board in boards)
              Builder(
                builder: (context) {
                  final identity = boardIdentityOf(board);
                  final selected = board.slug == current;
                  return Semantics(
                    button: true,
                    selected: selected,
                    child: Material(
                      color: selected ? canopy.surface3 : Colors.transparent,
                      borderRadius: BorderRadius.circular(AppSpacing.rTileMd),
                      clipBehavior: Clip.antiAlias,
                      child: InkWell(
                        onTap: () => Navigator.of(context).pop(board),
                        child: Padding(
                          padding: const EdgeInsets.all(10),
                          child: Row(
                            children: [
                              CanopyAccentTile(
                                icon: identity.icon,
                                emoji: identity.emoji,
                                tone: identity.tone.colorOf(canopy),
                                size: 36,
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      board.title,
                                      style: forumItemTitle(context),
                                    ),
                                    Text(
                                      _count(board.topicCount, 'topic'),
                                      style: forumMeta(context),
                                    ),
                                  ],
                                ),
                              ),
                              if (board.isLocked)
                                Icon(
                                  LucideIcons.lock,
                                  size: 16,
                                  color: canopy.ink2,
                                )
                              else if (selected)
                                Icon(
                                  LucideIcons.check,
                                  size: forumChevronSize,
                                  color: Theme.of(context).colorScheme.primary,
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }
}

/// The ways to order the list, the current one ticked.
class _SortSheet extends StatelessWidget {
  const _SortSheet({required this.current});

  final String current;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      // A list, not a column: on a short screen or at a large text size the
      // options scroll instead of overflowing the sheet.
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          AppSpacing.md,
        ),
        children: [
          const ForumSectionHeader('Sort topics'),
          for (final (value, label) in _sortOptions)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(label),
              selected: value == current,
              trailing: value == current
                  ? const Icon(LucideIcons.check, size: forumChevronSize)
                  : null,
              onTap: () => Navigator.of(context).pop(value),
            ),
        ],
      ),
    );
  }
}

/// What the board is for and how busy it is: its tile, description and
/// counts on a card washed in the board's own tone. The first card of the
/// hero carousel.
class _BoardIntro extends StatelessWidget {
  const _BoardIntro({
    required this.board,
    required this.identity,
    required this.tone,
  });

  final ForumBoard board;
  final BoardIdentity identity;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    final onSurface = Theme.of(context).colorScheme.onSurface;
    return ForumHeroCard(
      tone: tone,
      child: Row(
        // Centred: every hero card is as tall as the tallest one.
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          ForumHeroTile(icon: identity.icon, emoji: identity.emoji, tone: tone),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (board.description.isNotEmpty) ...[
                  Text(
                    board.description,
                    style: AppTypography.bodySm.copyWith(color: onSurface),
                  ),
                  const SizedBox(height: 6),
                ],
                Text(
                  '${_count(board.topicCount, 'topic')} · '
                  '${_count(board.postCount, 'post')}',
                  style: forumMeta(
                    context,
                  ).copyWith(color: onSurface, fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The list's tools on one scrolling line: the sort, then a chip per tag
/// seen on this forum's topics. With no tags it is the sort alone.
class _FilterBar extends StatelessWidget {
  const _FilterBar({
    required this.sortLabel,
    required this.onSort,
    required this.tags,
    required this.activeTag,
    required this.onTag,
  });

  final String sortLabel;
  final VoidCallback onSort;
  final List<String> tags;
  final String? activeTag;
  final void Function(String tag) onTag;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        // Bleeds to the screen edges so chips scroll under them, not into
        // the list's margin.
        clipBehavior: Clip.none,
        child: Row(
          children: [
            _ToolChip(
              label: sortLabel,
              icon: LucideIcons.arrowUpDown,
              semanticLabel: 'Sort: $sortLabel',
              filled: true,
              onTap: onSort,
            ),
            for (final tag in tags) ...[
              const SizedBox(width: 6),
              _ToolChip(
                label: '#$tag',
                semanticLabel: 'Tag $tag',
                selected: tag == activeTag,
                filled: tag == activeTag,
                onTap: () => onTag(tag),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// One chip of the [_FilterBar]: a 32pt pill inside a 48pt tap target.
class _ToolChip extends StatelessWidget {
  const _ToolChip({
    required this.label,
    required this.semanticLabel,
    required this.onTap,
    this.icon,
    this.filled = false,
    this.selected,
  });

  final String label;
  final String semanticLabel;
  final VoidCallback onTap;
  final IconData? icon;

  /// Painted in the primary colour: the sort, and the tag in force.
  final bool filled;

  /// For a toggle (a tag): whether it is the one in force.
  final bool? selected;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final colors = Theme.of(context).colorScheme;
    final foreground = filled ? colors.onPrimary : canopy.ink2;
    return Semantics(
      button: true,
      selected: selected,
      label: semanticLabel,
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.rPill),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: Center(
            widthFactor: 1,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: filled ? colors.primary : canopy.surface2,
                borderRadius: BorderRadius.circular(AppSpacing.rPill),
                border: Border.all(
                  color: filled ? colors.primary : canopy.line2,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (icon != null) ...[
                      Icon(icon, size: 14, color: foreground),
                      const SizedBox(width: 6),
                    ],
                    Text(
                      label,
                      style: AppTypography.meta.copyWith(
                        color: foreground,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TopicsList extends StatelessWidget {
  const _TopicsList({
    required this.paged,
    required this.emptyIcon,
    required this.emptyTone,
    required this.activeTag,
    required this.onOpenTopic,
    required this.onLoadMore,
  });

  /// The tag the list is filtered to, if any: an empty result then says so
  /// instead of calling the forum empty.
  final String? activeTag;
  final PagedList<ForumTopicListItem> paged;
  final IconData emptyIcon;
  final Color emptyTone;
  final void Function(ForumTopicListItem topic) onOpenTopic;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty && activeTag != null) {
      return ForumEmptyState(
        icon: LucideIcons.tag,
        tone: emptyTone,
        title: 'No topics tagged #$activeTag',
        body: 'Tap the tag again to see every topic.',
      );
    }
    if (paged.items.isEmpty) {
      return ForumEmptyState(
        icon: emptyIcon,
        tone: emptyTone,
        title: 'No topics yet',
        body: 'Be the first to post.',
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

/// Six rows shaped like topic rows: an avatar square and two lines.
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
              decoration: BoxDecoration(
                color: fill,
                borderRadius: forumAvatarRadius(34),
              ),
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

/// In place of the topics when the forum needs a password: a lock, one
/// line and an Unlock button.
class _LockedState extends StatelessWidget {
  const _LockedState({required this.tone, required this.onUnlock});
  final Color tone;
  final VoidCallback onUnlock;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl2),
      child: Column(
        children: [
          CanopyAccentTile(icon: LucideIcons.lock, tone: tone, size: 48),
          const SizedBox(height: AppSpacing.md),
          Text(
            'This forum needs a password.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.md),
          ClayButton(label: 'Unlock', onPressed: onUnlock),
        ],
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
