import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/routing/error_screen.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../models/plant.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import '../../shared/widgets/clay_button.dart';
import '../profile/forum_notification_settings_card.dart' show apiErrorMessage;
import '../results/results_screen.dart';
import 'capture_steps.dart';
import 'scan_decisions.dart';
import 'scan_job_api.dart';
import 'scan_job_tracker.dart';
import 'widgets/scan_job_pill.dart';
import 'widgets/short_scan_card.dart';

/// One scan job, fetched fresh by id (the tracker's copy is gone after a
/// restart or a push tap). No automatic retry: a failure shows the error
/// screen at once rather than spinning through Riverpod's backoff.
final scanJobProvider = FutureProvider.autoDispose.family<ScanJob, String>(
  (ref, id) => ref.watch(scanJobApiProvider).get(id),
  retry: (_, _) => null,
);

/// A scan the server no longer has, or one past its decide-by time.
bool _isGone(ScanJob job) => switch (job.decision) {
  ScanDecision.dismissed ||
  ScanDecision.expired ||
  ScanDecision.removed => true,
  ScanDecision.undecided =>
    job.decideBy != null && job.decideBy!.isBefore(DateTime.now()),
  ScanDecision.kept => false,
};

bool _isNotFound(Object error) =>
    error is ApiException && error.statusCode == 404;

/// The load error as a screen: "This scan was deleted" for a 404, else the
/// generic error screen.
Widget _errorScreen(Object error) => _isNotFound(error)
    ? const _NoResult(title: _deletedTitle)
    : ErrorScreen(
        error: error is Exception ? error : Exception(error.toString()),
      );

const _deletedTitle = 'This scan was deleted';

/// Try again needs the capture, which only the tracker holds: gone after a
/// kill, a dismiss or a retry.
bool _watchCanRetry(WidgetRef ref, String jobId) => ref.watch(
  scanJobTrackerProvider.select(
    (s) =>
        s.phase == TrackerPhase.ready &&
        s.job?.id == jobId &&
        s.job?.status == ScanJobStatus.degraded &&
        s.lastCapture != null,
  ),
);

/// The full result of [job] (which has a [result]), with [decisionBar].
Widget _fullResult(
  ScanJob job,
  ScanJobResult result, {
  required Widget decisionBar,
  VoidCallback? onRetry,
}) => ResultsScreen(
  plant: Plant(
    id: job.id,
    name: result.plantName,
    scientificName: result.scientificName,
    description: result.description,
    care: const [],
    imageUrl: job.coverPhoto,
    timestamp: job.createdAt.toLocal(),
  ),
  diagnosis: result.diagnosis,
  confidence: result.confidence,
  degraded: job.status == ScanJobStatus.degraded,
  onRetry: onRetry,
  decisionBar: decisionBar,
);

/// A background scan, opened at `/scans/<id>` (the pill and the "scan ready"
/// push land here).
///
/// An undecided scan shows the [ShortScanCard]; View opens the full result
/// at `/scans/<id>/full`, the one place it can be added to My Collection. A
/// kept scan shows the full result marked "In My Collection". Once the job
/// has loaded with a result it tells the tracker ([ScanJobTracker.viewed]),
/// which takes down the "ready" pill.
class ScanResultScreen extends ConsumerWidget {
  const ScanResultScreen({super.key, required this.jobId});

  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<AsyncValue<ScanJob>>(scanJobProvider(jobId), (_, next) {
      final job = next.asData?.value;
      if (job == null || !job.status.hasResult || job.result == null) return;
      unawaited(
        ref.read(scanJobTrackerProvider.notifier).viewed(jobId, job: job),
      );
    });
    final canRetry = _watchCanRetry(ref, jobId);
    final job = ref.watch(scanJobProvider(jobId));
    return job.when(
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (error, _) => _errorScreen(error),
      data: (job) {
        final result = job.result;
        // `hasResult` and a null `result` can disagree on a bad payload.
        if (!job.status.hasResult || result == null) {
          return const _NoResult();
        }
        if (_isGone(job)) return const _NoResult(title: _deletedTitle);
        final degraded = job.status == ScanJobStatus.degraded;
        final onRetry = degraded && canRetry
            ? () => unawaited(_retry(context, ref))
            : null;
        if (job.decision == ScanDecision.undecided) {
          return _ShortCardPage(job: job, onTryAgain: onRetry);
        }
        return _fullResult(
          job,
          result,
          decisionBar: ScanDecisionBar(job: job),
          onRetry: onRetry,
        );
      },
    );
  }

  /// Re-runs the check, then goes back at once so the user sees the pill
  /// upload it. Not awaited before leaving: the retry awaits the upload.
  static Future<void> _retry(BuildContext context, WidgetRef ref) async {
    final tracker = ref.read(scanJobTrackerProvider.notifier);
    final mode = ref.read(scanJobTrackerProvider).lastCapture?.mode;
    final messenger = ScaffoldMessenger.maybeOf(context);
    final retrying = tracker.retry();
    _closeResult(context);
    try {
      await retrying;
    } on ScanRefused catch (e) {
      final message = scanRefusalMessage(e, mode: mode ?? ScanMode.diagnose);
      if (message != null) {
        messenger?.showSnackBar(SnackBar(content: Text(message)));
      }
    } catch (e) {
      debugPrint('[SCAN_JOB] Retry from the result failed: $e');
      messenger?.showSnackBar(
        const SnackBar(content: Text("Couldn't start the check. Try again.")),
      );
    }
  }
}

