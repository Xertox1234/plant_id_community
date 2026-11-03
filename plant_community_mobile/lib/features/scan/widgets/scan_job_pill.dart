import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/routing/app_router.dart';
import '../../../core/routing/main_shell.dart';
import '../../../core/theme/app_typography.dart';
import '../../../shared/widgets/canopy_surfaces.dart';
import '../capture_steps.dart';
import '../scan_job_api.dart';
import '../scan_job_tracker.dart';

/// The SnackBar copy for a scan the server (or the allowance pre-check)
/// declined, or null when nothing should be shown (`scan_in_progress`: the
/// caller shows the running job instead).
///
/// The limits come from [allowance]; without one the copy is generic.
String? scanRefusalMessage(
  ScanRefused e, {
  required ScanMode mode,
  ScanAllowance? allowance,
}) {
  switch (e.code) {
    case 'allowance_exhausted':
      final kind = e.kind ?? mode.name;
      if (kind == ScanMode.identify.name) return 'No identifies left today';
      if (allowance == null) return 'No checks left today';
      return allowance.isPremium
          ? "You've used today's ${allowance.diagnoseLimit} checks. "
                'More at midnight.'
          : 'No checks left today · Go premium for '
                '${allowance.premiumDiagnoseLimit}';
    case 'plant_id_busy':
      return 'Plant checks are busy right now, try again later';
    case 'scan_in_progress':
      return null;
    default:
      return "Couldn't start the check. Try again.";
  }
}

/// App-wide progress of the background scan job, floating above the nav bar.
///
/// Placed by `MaterialApp.router(builder:)` in main.dart, ABOVE the router's
/// navigator: so it has no route of its own, no Overlay (no tooltips here)
/// and reads the current path from [appRouterProvider]. It hides on
/// `/camera`, where the scan screen's status view shows the same content.
class ScanJobPill extends ConsumerWidget {
  const ScanJobPill({super.key});

  static const uploadingCopy = 'Uploading…';
  static const waitingCopy = 'Checking your plant…';
  static const slowCopy = 'This scan is taking a little longer than usual.';
  static const readyCopy = 'Your plant check is ready';
  static const failedCopy = "We couldn't check your plant";

  static const waitKey = Key('scan-pill-wait');
  static const cancelKey = Key('scan-pill-cancel');
  static const viewKey = Key('scan-pill-view');
  static const retryKey = Key('scan-pill-retry');
  static const dismissKey = Key('scan-pill-dismiss');
  static const progressKey = Key('scan-pill-progress');

  /// Distance from the screen's bottom edge: the safe area, the nav bar,
  /// and the shell's Identify FAB with its margin, so the pill covers none
  /// of them.
  static double bottomOffset(BuildContext context) =>
      MediaQuery.paddingOf(context).bottom +
      (NavigationBarTheme.of(context).height ?? 80) +
      MainShell.fabClearance;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = _routerOrNull(ref);
    if (router == null) return const ScanJobStatusCard();
    final delegate = router.routerDelegate;
    return ListenableBuilder(
      listenable: delegate,
      builder: (context, _) {
        if (_topPath(delegate) == AppRoutes.camera) {
          return const SizedBox.shrink();
        }
        return const ScanJobStatusCard();
      },
    );
  }

  /// The path of the TOP route. `currentConfiguration.uri` is not it: a
  /// `push` (how the shell opens `/camera`) leaves the list's uri at the
  /// page underneath. Empty before the first route is parsed.
  static String? _topPath(GoRouterDelegate delegate) =>
      delegate.currentConfiguration.isEmpty ? null : delegate.state.uri.path;

  /// The router, or null where none can be built (a test that pumps the
  /// pill without one): the pill then never hides.
  static GoRouter? _routerOrNull(WidgetRef ref) {
    try {
      return ref.watch(appRouterProvider);
    } catch (_) {
      return null;
    }
  }
}

/// The job's state as a card: the pill's body, and the scan screen's status
/// view. Idle renders nothing.
///
/// [onView] replaces the default "View" action (push `/scans/<id>`, then
/// dismiss); the status view uses it to replace the camera instead.
class ScanJobStatusCard extends ConsumerStatefulWidget {
  const ScanJobStatusCard({super.key, this.onView});

  final void Function(ScanJob job)? onView;

  @override
  ConsumerState<ScanJobStatusCard> createState() => _ScanJobStatusCardState();
}

class _ScanJobStatusCardState extends ConsumerState<ScanJobStatusCard> {
  /// "Wait" was tapped on the slow copy. Reset on a PHASE change only: a
  /// poll emits a fresh state every tick while the job stays slow.
  bool _waited = false;

  ScanJobTracker get _tracker => ref.read(scanJobTrackerProvider.notifier);

