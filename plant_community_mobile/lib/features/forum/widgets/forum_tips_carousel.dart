import 'dart:async';

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../shared/widgets/canopy_accents.dart';
import '../utils/board_identity.dart';
import 'forum_style.dart';

/// One card of the [ForumTipsCarousel]: a short tip about the forum, the app
/// or premium, optionally with one action.
class ForumTip {
  const ForumTip({
    required this.id,
    required this.icon,
    required this.tone,
    required this.title,
    required this.body,
    this.actionLabel,
    this.routeName,
  });

  /// Stable name, for keys and tests.
  final String id;
  final IconData icon;
  final CanopyTone tone;
  final String title;
  final String body;

  /// The action's words and the named route it opens; both or neither.
  final String? actionLabel;
  final String? routeName;
}

/// The tips to show this viewer, most personal first. They are about the
/// whole forum and the app, not one board, so every board shows the same set.
///
/// [hasAvatar] and [isPremium] are `null` while unknown (signed out, still
/// loading, or the request failed): a tip that depends on one is then left
/// out rather than guessed. [premiumDailyChecks] is the server's premium
/// diagnosis allowance, quoted in the premium tip.
List<ForumTip> forumTipsFor({
  required bool signedIn,
  bool? hasAvatar,
  bool? isPremium,
  int? premiumDailyChecks,
}) {
  return [
    if (!signedIn)
      const ForumTip(
        id: 'sign-in',
        icon: LucideIcons.logIn,
        tone: CanopyTone.sage,
        title: 'Join the conversation',
        body: 'Sign in to post, reply and bookmark topics.',
        actionLabel: 'Sign in',
        routeName: 'login',
      ),
    if (signedIn && hasAvatar == false)
      const ForumTip(
        id: 'add-avatar',
        icon: LucideIcons.circleUser,
        tone: CanopyTone.orchid,
        title: 'Add a photo to your profile',
        body:
            'A face or a favourite plant helps other members recognise '
            'you, and makes the forum feel more welcoming.',
        actionLabel: 'Edit profile',
        routeName: 'editProfile',
      ),
    if (signedIn && isPremium == false && premiumDailyChecks != null)
      ForumTip(
        id: 'premium-checks',
        icon: LucideIcons.sparkles,
        tone: CanopyTone.pollen,
        title: 'More health checks with premium',
        body:
            'Premium members get $premiumDailyChecks plant health checks '
            'a day.',
      ),
    const ForumTip(
      id: 'search-first',
      icon: LucideIcons.search,
      tone: CanopyTone.sage,
      title: 'Search before you post',
      body: 'Someone may have asked already. Search covers every forum.',
      actionLabel: 'Search the forum',
      routeName: 'forumSearch',
    ),
    const ForumTip(
      id: 'good-photos',
      icon: LucideIcons.camera,
      tone: CanopyTone.bloom,
      title: 'Good photos get faster answers',
      body:
          'Show the whole plant, then a leaf up close, in daylight if '
          'you can.',
    ),
    if (signedIn)
      const ForumTip(
        id: 'bookmarks',
        icon: LucideIcons.bookmark,
        tone: CanopyTone.pollen,
        title: 'Save a topic for later',
        body: 'Bookmark a topic from its top bar to find it again.',
        actionLabel: 'Open bookmarks',
        routeName: 'forumBookmarks',
      ),
    if (signedIn)
      const ForumTip(
        id: 'mark-solved',
        icon: LucideIcons.circleCheck,
        tone: CanopyTone.sage,
        title: 'Mark what solved it',
        body:
            'When a reply answers your question, mark it as the solution '
            'so the next person finds it.',
      ),
  ];
}

/// The hero at the top of a board: [intro] (the board's own card) first, then
/// one card per tip, one at a time. It moves on by itself every few seconds,
/// on a sideways swipe, or on a tap of a dot; it holds still while reduced
/// motion is on, and after the viewer has moved it by hand.
class ForumTipsCarousel extends StatefulWidget {
  const ForumTipsCarousel({
    super.key,
    this.intro,
    required this.tips,
    required this.onAction,
    this.interval = const Duration(seconds: 7),
  });

  /// The board's identity card, shown first. Absent while the board is
  /// unknown; the tips then stand alone.
  final Widget? intro;
  final List<ForumTip> tips;

  /// Called with a tip's [ForumTip.routeName] when its action is tapped.
  final void Function(String routeName) onAction;
  final Duration interval;

  @override
  State<ForumTipsCarousel> createState() => _ForumTipsCarouselState();
}

class _ForumTipsCarouselState extends State<ForumTipsCarousel> {
  int _index = 0;
  Timer? _timer;

  /// Set once the viewer picks a card: the carousel then stays where it was
  /// put instead of moving off under their thumb.
  bool _held = false;

