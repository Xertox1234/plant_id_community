import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../services/auth_service.dart';
import '../../shared/widgets/brand_mark.dart';
import '../../shared/widgets/canopy_accents.dart';
import '../../shared/widgets/canopy_surfaces.dart';
import 'providers/forum_providers.dart';
import 'widgets/forum_experts_strip.dart';
import 'widgets/home/forum_activity_card.dart';
import 'widgets/home/forum_boards_section.dart';
import 'widgets/home/forum_home_footer.dart';
import 'widgets/home/forum_season_card.dart';
import 'widgets/home/forum_whos_online.dart';

/// Gap between home sections (design: 30pt; nearest token).
const double _sectionGap = AppSpacing.xl;

/// First-visit entrance (spec §8.2): each section fades in and rises 8pt,
/// 40 ms after the one above it.
const Duration _stagger = Duration(milliseconds: 40);
const Duration _sectionFade = Duration(milliseconds: 200);
const int _slotCount = 6;
const double _rise = 8;

/// Community forum home (spec 2026-11-02 §5): your season, experts, boards,
/// recent activity, who's online and the footer, top to bottom.
class ForumScreen extends ConsumerStatefulWidget {
  const ForumScreen({super.key});

  @override
  ConsumerState<ForumScreen> createState() => _ForumScreenState();
}