  void _view(ScanJob job) {
    final onView = widget.onView;
    if (onView != null) {
      onView(job);
      return;
    }
    unawaited(ref.read(appRouterProvider).push('/scans/${job.id}'));
    _tracker.dismiss();
  }

  Future<void> _cancel() async {
    try {
      await _tracker.cancel();
    } catch (_) {
      _snack("Couldn't cancel the check. Try again.");
    }
  }

  Future<void> _retry() async {
    final capture = ref.read(scanJobTrackerProvider).lastCapture;
    try {
      await _tracker.retry();
    } on ScanRefused catch (e) {
      final message = scanRefusalMessage(
        e,
        mode: capture?.mode ?? ScanMode.diagnose,
        allowance: ref.read(scanAllowanceProvider).value,
      );
      if (message != null) _snack(message);
    } catch (_) {
      _snack("Couldn't start the check. Try again.");
    }
  }

  void _snack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.maybeOf(
      context,
    )?.showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(
      scanJobTrackerProvider.select((s) => s.phase),
      (_, _) => setState(() => _waited = false),
    );
    final state = ref.watch(scanJobTrackerProvider);
    final job = state.job;
    final phase = state.phase == TrackerPhase.slow && _waited
        ? TrackerPhase.waiting
        : state.phase;
    return switch (phase) {
      TrackerPhase.idle => const SizedBox.shrink(),
      TrackerPhase.uploading => _card(
        icon: LucideIcons.upload,
        copy: ScanJobPill.uploadingCopy,
        below: LinearProgressIndicator(
          key: ScanJobPill.progressKey,
          value: state.uploadProgress,
        ),
      ),
      TrackerPhase.waiting => _card(
        icon: LucideIcons.leaf,
        copy: ScanJobPill.waitingCopy,
        below: const LinearProgressIndicator(),
      ),
      TrackerPhase.slow => _card(
        icon: LucideIcons.hourglass,
        copy: ScanJobPill.slowCopy,
        actions: [
          _action(
            key: ScanJobPill.waitKey,
            label: 'Wait',
            onPressed: () => setState(() => _waited = true),
          ),
          _action(
            key: ScanJobPill.cancelKey,
            label: 'Cancel',
            onPressed: _cancel,
          ),
        ],
      ),
      TrackerPhase.ready => _card(
        icon: LucideIcons.circleCheck,
        copy: ScanJobPill.readyCopy,
        actions: [
          if (job != null)
            _action(
              key: ScanJobPill.viewKey,
              label: 'View',
              filled: true,
              onPressed: () => _view(job),
            ),
        ],
      ),
      TrackerPhase.failed => _card(
        icon: LucideIcons.circleAlert,
        copy: ScanJobPill.failedCopy,
        dismissible: true,
        actions: [
          // A failed job restored after a kill has no capture to resend.
          if (state.lastCapture != null)
            _action(
              key: ScanJobPill.retryKey,
              label: 'Try again',
              filled: true,
              onPressed: _retry,
            ),
        ],
      ),
    };
  }

  Widget _action({
    required Key key,
    required String label,
    required VoidCallback onPressed,
    bool filled = false,
  }) {
    // 48dp: Material's 40dp default misses the tap-target guideline.
    final style = ButtonStyle(
      minimumSize: const WidgetStatePropertyAll(Size(64, 48)),
      textStyle: const WidgetStatePropertyAll(AppTypography.button),
    );
    final text = Text(label, textAlign: TextAlign.center);
    return filled
        ? FilledButton(
            key: key,
            style: style,
            onPressed: onPressed,
            child: text,
          )
        : TextButton(key: key, style: style, onPressed: onPressed, child: text);
  }

  Widget _card({
    required IconData icon,
    required String copy,
    Widget? below,
    List<Widget> actions = const [],
    bool dismissible = false,
  }) {
    final cs = Theme.of(context).colorScheme;
    return CanopyCard(
      elevation: 2,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.sm,
        AppSpacing.sm,
        AppSpacing.sm,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(icon, size: AppSpacing.iconMD, color: cs.primary),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                  child: Semantics(
                    liveRegion: true,
                    child: Text(
                      copy,
                      style: AppTypography.body.copyWith(color: cs.onSurface),
                    ),
                  ),
                ),
              ),
              if (dismissible)
                IconButton(
                  key: ScanJobPill.dismissKey,
                  onPressed: _tracker.dismiss,
                  icon: Icon(
                    LucideIcons.x,
                    semanticLabel: 'Dismiss',
                    color: cs.onSurface,
                  ),
                ),
            ],
          ),
          if (below != null)
            Padding(
              padding: const EdgeInsets.only(
                right: AppSpacing.sm,
                bottom: AppSpacing.sm,
              ),
              child: below,
            ),
          if (actions.isNotEmpty)
            Wrap(
              alignment: WrapAlignment.end,
              spacing: AppSpacing.sm,
              children: actions,
            ),
        ],
      ),
    );
  }
}