/// Leaves the result: back where it was opened from, else home.
void _closeResult(BuildContext context) {
  final router = GoRouter.maybeOf(context);
  if (router == null) {
    Navigator.of(context).maybePop();
  } else if (router.canPop()) {
    router.pop();
  } else {
    router.go(AppRoutes.home);
  }
}

class _NoResult extends StatelessWidget {
  const _NoResult({this.title = "We couldn't check your plant"});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpacing.lg),
                FilledButton(
                  onPressed: () => _closeResult(context),
                  child: const Text('Close'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// `/scans/<id>` for an undecided scan: the short card on its own.
class _ShortCardPage extends ConsumerWidget {
  const _ShortCardPage({required this.job, this.onTryAgain});

  final ScanJob job;
  final VoidCallback? onTryAgain;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ext = context.canopy;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Your scan'),
        centerTitle: true,
        leading: CloseButton(onPressed: () => _closeResult(context)),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(ext.padScreen),
          child: ShortScanCard(
            job: job,
            onTryAgain: onTryAgain,
            onView: () =>
                GoRouter.maybeOf(context)?.push(scanFullResultPath(job.id)),
            onDismiss: () => _dismiss(context, ref),
          ),
        ),
      ),
    );
  }

  Future<void> _dismiss(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.maybeOf(context);
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await ref.read(scanDecisionsProvider).dismiss(job.id);
    } catch (e) {
      debugPrint('[SCAN_JOB] Dismiss failed: ${e.runtimeType}');
      messenger?.showSnackBar(
        SnackBar(content: Text(apiErrorMessage(e) ?? _dismissFailed)),
      );
      return;
    }
    _clearTrackedPill(container, job.id);
    if (context.mounted) _closeResult(context);
  }
}

const _dismissFailed = "Couldn't dismiss the scan. Try again.";

/// After a server dismiss: drops the tracker's pill when it is showing this
/// scan, so it stops offering View and Try again for an erased scan (its
/// `retry_of` would be ignored and the retry charged as a new scan). The
/// tracker's dismiss is local-only.
void _clearTrackedPill(ProviderContainer container, String jobId) {
  if (container.read(scanJobTrackerProvider).job?.id != jobId) return;
  container.read(scanJobTrackerProvider.notifier).dismiss();
}

/// `/scans/<id>/full`: the whole result, with Add to My Collection and
/// Dismiss while the scan is undecided, or "In My Collection" once kept.
class ScanFullResultScreen extends ConsumerWidget {
  const ScanFullResultScreen({super.key, required this.jobId});

  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // No Try again here: it lives on the short card, so a retry never
    // leaves this screen stacked over the scan it replaces.
    return ref
        .watch(scanJobProvider(jobId))
        .when(
          loading: () =>
              const Scaffold(body: Center(child: CircularProgressIndicator())),
          error: (error, _) => _errorScreen(error),
          data: (job) {
            final result = job.result;
            if (!job.status.hasResult || result == null) {
              return const _NoResult();
            }
            if (_isGone(job)) return const _NoResult(title: _deletedTitle);
            return _fullResult(
              job,
              result,
              decisionBar: ScanDecisionBar(job: job),
            );
          },
        );
  }
}

/// Under a full result: Add to My Collection and Dismiss for an undecided
/// scan, "In My Collection" for a kept one, and Add alone for a kept scan
/// missing from the user's plants.
///
/// While Add runs both buttons are off and Add shows progress; the app bar's
/// back still works (the Firestore write can stay pending offline after the
/// server has kept the scan). A failure shows a SnackBar and turns them back
/// on.
class ScanDecisionBar extends ConsumerStatefulWidget {
  const ScanDecisionBar({super.key, required this.job});