class _ForumScreenState extends ConsumerState<ForumScreen>
    with SingleTickerProviderStateMixin {
  /// Runs once per mount. A refresh rebuilds the sections, not this state, so
  /// the entrance never replays; a section first built by scrolling reads the
  /// finished value and appears without animating.
  late final AnimationController _entrance = AnimationController(
    vsync: this,
    duration: _stagger * (_slotCount - 1) + _sectionFade,
  )..forward();

  @override
  void dispose() {
    _entrance.dispose();
    super.dispose();
  }

  Future<void> _refresh(bool isAuthenticated) async {
    ref.read(expandedActivityTopicProvider.notifier).collapse();
    ref.invalidate(boardsProvider);
    ref.invalidate(homeRecentTopicsProvider);
    ref.invalidate(latestRepliesProvider);
    ref.invalidate(communityStatsProvider);
    ref.invalidate(expertsProvider);
    ref.invalidate(recentTopicsProvider);
    // Auth-only: never refetch the stats for a signed-out viewer.
    if (isAuthenticated) ref.invalidate(meStatsProvider);
  }

  @override
  Widget build(BuildContext context) {
    // The offline mirror (delta sync) is no longer shown here, but opening
    // the forum is still what syncs it: keep it alive without rendering it
    // (spec §6.2, "keep the offline sync mirror as is"). It never throws.
    ref.listen(recentTopicsProvider, (_, _) {});
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    final showOnline = ref.watch(
      communityStatsProvider.select((a) => a.asData != null),
    );

    Widget slot(int index, Widget child) =>
        _Arrive(entrance: _entrance, index: index, child: child);

    return Scaffold(
      appBar: AppBar(
        centerTitle: false,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // The title already names the screen; the mark is decoration.
            const ExcludeSemantics(child: BrandMark(size: 28)),
            const SizedBox(width: 10),
            Flexible(
              child: Text(
                'Community',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Search',
            onPressed: () => context.pushNamed('forumSearch'),
            icon: const Icon(LucideIcons.search),
          ),
          if (isAuthenticated) ...[
            IconButton(
              tooltip: 'Bookmarks',
              onPressed: () => context.pushNamed('forumBookmarks'),
              icon: const Icon(LucideIcons.bookmark),
            ),
            const _MessagesInboxButton(),
            const _NotificationsBellButton(),
          ],
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _refresh(isAuthenticated),
          // ONE Column child, not a section per ListView child: a lazily
          // built section is disposed off screen, which drops its autoDispose
          // provider and refetches (skeleton flash, scroll jump) on the way
          // back up. A ListView, not a SingleChildScrollView, so the scroll
          // view fills the body (and pull-to-refresh works) on a short page.
          child: ListView(
            padding:
                const EdgeInsets.all(AppSpacing.md) +
                MainShell.fabClearanceOf(context),
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (isAuthenticated) slot(0, const _YourSeasonSection()),
                  slot(1, const _ExpertsSection()),
                  slot(
                    2,
                    const Padding(
                      padding: EdgeInsets.only(bottom: _sectionGap),
                      child: _BoardsSection(),
                    ),
                  ),
                  slot(
                    3,
                    const Padding(
                      padding: EdgeInsets.only(bottom: _sectionGap),
                      child: _RecentActivitySection(),
                    ),
                  ),
                  if (showOnline)
                    slot(
                      4,
                      const Padding(
                        padding: EdgeInsets.only(bottom: _sectionGap),
                        child: ForumWhosOnline(),
                      ),
                    ),
                  slot(5, const ForumHomeFooter()),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One section's share of the first-visit entrance: a fade plus an 8pt rise
/// on emphasized-decelerate, starting [index] staggers in. Under reduced
/// motion it only fades.
class _Arrive extends StatelessWidget {
  const _Arrive({
    required this.entrance,
    required this.index,
    required this.child,
  });

  final Animation<double> entrance;
  final int index;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final total = (_stagger * (_slotCount - 1) + _sectionFade).inMicroseconds;
    final start = (_stagger * index).inMicroseconds / total;
    final end = (_stagger * index + _sectionFade).inMicroseconds / total;
    final interval = Interval(start, end, curve: Easing.emphasizedDecelerate);
    final rise = !MediaQuery.disableAnimationsOf(context);
    return AnimatedBuilder(
      animation: entrance,
      child: child,
      builder: (context, child) {
        if (entrance.isCompleted) return child!;
        final t = interval.transform(entrance.value);
        return Opacity(
          opacity: t,
          // A screen reader must not lose the sections while they fade in.
          alwaysIncludeSemantics: true,
          child: rise
              ? Transform.translate(
                  offset: Offset(0, _rise * (1 - t)),
                  child: child,
                )
              : child,
        );
      },
    );
  }
}

/// "Your season" (`GET me/stats/`, todo 341 wave 4). Only mounted when
/// signed in — the endpoint is auth-only. The card carries its own eyebrow.
class _YourSeasonSection extends ConsumerWidget {
  const _YourSeasonSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statsAsync = ref.watch(meStatsProvider);
    return Padding(
      padding: const EdgeInsets.only(bottom: _sectionGap),
      child: statsAsync.when(
        loading: () => const _SeasonSkeleton(),
        error: (error, _) => _SectionError(
          message: 'Could not load your stats.',
          onRetry: () => ref.invalidate(meStatsProvider),
        ),
        data: (stats) => ForumSeasonCard(stats: stats),
      ),
    );
  }
}

/// "Experts" strip with the online dot (`GET users/experts/`, todo 341 wave
/// 4). A rail, not a feed: while loading, on error, or when the site has no
/// experts yet it renders nothing rather than adding noise to the home.
class _ExpertsSection extends ConsumerWidget {
  const _ExpertsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final experts = ref.watch(expertsProvider).asData?.value ?? const [];
    if (experts.isEmpty) return const SizedBox.shrink();
    final online = experts.where((e) => e.online).length;
    return Padding(
      padding: const EdgeInsets.only(bottom: _sectionGap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(online > 0 ? 'Experts · $online online' : 'Experts'),
          ForumExpertsStrip(
            experts: experts,
            onTap: (expert) => context.pushNamed(
              'forumUserProfile',
              pathParameters: {'username': expert.author.username},
            ),
          ),
        ],
      ),
    );
  }
}

class _BoardsSection extends ConsumerWidget {
  const _BoardsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final boardsAsync = ref.watch(boardsProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _SectionHeader('Boards'),
        boardsAsync.when(
          loading: () => const _BoardsSkeleton(),
          error: (error, _) => _SectionError(
            message: 'Could not load boards.',
            onRetry: () => ref.invalidate(boardsProvider),
          ),
          data: (boards) => boards.isEmpty
              ? const _EmptyLine('No boards yet.')
              : ForumBoardsSection(
                  boards: boards,
                  onTap: (board) => context.pushNamed(
                    'forumBoard',
                    pathParameters: {'slug': board.slug},
                    extra: board.title,
                  ),
                ),
        ),
      ],
    );
  }
}

/// Recent activity: up to ten cards from `GET forum/topics/recent/`. No
/// "View all": forum search cannot sort by latest activity yet, so there is
/// no list for it to open.
class _RecentActivitySection extends ConsumerWidget {
  const _RecentActivitySection();

  static const int _maxTopics = 10;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recentAsync = ref.watch(homeRecentTopicsProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _SectionHeader('Recent activity'),
        recentAsync.when(
          loading: () => const _ActivitySkeleton(),
          error: (error, _) => _SectionError(
            message: 'Could not load recent topics.',
            onRetry: () => ref.invalidate(homeRecentTopicsProvider),
          ),
          data: (topics) => topics.isEmpty
              ? const _EmptyLine('Nothing here yet.')
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final (i, topic) in topics.take(_maxTopics).indexed)
                      Padding(
                        key: ValueKey(topic.id),
                        padding: EdgeInsets.only(
                          top: i == 0 ? 0 : AppSpacing.sm + AppSpacing.xs,
                        ),
                        child: ForumActivityCard(
                          topic: topic,
                          onOpen: () => context.pushNamed(
                            'forumTopic',
                            pathParameters: {'id': '${topic.id}'},
                            extra: topic.title,
                          ),
                        ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }
}

/// Inbox icon with an unread-conversation badge, opening the DM inbox
/// (todo 339). Sits beside the bell so the two private feeds read as a pair.
class _MessagesInboxButton extends ConsumerWidget {
  const _MessagesInboxButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadAsync = ref.watch(unreadConversationCountProvider);
    final unread = unreadAsync.asData?.value ?? 0;
    return IconButton(
      tooltip: 'Messages',
      onPressed: () => context.pushNamed('forumMessages'),
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text('$unread'),
        child: const Icon(LucideIcons.mail),
      ),
    );
  }
}

