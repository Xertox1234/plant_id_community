import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_accents.dart';
import '../../../../shared/widgets/canopy_surfaces.dart';
import '../../forum_format.dart';
import '../../models/models.dart';
import '../../providers/forum_providers.dart';
import '../../utils/board_identity.dart';
import '../author_identity.dart';
import '../forum_style.dart';
import 'forum_latest_replies_view.dart';

/// Open: height grows on emphasized-decelerate (spec §8.3).
const Duration _openDuration = Duration(milliseconds: 250);

/// Close: a little quicker, on emphasized-accelerate.
const Duration _closeDuration = Duration(milliseconds: 200);

/// The content waits this long after the height starts growing.
const Duration _fadeDelay = Duration(milliseconds: 80);

/// Side of one picture in the collapsed card's stack.
const double _thumbSize = 56;

/// How far each picture behind the first one shows.
const double _thumbPeek = 10;

/// One topic in the forum home's Recent activity.
///
/// Every card starts **collapsed**: board chip, title, reply count and time,
/// with the opening post's pictures stacked at the trailing edge
/// ([ForumRecentTopic.thumbnails]) and, once two or more people have
/// replied, their avatars stacked beside the count. Tapping it expands it in
/// place to show the latest replies ([ForumLatestRepliesView], which holds
/// the "Open topic" button); one card is open at a time
/// ([expandedActivityTopicProvider]).
class ForumActivityCard extends ConsumerWidget {
  const ForumActivityCard({
    super.key,
    required this.topic,
    required this.onOpen,
  });

  final ForumRecentTopic topic;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final expanded = ref.watch(
      expandedActivityTopicProvider.select((open) => open == topic.id),
    );
    return _Card(
      topic: topic,
      expanded: expanded,
      onToggle: () {
        HapticFeedback.selectionClick();
        ref.read(expandedActivityTopicProvider.notifier).toggle(topic.id);
      },
      onOpen: onOpen,
    );
  }
}

String _replies(int n) => '$n ${n == 1 ? 'reply' : 'replies'}';

/// Identity of [topic]'s board: the server's icon and colour when the board is
/// in the (already loaded) forum feed, the slug's default icon and tone when
/// it is there but still locked for the viewer (see [boardIdentityOf]), else
/// the slug's. Never waits on the feed and never starts a request: it only
/// reads what the home already fetched.
BoardIdentity _identityOf(WidgetRef ref, ForumRecentTopic topic) {
  final slug = topic.board.slug;
  final board = ref.watch(
    viewerCategoriesProvider.select(
      (feed) => feed.value
          ?.expand((c) => c.forums)
          .where((f) => f.slug == slug)
          .firstOrNull,
    ),
  );
  return board != null
      ? boardIdentityOf(board)
      : boardIdentity(topic.board.slug, fallbackLabel: topic.board.title);
}

/// The words a screen reader hears for the card's header.
String _cardLabel(ForumRecentTopic topic, String chip) {
  final time = forumListTime(topic.lastPostAt);
  final photos = topic.thumbnails.length;
  return [
    chip,
    topic.title,
    _replies(topic.replyCount),
    if (time.isNotEmpty) time,
    if (photos > 0) photos == 1 ? 'Has a photo' : 'Has photos',
    if (topic.isSolved) 'Solved',
    if (topic.isUnread) 'New replies',
  ].join(', ');
}

class _BoardChip extends ConsumerWidget {
  const _BoardChip({required this.topic});

  final ForumRecentTopic topic;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final identity = _identityOf(ref, topic);
    return CanopyChip(
      label: identity.chipLabel,
      tone: identity.tone.colorOf(context.canopy),
      icon: identity.icon,
      emoji: identity.emoji,
    );
  }
}

/// Who replied, reply count and time, in the home's detail style.
class _Meta extends StatelessWidget {
  const _Meta({required this.topic, this.trailing});

  final ForumRecentTopic topic;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final style = forumMeta(context);
    final time = forumListTime(topic.lastPostAt);
    // One avatar says nothing the count does not: the stack is for a thread
    // with several voices.
    final distinct = {for (final a in topic.repliers) a.username}.length;
    final repliers = distinct >= 2 ? topic.repliers : const <ForumAuthor>[];
    // A Wrap: at large text the pieces drop to a second line, never clip.
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.xs,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (repliers.isNotEmpty) ...[
              _ReplierStack(authors: repliers),
              const SizedBox(width: 6),
            ] else ...[
              Icon(LucideIcons.messageCircle, size: 14, color: canopy.ink2),
              const SizedBox(width: 6),
            ],
            // The count always says what it counts. One Text with the
            // time, so the separator's spacing is the font's, not the Wrap's.
            Flexible(
              child: Text(
                time.isEmpty
                    ? _replies(topic.replyCount)
                    : '${_replies(topic.replyCount)} · $time',
                style: style,
              ),
            ),
          ],
        ),
        ?trailing,
      ],
    );
  }
}

