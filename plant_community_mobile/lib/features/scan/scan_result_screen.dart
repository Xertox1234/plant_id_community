import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/routing/error_screen.dart';
import '../../models/plant.dart';
import '../results/results_screen.dart';
import 'capture_steps.dart';
import 'scan_job_api.dart';
import 'scan_job_tracker.dart';
import 'widgets/scan_job_pill.dart';

/// One scan job, fetched fresh by id (the tracker's copy is gone after a
/// restart or a push tap). No automatic retry: a failure shows the error
/// screen at once rather than spinning through Riverpod's backoff.
final scanJobProvider = FutureProvider.autoDispose.family<ScanJob, String>(
  (ref, id) => ref.watch(scanJobApiProvider).get(id),
  retry: (_, _) => null,
);

/// The result of a background scan, opened at `/scans/<id>`.
///
/// Once the job has loaded with a result it tells the tracker
/// ([ScanJobTracker.viewed]): that saves a result the tracker had not
/// applied yet and takes down the "ready" pill.
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
    // Try again needs the capture, which only the tracker holds: gone after
    // a kill, a dismiss or a retry.
    final canRetry = ref.watch(
      scanJobTrackerProvider.select(
        (s) =>
            s.phase == TrackerPhase.ready &&
            s.job?.id == jobId &&
            s.job?.status == ScanJobStatus.degraded &&
            s.lastCapture != null,
      ),
    );
    final job = ref.watch(scanJobProvider(jobId));
    return job.when(
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (error, _) => ErrorScreen(
        error: error is Exception ? error : Exception(error.toString()),
      ),
      data: (job) {
        final result = job.result;
        // `hasResult` and a null `result` can disagree on a bad payload.
        if (!job.status.hasResult || result == null) {
          return const _NoResult();
        }
        final degraded = job.status == ScanJobStatus.degraded;
        return ResultsScreen(
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
          degraded: degraded,
          onRetry: degraded && canRetry
              ? () => unawaited(_retry(context, ref))
              : null,
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
  const _NoResult();

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
                  "We couldn't check your plant",
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