  int get _count => widget.tips.length + (widget.intro == null ? 0 : 1);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _schedule();
  }

  @override
  void didUpdateWidget(ForumTipsCarousel oldWidget) {
    super.didUpdateWidget(oldWidget);
    // A tip can leave (the viewer adds an avatar): never point past the end.
    if (_index >= _count) _index = 0;
    _schedule();
  }

  void _schedule() {
    _timer?.cancel();
    _timer = null;
    if (_held || _count < 2 || MediaQuery.disableAnimationsOf(context)) return;
    _timer = Timer.periodic(widget.interval, (_) {
      if (mounted) setState(() => _index = (_index + 1) % _count);
    });
  }

  void _goTo(int index) {
    setState(() {
      _index = index % _count;
      _held = true;
    });
    _schedule();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final count = _count;
    if (count == 0) return const SizedBox.shrink();
    final index = _index.clamp(0, count - 1);
    final intro = widget.intro;
    final cards = <Widget>[
      ?intro,
      for (final tip in widget.tips)
        _TipCard(key: ValueKey(tip.id), tip: tip, onAction: widget.onAction),
    ];
    final fade = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 260);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GestureDetector(
          // A sideways swipe moves one card; vertical drags stay the list's.
          onHorizontalDragEnd: count < 2
              ? null
              : (details) {
                  final v = details.primaryVelocity ?? 0;
                  if (v.abs() < 80) return;
                  _goTo(v < 0 ? index + 1 : index - 1 + count);
                },
          // Every card is laid out, only one shown: the hero keeps the
          // height of its tallest card, so the list below never jumps as
          // the cards turn.
          child: IntrinsicHeight(
            child: Stack(
              fit: StackFit.expand,
              children: [
                for (var i = 0; i < cards.length; i++)
                  IgnorePointer(
                    ignoring: i != index,
                    child: ExcludeSemantics(
                      excluding: i != index,
                      child: AnimatedOpacity(
                        opacity: i == index ? 1 : 0,
                        duration: fade,
                        child: cards[i],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        if (count > 1) _Dots(count: count, index: index, onSelect: _goTo),
      ],
    );
  }
}

/// The shared shell of every hero card: a wash of [tone] with its hairline.
class ForumHeroCard extends StatelessWidget {
  const ForumHeroCard({super.key, required this.tone, required this.child});

  final Color tone;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.32),
        borderRadius: BorderRadius.circular(AppSpacing.rMd),
        border: Border.all(color: tone.withValues(alpha: 0.50)),
      ),
      child: Padding(padding: const EdgeInsets.all(14), child: child),
    );
  }
}

/// The icon tile of a hero card, on the card surface so it stands off the
/// wash instead of sinking into it (tone on tone).
class ForumHeroTile extends StatelessWidget {
  const ForumHeroTile({
    super.key,
    required this.icon,
    required this.tone,
    this.emoji,
  });

  final IconData icon;
  final Color tone;
  final String? emoji;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: context.canopy.surface2,
        borderRadius: BorderRadius.circular(12),
      ),
      child: CanopyAccentTile(icon: icon, emoji: emoji, tone: tone, size: 44),
    );
  }
}

class _TipCard extends StatelessWidget {
  const _TipCard({super.key, required this.tip, required this.onAction});

  final ForumTip tip;
  final void Function(String routeName) onAction;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final onSurface = Theme.of(context).colorScheme.onSurface;
    final tone = tip.tone.colorOf(canopy);
    final route = tip.routeName;
    final label = tip.actionLabel;
    return ForumHeroCard(
      tone: tone,
      child: Row(
        // Centred: every hero card is as tall as the tallest one.
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          ForumHeroTile(icon: tip.icon, tone: tone),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'TIP',
                  style: AppTypography.label.copyWith(color: onSurface),
                ),
                const SizedBox(height: 2),
                Text(tip.title, style: forumItemTitle(context)),
                const SizedBox(height: 2),
                Text(
                  tip.body,
                  style: AppTypography.bodySm.copyWith(color: onSurface),
                ),
                if (route != null && label != null)
                  _TipAction(label: label, onTap: () => onAction(route)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A tip's one action: its words and an arrow, in a 48pt tap target.
class _TipAction extends StatelessWidget {
  const _TipAction({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final onSurface = Theme.of(context).colorScheme.onSurface;
    return Semantics(
      button: true,
      label: label,
      onTap: onTap,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.rSm),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48, minWidth: 48),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Flexible(
                child: Text(
                  label,
                  style: AppTypography.buttonSm.copyWith(color: onSurface),
                ),
              ),
              const SizedBox(width: 6),
              Icon(LucideIcons.arrowRight, size: 16, color: onSurface),
            ],
          ),
        ),
      ),
    );
  }
}

/// One dot per card: an 8pt dot in a 28x48pt tap target.
class _Dots extends StatelessWidget {
  const _Dots({
    required this.count,
    required this.index,
    required this.onSelect,
  });

  final int count;
  final int index;
  final void Function(int index) onSelect;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final active = Theme.of(context).colorScheme.primary;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < count; i++)
          Semantics(
            button: true,
            selected: i == index,
            label: 'Card ${i + 1} of $count',
            onTap: () => onSelect(i),
            excludeSemantics: true,
            child: InkResponse(
              onTap: () => onSelect(i),
              radius: 20,
              child: SizedBox(
                // Narrow enough for eight dots at 320pt, tall enough to tap.
                width: 28,
                height: 48,
                child: Center(
                  child: AnimatedContainer(
                    duration: MediaQuery.disableAnimationsOf(context)
                        ? Duration.zero
                        : const Duration(milliseconds: 200),
                    width: i == index ? 18 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: i == index ? active : canopy.line2,
                      borderRadius: BorderRadius.circular(AppSpacing.rPill),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