/// The latest repliers' avatars, overlapping. Decoration only: the card's
/// label already says how many replies there are.
class _ReplierStack extends StatelessWidget {
  const _ReplierStack({required this.authors});

  final List<ForumAuthor> authors;

  static const int _max = 3;
  static const double _radius = 10;
  static const double _ring = 1.5;

  @override
  Widget build(BuildContext context) {
    // Each person once, whoever built the list.
    final seen = <String>{};
    final shown = [
      for (final author in authors)
        if (seen.add(author.username)) author,
    ].take(_max).toList(growable: false);
    const size = (_radius + _ring) * 2;
    const step = _radius * 1.3;
    return SizedBox(
      width: size + step * (shown.length - 1),
      height: size,
      child: Stack(
        children: [
          // Painted last-to-first so the newest replier sits on top.
          for (var i = shown.length - 1; i >= 0; i--)
            Positioned(
              left: i * step,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: forumAvatarRadius(_radius * 2),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.surface,
                    width: _ring,
                  ),
                ),
                child: AuthorAvatar(author: shown[i], radius: _radius),
              ),
            ),
        ],
      ),
    );
  }
}

/// The opening post's pictures as a small stack: the first one in front, the
/// others peeking out behind it to the right.
class _ThumbnailStack extends StatelessWidget {
  const _ThumbnailStack({required this.urls});

  final List<String> urls;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    // Decode at the size drawn, not the size sent.
    final cacheWidth = (_thumbSize * MediaQuery.devicePixelRatioOf(context))
        .round();
    final count = urls.length;