  final ScanJob job;

  static const addKey = Key('scan-decision-add');
  static const dismissKey = Key('scan-decision-dismiss');
  static const keptKey = Key('scan-decision-kept');

  @override
  ConsumerState<ScanDecisionBar> createState() => _ScanDecisionBarState();
}

enum _Busy { none, adding, dismissing }

class _ScanDecisionBarState extends ConsumerState<ScanDecisionBar> {
  bool _kept = false;
  _Busy _busy = _Busy.none;

  Future<void> _add() async {
    final decisions = ref.read(scanDecisionsProvider);
    final container = ProviderScope.containerOf(context, listen: false);
    final messenger = ScaffoldMessenger.maybeOf(context);
    setState(() => _busy = _Busy.adding);
    try {
      await decisions.keep(widget.job);
      // The short card under this screen must not keep counting down.
      container.invalidate(scanJobProvider(widget.job.id));
      if (!mounted) return;
      unawaited(HapticFeedback.lightImpact());
      setState(() => _kept = true);
    } catch (e) {
      debugPrint('[SCAN_JOB] Keep failed: ${e.runtimeType}');
      messenger?.showSnackBar(
        SnackBar(
          content: Text(
            apiErrorMessage(e) ??
                "Couldn't add it to My Collection. Try again.",
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = _Busy.none);
    }
  }

  Future<void> _dismiss() async {
    final decisions = ref.read(scanDecisionsProvider);
    final router = GoRouter.maybeOf(context);
    final messenger = ScaffoldMessenger.maybeOf(context);
    final container = ProviderScope.containerOf(context, listen: false);
    setState(() => _busy = _Busy.dismissing);
    try {
      await decisions.dismiss(widget.job.id);
    } catch (e) {
      debugPrint('[SCAN_JOB] Dismiss failed: ${e.runtimeType}');
      messenger?.showSnackBar(
        SnackBar(content: Text(apiErrorMessage(e) ?? _dismissFailed)),
      );
      if (mounted) setState(() => _busy = _Busy.none);
      return;
    }
    _clearTrackedPill(container, widget.job.id);
    // A tab root: `go`, never `push` (docs/rules/flutter.md).
    router?.go(AppRoutes.collection);
  }

  /// Whether a scan the server has kept is also a saved plant. Only a
  /// collection that has loaded and lacks it says no, so Add never flashes
  /// while the plants stream loads or after it fails.
  bool _inCollection() {
    final uid = ref.watch(currentUserIdProvider);
    if (uid == null) return true;
    final plants = ref.watch(plantsStreamProvider(uid)).value?.plants;
    return plants == null || plants.any((p) => p.id == widget.job.id);
  }

  @override
  Widget build(BuildContext context) {
    final ext = context.canopy;
    final theme = Theme.of(context);
    final serverKept = widget.job.decision == ScanDecision.kept;
    // Kept on the server but missing from Firestore (the write never
    // landed): offer Add again. Keep is a no-op on the server for a kept
    // scan, then writes the same plant doc.
    final readd = serverKept && !_kept && !_inCollection();
    if (!readd && (_kept || serverKept)) {
      return Semantics(
        container: true,
        child: ConstrainedBox(
          key: ScanDecisionBar.keptKey,
          constraints: const BoxConstraints(minHeight: 48),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(LucideIcons.circleCheck, color: ext.statusOk, size: 20),
              const SizedBox(width: AppSpacing.sm),
              Flexible(
                child: Text(
                  'In My Collection',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }
    final idle = _busy == _Busy.none;
    // Stacked full-width: "Add to My Collection" must not ellipsise at a
    // large text scale on a narrow phone.
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: ClayButton(
            key: ScanDecisionBar.addKey,
            label: 'Add to My Collection',
            fullWidth: true,
            loading: _busy == _Busy.adding,
            onPressed: idle ? _add : null,
          ),
        ),
        if (!readd) ...[
          const SizedBox(height: AppSpacing.sm),
          ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: ClayButton(
              key: ScanDecisionBar.dismissKey,
              label: 'Dismiss',
              fullWidth: true,
              variant: ClayButtonVariant.outline,
              loading: _busy == _Busy.dismissing,
              onPressed: idle ? _dismiss : null,
            ),
          ),
        ],
      ],
    );
  }
}
