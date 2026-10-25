import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/green_thumb_extension.dart';

/// The rounded viewfinder drawn over the camera preview.
///
/// Neutral while the frame is being judged; when [locked] it turns Canopy
/// primary green and snaps in (a ~180 ms scale from slightly large). With
/// reduce motion on, the snap jumps straight to its end state. The haptic for
/// the lock is the screen's job, so this widget stays pure.
class ViewfinderFrame extends StatefulWidget {
  const ViewfinderFrame({super.key, required this.locked});

  final bool locked;

  static const Duration snapDuration = Duration(milliseconds: 180);

  @override
  State<ViewfinderFrame> createState() => _ViewfinderFrameState();
}

class _ViewfinderFrameState extends State<ViewfinderFrame>
    with SingleTickerProviderStateMixin {
  late final AnimationController _snap = AnimationController(
    vsync: this,
    duration: ViewfinderFrame.snapDuration,
    value: 1,
  );
  late final Animation<double> _scale = Tween<double>(
    begin: 1.06,
    end: 1,
  ).animate(CurvedAnimation(parent: _snap, curve: Easing.emphasizedDecelerate));

  @override
  void didUpdateWidget(ViewfinderFrame oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.locked && !oldWidget.locked) {
      if (MediaQuery.disableAnimationsOf(context)) {
        _snap.value = 1;
      } else {
        _snap.forward(from: 0);
      }
    }
  }

  @override
  void dispose() {
    _snap.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = widget.locked
        ? Theme.of(context).colorScheme.primary
        : context.canopy.line.withValues(alpha: 0.6);
    return RepaintBoundary(
      child: ScaleTransition(
        scale: _scale,
        child: CustomPaint(
          painter: _FramePainter(color: color, locked: widget.locked),
          child: const SizedBox.expand(),
        ),
      ),
    );
  }
}

class _FramePainter extends CustomPainter {
  _FramePainter({required this.color, required this.locked});

  final Color color;
  final bool locked;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final rect = Offset.zero & size;
    final radius = Radius.circular(
      AppSpacing.rLg.clamp(0, size.shortestSide / 2),
    );
    final rrect = RRect.fromRectAndRadius(rect.deflate(1.5), radius);
    canvas.drawRRect(
      rrect,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = locked ? 3 : 2
        ..color = color,
    );

    // Heavier corner brackets give the frame its "reticle" read.
    final arm = (size.shortestSide * 0.16).clamp(12.0, 40.0);
    final r = radius.x;
    final bracket = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = locked ? 5 : 4
      ..strokeCap = StrokeCap.round
      ..color = color;
    final l = rrect.left, t = rrect.top, rt = rrect.right, b = rrect.bottom;
    final corners = <Path>[
      Path()
        ..moveTo(l, t + r + arm)
        ..lineTo(l, t + r)
        ..arcToPoint(Offset(l + r, t), radius: radius)
        ..lineTo(l + r + arm, t),
      Path()
        ..moveTo(rt - r - arm, t)
        ..lineTo(rt - r, t)
        ..arcToPoint(Offset(rt, t + r), radius: radius)
        ..lineTo(rt, t + r + arm),
      Path()
        ..moveTo(rt, b - r - arm)
        ..lineTo(rt, b - r)
        ..arcToPoint(Offset(rt - r, b), radius: radius)
        ..lineTo(rt - r - arm, b),
      Path()
        ..moveTo(l + r + arm, b)
        ..lineTo(l + r, b)
        ..arcToPoint(Offset(l, b - r), radius: radius)
        ..lineTo(l, b - r - arm),
    ];
    for (final p in corners) {
      canvas.drawPath(p, bracket);
    }
  }

  @override
  bool shouldRepaint(_FramePainter old) =>
      old.color != color || old.locked != locked;
}