/// Bell icon with an unread-count badge, opening the notifications screen.
class _NotificationsBellButton extends ConsumerWidget {
  const _NotificationsBellButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadAsync = ref.watch(unreadNotificationCountProvider);
    final unread = unreadAsync.asData?.value ?? 0;
    return IconButton(
      tooltip: 'Notifications',
      onPressed: () => context.pushNamed('forumNotifications'),
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text('$unread'),
        child: const Icon(LucideIcons.bell),
      ),
    );
  }
}

/// Section heading in the display face, matching "Who's online".
class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.title);
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Semantics(
        header: true,
        child: Text(
          title,
          style: AppTypography.h3.copyWith(
            color: Theme.of(context).colorScheme.onSurface,
          ),
        ),
      ),
    );
  }
}

/// A rounded placeholder bar for the skeletons.
class _Bar extends StatelessWidget {
  const _Bar({required this.widthFactor, this.height = 10});

  final double widthFactor;
  final double height;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      alignment: Alignment.centerLeft,
      widthFactor: widthFactor,
      child: SizedBox(
        height: height,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: context.canopy.surface3,
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
          ),
        ),
      ),
    );
  }
}

/// Announces [label] once and hides the placeholder shapes from a reader.
class _Skeleton extends StatelessWidget {
  const _Skeleton({required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: label,
      child: ExcludeSemantics(child: child),
    );
  }
}

class _SeasonSkeleton extends StatelessWidget {
  const _SeasonSkeleton();

  @override
  Widget build(BuildContext context) {
    return const _Skeleton(
      label: 'Loading your stats',
      child: CanopyCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Bar(widthFactor: 0.3, height: 8),
            SizedBox(height: AppSpacing.md),
            _Bar(widthFactor: 0.9, height: 24),
            SizedBox(height: AppSpacing.md),
            _Bar(widthFactor: 0.6),
          ],
        ),
      ),
    );
  }
}

/// Three rows shaped like board rows: a 40pt tile and two lines.
class _BoardsSkeleton extends StatelessWidget {
  const _BoardsSkeleton();

  @override
  Widget build(BuildContext context) {
    final fill = context.canopy.surface3;
    Widget row(double width) => Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: 12,
      ),
      child: Row(
        children: [
          SizedBox.square(
            dimension: 40,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: fill,
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Bar(widthFactor: width, height: 12),
                const SizedBox(height: 8),
                const _Bar(widthFactor: 0.35, height: 8),
              ],
            ),
          ),
        ],
      ),
    );
    return _Skeleton(
      label: 'Loading boards',
      child: CanopyGroupedCard(rows: [row(0.7), row(0.5), row(0.6)]),
    );
  }
}

/// Three cards shaped like activity cards: chip, title, meta.
class _ActivitySkeleton extends StatelessWidget {
  const _ActivitySkeleton();

  @override
  Widget build(BuildContext context) {
    Widget card(double width) => CanopyCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _Bar(widthFactor: 0.25, height: 14),
          const SizedBox(height: 10),
          _Bar(widthFactor: width, height: 14),
          const SizedBox(height: 10),
          const _Bar(widthFactor: 0.4, height: 8),
        ],
      ),
    );
    return _Skeleton(
      label: 'Loading recent topics',
      child: Column(
        children: [
          card(0.85),
          const SizedBox(height: AppSpacing.sm + AppSpacing.xs),
          card(0.65),
          const SizedBox(height: AppSpacing.sm + AppSpacing.xs),
          card(0.75),
        ],
      ),
    );
  }
}

class _SectionError extends StatelessWidget {
  const _SectionError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          Expanded(child: Text(message)),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}

/// A quiet empty state with the leaf mark.
class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          ExcludeSemantics(
            child: Icon(
              LucideIcons.leaf,
              size: AppSpacing.iconSM,
              color: canopy.ink3,
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              text,
              style: AppTypography.bodySm.copyWith(color: canopy.ink2),
            ),
          ),
        ],
      ),
    );
  }
}
