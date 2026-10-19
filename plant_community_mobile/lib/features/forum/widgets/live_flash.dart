import 'package:flutter/material.dart';

/// How long a live reply stays highlighted (the web's `canopy-flash`).
const liveFlashDuration = Duration(milliseconds: 2500);

/// How long a reply inserted live takes to slide open.
const liveSlideDuration = Duration(milliseconds: 250);

/// Highlights a reply that arrived live, or that the "N new replies" pill
/// revealed: a `secondaryContainer` wash over the card that fades over
/// [liveFlashDuration], then [onDone]. With [slide] the card also opens from
/// zero height.
///
/// With the OS reduce-motion setting on there is no slide and no fade: the
/// wash shows at full strength for the same time, then goes.
class LiveFlash extends StatefulWidget {
  const LiveFlash({
    super.key,
    required this.child,
    required this.onDone,
    this.slide = true,
    this.onSlideDone,
  });

  final Widget child;
  final VoidCallback onDone;
  final bool slide;

  /// Once the card has its full height: after the slide, or on the first
  /// frame when there is none. The thread follows a live insert to the
  /// bottom until then, since a growing card moves the end of the list.
  final VoidCallback? onSlideDone;

  @override
  State<LiveFlash> createState() => _LiveFlashState();
}

class _LiveFlashState extends State<LiveFlash> with TickerProviderStateMixin {
  // `preserve`: with the OS reduce-motion setting a `normal` controller runs
  // at 5% of its duration, and the highlight would last 125 ms.
  late final AnimationController _fade = AnimationController(
    vsync: this,
    duration: liveFlashDuration,
    animationBehavior: AnimationBehavior.preserve,
  );
  late final AnimationController _size = AnimationController(
    vsync: this,
    duration: liveSlideDuration,
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    _size.value = widget.slide && !reduceMotion ? 0 : 1;
    if (_size.value < 1) {
      _size.forward().whenComplete(() {
        if (mounted) widget.onSlideDone?.call();
      });
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) widget.onSlideDone?.call();
      });
    }
    _fade.forward().whenComplete(() {
      if (mounted) widget.onDone();
    });
  }

  @override
  void dispose() {
    _fade.dispose();
    _size.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    final wash = Theme.of(context).colorScheme.secondaryContainer;
    final flashed = AnimatedBuilder(
      animation: _fade,
      builder: (context, child) => Container(
        foregroundDecoration: BoxDecoration(
          color: wash.withValues(
            alpha: 0.45 * (reduceMotion ? 1 : 1 - _fade.value),
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: child,
      ),
      child: widget.child,
    );
    if (reduceMotion || !widget.slide) return flashed;
    return SizeTransition(sizeFactor: _size, axisAlignment: -1, child: flashed);
  }
}