    Widget picture(int i) {
      // Each one behind is a little smaller, so the stack reads as depth.
      final side = _thumbSize - i * 8;
      return Positioned(
        left: i * _thumbPeek + (i * 8),
        top: i * 4,
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppSpacing.rSm),
            border: Border.all(
              color: Theme.of(context).colorScheme.surface,
              width: 1.5,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(1.5),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(AppSpacing.rSm - 1.5),
              child: SizedBox.square(
                dimension: side - 3,
                child: CachedNetworkImage(
                  imageUrl: urls[i],
                  fit: BoxFit.cover,
                  memCacheWidth: cacheWidth,
                  placeholder: (context, _) =>
                      ColoredBox(color: canopy.surface3),
                  // Keep the slot when the image fails.
                  errorWidget: (context, _, _) => ColoredBox(
                    color: canopy.surface3,
                    child: Center(
                      child: Icon(
                        LucideIcons.imageOff,
                        size: 16,
                        color: canopy.ink3,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    }

    return SizedBox(
      width: _thumbSize + (count - 1) * _thumbPeek,
      height: _thumbSize,
      child: Stack(
        clipBehavior: Clip.none,
        children: [for (var i = count - 1; i >= 0; i--) picture(i)],
      ),
    );
  }
}

class _Card extends ConsumerWidget {
  const _Card({
    required this.topic,
    required this.expanded,
    required this.onToggle,
    required this.onOpen,
  });

  final ForumRecentTopic topic;
  final bool expanded;
  final VoidCallback onToggle;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canopy = context.canopy;
    final reduce = MediaQuery.disableAnimationsOf(context);
    final identity = _identityOf(ref, topic);
    final thumbnails = topic.thumbnails;
    final chevron = AnimatedRotation(
      turns: expanded ? 0.5 : 0,
      duration: reduce
          ? Duration.zero
          : (expanded ? _openDuration : _closeDuration),
      curve: expanded
          ? Easing.emphasizedDecelerate
          : Easing.emphasizedAccelerate,
      child: Icon(
        LucideIcons.chevronDown,
        size: forumChevronSize,
        color: canopy.ink2,
      ),
    );
    // One row, top-aligned: the text block, the pictures, then the chevron
    // on the same edge as every other chevron on the home.
    final header = ExcludeSemantics(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(child: _BoardChip(topic: topic)),
                    const SizedBox(width: AppSpacing.sm),
                    if (topic.isSolved)
                      Flexible(
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              LucideIcons.circleCheck,
                              size: 13,
                              color: canopy.leaf,
                            ),
                            const SizedBox(width: 4),
                            Flexible(
                              child: Text(
                                'Solved',
                                style: AppTypography.micro.copyWith(
                                  color: canopy.leaf,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      )
                    else if (topic.isUnread)
                      SizedBox.square(
                        dimension: 8,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: canopy.clay,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  topic.title,
                  style: forumItemTitle(context),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: AppSpacing.xs),
                _Meta(
                  topic: topic,
                  trailing: topic.isUnread
                      ? Text(
                          'New replies',
                          style: AppTypography.micro.copyWith(
                            color: canopy.clay,
                            fontWeight: FontWeight.w600,
                          ),
                        )
                      : null,
                ),
              ],
            ),
          ),
          if (thumbnails.isNotEmpty) ...[
            const SizedBox(width: AppSpacing.md),
            _ThumbnailStack(urls: thumbnails),
          ],
          const SizedBox(width: AppSpacing.sm),
          chevron,
        ],
      ),
    );
    return CanopyPressable(
      onTap: onToggle,
      style: CanopyPressStyle.scale,
      expanded: expanded,
      semanticLabel: _cardLabel(topic, identity.chipLabel),
      child: CanopyCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            header,
            // Its own semantics subtree: the replies are read as content and
            // "Open topic" is its own control, not part of the card's label.
            Semantics(
              container: true,
              child: _ExpandingBody(
                expanded: expanded,
                reduce: reduce,
                child: Padding(
                  padding: const EdgeInsets.only(top: 14),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      border: Border(top: BorderSide(color: canopy.line)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: ForumLatestRepliesView(
                        topicId: topic.id,
                        onOpen: onOpen,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Grows to [child]'s height and fades it in when [expanded]; fades it out
/// and shrinks when not. One controller drives both, so a tap mid-animation
/// reverses from where it is, and the content is only built while open or
/// closing (the replies are fetched on first open, not on first paint).
///
/// Under reduced motion the height snaps; the content still fades (opacity
/// only, spec §8.3).
class _ExpandingBody extends StatefulWidget {
  const _ExpandingBody({
    required this.expanded,
    required this.reduce,
    required this.child,
  });

  final bool expanded;
  final bool reduce;
  final Widget child;

  @override
  State<_ExpandingBody> createState() => _ExpandingBodyState();
}

class _ExpandingBodyState extends State<_ExpandingBody>
    with TickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _openDuration,
    reverseDuration: _closeDuration,
    value: widget.expanded ? 1 : 0,
  )..addStatusListener((_) => setState(() {}));

  late final Animation<double> _size = CurvedAnimation(
    parent: _controller,
    curve: Easing.emphasizedDecelerate,
    reverseCurve: Easing.emphasizedAccelerate,
  );

  // Opening: the fade starts 80 ms in. Closing (the same interval run
  // backwards): the content is gone well before the height finishes.
  late final Animation<double> _fade = CurvedAnimation(
    parent: _controller,
    curve: Interval(
      _fadeDelay.inMicroseconds / _openDuration.inMicroseconds,
      1,
    ),
  );

  // Under reduced motion only the opacity moves.
  late final AnimationController _reducedFade = AnimationController(
    vsync: this,
    duration: Durations.short3,
    value: widget.expanded ? 1 : 0,
  );

  @override
  void didUpdateWidget(_ExpandingBody old) {
    super.didUpdateWidget(old);
    if (widget.expanded == old.expanded) return;
    if (widget.reduce) {
      _controller.value = widget.expanded ? 1 : 0;
      if (widget.expanded) {
        _reducedFade.forward(from: 0);
      } else {
        _reducedFade.value = 0;
      }
    } else if (widget.expanded) {
      _controller.forward();
    } else {
      _controller.reverse();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _reducedFade.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_controller.isDismissed) return const SizedBox(width: double.infinity);
    if (widget.reduce) {
      return FadeTransition(opacity: _reducedFade, child: widget.child);
    }
    return ClipRect(
      child: SizeTransition(
        sizeFactor: _size,
        // `alignment: Alignment.topLeft` is the replacement, but Flutter
        // 3.41.x has no `alignment` here; migrate once no local SDK is < 3.47.
        // ignore: deprecated_member_use
        axisAlignment: -1,
        child: FadeTransition(opacity: _fade, child: widget.child),
      ),
    );
  }
}
