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
  });

  final Widget child;
  final VoidCallback onDone;
  final bool slide;

  @override
  State<LiveFlash> createState() => _LiveFlashState();
}

class _LiveFlashState extends State<LiveFlash> with TickerProviderStateMixin {
  late final AnimationController _fade = AnimationController(
    vsync: this,
    duration: liveFlashDuration,
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
    if (_size.value < 1) _size.forward();
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
