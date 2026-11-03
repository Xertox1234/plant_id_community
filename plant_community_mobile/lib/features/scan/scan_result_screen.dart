import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/routing/error_screen.dart';
import '../../models/plant.dart';
import '../results/results_screen.dart';
import 'scan_job_api.dart';

/// One scan job, fetched fresh by id (the tracker's copy is gone after a
/// restart or a push tap). No automatic retry: a failure shows the error
/// screen at once rather than spinning through Riverpod's backoff.
final scanJobProvider = FutureProvider.autoDispose.family<ScanJob, String>(
  (ref, id) => ref.watch(scanJobApiProvider).get(id),
  retry: (_, _) => null,
);

/// The result of a background scan, opened at `/scans/<id>`.
class ScanResultScreen extends ConsumerWidget {
  const ScanResultScreen({super.key, required this.jobId});

  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
          degraded: job.status == ScanJobStatus.degraded,
        );
      },
    );
  }
}

class _NoResult extends StatelessWidget {
  const _NoResult();

  void _close(BuildContext context) {
    final router = GoRouter.maybeOf(context);
    if (router == null) {
      Navigator.of(context).maybePop();
    } else if (router.canPop()) {
      router.pop();
    } else {
      router.go(AppRoutes.home);
    }
  }

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
                  onPressed: () => _close(context),
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
