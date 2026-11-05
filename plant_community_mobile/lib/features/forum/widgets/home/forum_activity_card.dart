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
import 'forum_latest_replies_view.dart';

/// Open: height grows on emphasized-decelerate (spec §8.3).
const Duration _openDuration = Duration(milliseconds: 250);

/// Close: a little quicker, on emphasized-accelerate.
const Duration _closeDuration = Duration(milliseconds: 200);

/// The content waits this long after the height starts growing.
const Duration _fadeDelay = Duration(milliseconds: 80);

/// One topic in the forum home's Recent activity.
///
/// A topic with a picture is a **picture card**: tapping it calls [onOpen]
/// and it never expands. Any other topic is a **text card**: tapping it
/// expands it in place to show the latest replies
/// ([ForumLatestRepliesView]); one card is open at a time
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
    if (topic.hasPicture) {
      return _PictureCard(topic: topic, onOpen: onOpen);
    }
    final expanded = ref.watch(
      expandedActivityTopicProvider.select((open) => open == topic.id),
    );
    return _TextCard(
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

/// The words a screen reader hears for the card's header.
String _cardLabel(
  ForumRecentTopic topic,
  String chip, {
  required bool includeState,
}) {
  final time = forumRelativeTime(topic.lastPostAt);
  return [
    chip,
    topic.title,
    _replies(topic.replyCount),
    if (time.isNotEmpty) time,
    if (includeState && topic.isSolved) 'Solved',
    if (includeState && topic.isUnread) 'New replies',
  ].join(', ');
}

class _BoardChip extends StatelessWidget {
  const _BoardChip({required this.topic});

  final ForumRecentTopic topic;

  @override
  Widget build(BuildContext context) {
    final identity = boardIdentity(
      topic.board.slug,
      fallbackLabel: topic.board.title,
    );
    return CanopyChip(
      label: identity.chipLabel,
      tone: identity.tone.colorOf(context.canopy),
      icon: identity.icon,
    );
  }
}

/// Reply count and time, in Geist Mono.
class _Meta extends StatelessWidget {
  const _Meta({required this.topic, this.trailing});

  final ForumRecentTopic topic;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final style = AppTypography.label.copyWith(color: canopy.ink3);
    final time = forumRelativeTime(topic.lastPostAt);
    // A Wrap: at large text the pieces drop to a second line, never clip.
    return Wrap(
      spacing: 14,
      runSpacing: 4,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(LucideIcons.messageCircle, size: 14, color: canopy.ink3),
            const SizedBox(width: 5),
            Text('${topic.replyCount}', style: style),
          ],
        ),
        if (time.isNotEmpty) Text(time, style: style),
        ?trailing,
      ],
    );
  }
}

class _PictureCard extends StatelessWidget {
  const _PictureCard({required this.topic, required this.onOpen});

  final ForumRecentTopic topic;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canopy = context.canopy;
    final identity = boardIdentity(
      topic.board.slug,
      fallbackLabel: topic.board.title,
    );
    // Decode no wider than the screen needs (the card is never wider).
    final cacheWidth =
        (MediaQuery.sizeOf(context).width *
                MediaQuery.devicePixelRatioOf(context))
            .round();
    return CanopyPressable(
      onTap: onOpen,
      style: CanopyPressStyle.scale,
      semanticLabel: _cardLabel(topic, identity.chipLabel, includeState: false),
      child: CanopyCard(
        padding: const EdgeInsets.all(14),
        child: ExcludeSemantics(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: _BoardChip(topic: topic),
              ),
              const SizedBox(height: 10),
              Text(topic.title, style: theme.textTheme.titleLarge),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(AppSpacing.rSm),
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: CachedNetworkImage(
                    imageUrl: topic.imageUrl!,
                    fit: BoxFit.cover,
                    memCacheWidth: cacheWidth,
                    placeholder: (context, _) =>
                        ColoredBox(color: canopy.surface3),
                    // Keep the card's height when the image fails.
                    errorWidget: (context, _, _) => ColoredBox(
                      color: canopy.surface3,
                      child: Center(
                        child: Icon(
                          LucideIcons.imageOff,
                          size: 20,
                          color: canopy.ink3,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(child: _Meta(topic: topic)),
                  Icon(LucideIcons.chevronRight, size: 16, color: canopy.ink3),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TextCard extends StatelessWidget {
  const _TextCard({
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
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canopy = context.canopy;
    final reduce = MediaQuery.disableAnimationsOf(context);
    final identity = boardIdentity(
      topic.board.slug,
      fallbackLabel: topic.board.title,
    );
    final header = ExcludeSemantics(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Row(
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
              ),
              AnimatedRotation(
                turns: expanded ? 0.5 : 0,
                duration: reduce
                    ? Duration.zero
                    : (expanded ? _openDuration : _closeDuration),
                curve: expanded
                    ? Easing.emphasizedDecelerate
                    : Easing.emphasizedAccelerate,
                child: Icon(
                  LucideIcons.chevronDown,
                  size: 18,
                  color: canopy.ink3,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(topic.title, style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
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
    );
    return CanopyPressable(
      onTap: onToggle,
      style: CanopyPressStyle.scale,
      expanded: expanded,
      semanticLabel: _cardLabel(topic, identity.chipLabel, includeState: true),
      child: CanopyCard(
        padding: const EdgeInsets.all(14),
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
