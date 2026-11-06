import 'dart:math' as math;
import 'dart:ui' show PathMetric;

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../shared/widgets/api_image.dart';
import '../../../shared/widgets/clay_button.dart';
import '../capture_steps.dart';
import '../scan_job_api.dart';

/// "Deletes in 18 h", or "Deletes in 42 min" under an hour (never below
/// 1 min), from [decideBy] as seen at [now].
String scanCountdownLabel(DateTime decideBy, DateTime now) {
  final left = decideBy.difference(now);
  if (left.inHours >= 1) return 'Deletes in ${left.inHours} h';
  return 'Deletes in ${math.max(1, left.inMinutes)} min';
}

/// The one-line verdict of a finished scan: the problem's name, "Looks
/// healthy", or why there is no verdict.
String scanDiagnosisLine(ScanJob job) {
  final d = job.result?.diagnosis;
  if (job.status == ScanJobStatus.degraded) return "Health check didn't run";
  if (job.mode == ScanMode.identify || d == null) return 'Identified only';
  final name = d.name?.trim();
  if (d.state == 'found' && name != null && name.isNotEmpty) return name;
  if (d.state == 'healthy') return 'Looks healthy';
  // `unavailable`, or a state a newer server adds: no health claim.
  return "Health check didn't run";
}

/// A finished scan still waiting for the user's decision: photo, name,
/// confidence, a one-line diagnosis and the time left, with View and
/// Dismiss. No description: View opens the full result for that.
///
/// The dashed warning-coloured edge marks it as not yet in the collection.
class ShortScanCard extends StatefulWidget {
  const ShortScanCard({
    super.key,
    required this.job,
    required this.onView,
    required this.onDismiss,
    this.onTryAgain,
    this.now,
  });

  final ScanJob job;
  final VoidCallback onView;

  /// Awaited: the buttons stay off until it settles. Errors are the
  /// caller's to report.
  final Future<void> Function() onDismiss;

  /// Shown as "Try again" when given (a half-result that can be re-run).
  final VoidCallback? onTryAgain;

  /// The clock for the countdown; defaults to [DateTime.now].
  final DateTime Function()? now;

  static const viewKey = Key('short-scan-view');
  static const dismissKey = Key('short-scan-dismiss');
  static const tryAgainKey = Key('short-scan-try-again');

  @override
  State<ShortScanCard> createState() => _ShortScanCardState();
}

class _ShortScanCardState extends State<ShortScanCard> {
  bool _dismissing = false;

  Future<void> _dismiss() async {
    setState(() => _dismissing = true);
    try {
      await widget.onDismiss();
    } catch (_) {
      // The caller reports it; this only re-enables the buttons.
    } finally {
      if (mounted) setState(() => _dismissing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ext = context.canopy;
    final job = widget.job;
    final result = job.result;
    final confidence = result?.confidence;
    final decideBy = job.decideBy;
    final now = (widget.now ?? DateTime.now)();
    final cover = job.coverPhoto;

    final photo = ClipRRect(
      borderRadius: BorderRadius.circular(AppSpacing.rSm),
      child: SizedBox.square(
        dimension: 88,
        child: cover != null && cover.startsWith('http')
            ? ApiImage(
                url: cover,
                placeholder: (context, _) =>
                    ColoredBox(color: theme.colorScheme.surfaceContainerLow),
                errorWidget: (context, _, _) => _PhotoPlaceholder(ext: ext),
              )
            : _PhotoPlaceholder(ext: ext),
      ),
    );

    final details = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Expanded(
              child: Text(
                result?.plantName ?? '',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (confidence != null) ...[
              const SizedBox(width: AppSpacing.sm),
              Text(
                '${(confidence * 100).round()}%',
                style: AppTypography.mono.copyWith(color: ext.ink2),
              ),
            ],
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        Row(
          children: [
            Icon(LucideIcons.stethoscope, size: 14, color: ext.ink2),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: Text(
                scanDiagnosisLine(job),
                style: theme.textTheme.bodyMedium?.copyWith(color: ext.ink2),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        if (decideBy != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            scanCountdownLabel(decideBy, now),
            style: theme.textTheme.labelLarge?.copyWith(
              color: ext.statusWarn,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ],
    );

    final tryAgain = widget.onTryAgain;
    final buttons = Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: [
        _MinTap(
          child: ClayButton(
            key: ShortScanCard.viewKey,
            label: 'View',
            size: ClayButtonSize.medium,
            onPressed: _dismissing ? null : widget.onView,
          ),
        ),
        if (tryAgain != null)
          _MinTap(
            child: ClayButton(
              key: ShortScanCard.tryAgainKey,
              label: 'Try again',
              size: ClayButtonSize.medium,
              variant: ClayButtonVariant.secondary,
              onPressed: _dismissing ? null : tryAgain,
            ),
          ),
        _MinTap(
          child: ClayButton(
            key: ShortScanCard.dismissKey,
            label: 'Dismiss',
            size: ClayButtonSize.medium,
            variant: ClayButtonVariant.outline,
            loading: _dismissing,
            onPressed: _dismiss,
          ),
        ),
      ],
    );

    return CustomPaint(
      foregroundPainter: _DashedBorderPainter(
        color: ext.statusWarn,
        radius: AppSpacing.rMd,
      ),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: ext.surface2,
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  photo,
                  const SizedBox(width: AppSpacing.md),
                  Expanded(child: details),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              buttons,
            ],
          ),
        ),
      ),
    );
  }
}

/// Holds a button at the 48dp tap-target minimum without fixing its height.
class _MinTap extends StatelessWidget {
  const _MinTap({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => ConstrainedBox(
    constraints: const BoxConstraints(minHeight: 48, minWidth: 64),
    child: child,
  );
}

class _PhotoPlaceholder extends StatelessWidget {
  const _PhotoPlaceholder({required this.ext});
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: ext.surface3,
    child: Center(child: Icon(LucideIcons.leaf, color: ext.ink3)),
  );
}

/// A 2px dashed rounded-rectangle edge (Flutter has no dashed border).
class _DashedBorderPainter extends CustomPainter {
  const _DashedBorderPainter({required this.color, required this.radius});

  final Color color;
  final double radius;
  static const _dash = 6.0, _gap = 4.0, _stroke = 2.0;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = (Offset.zero & size).deflate(_stroke / 2);
    final path = Path()
      ..addRRect(RRect.fromRectAndRadius(rect, Radius.circular(radius)));
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = _stroke;
    for (final PathMetric metric in path.computeMetrics()) {
      for (var d = 0.0; d < metric.length; d += _dash + _gap) {
        canvas.drawPath(metric.extractPath(d, d + _dash), paint);
      }
    }
  }

  @override
  bool shouldRepaint(_DashedBorderPainter old) =>
      old.color != color || old.radius != radius;
}
