import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'capture_steps.dart';
import 'scan_job_api.dart';
import 'scan_job_tracker.dart';
import 'widgets/scan_job_pill.dart';

/// The short-card actions shared by `/scans/<id>` and My Plants, so both
/// offer Try again and clear the pill by the same rules.

/// Try again needs the capture, which only the tracker holds: gone after a
/// kill, a dismiss or a retry. True when the tracker is `ready` with
/// [jobId], that job is degraded, and its capture is still held.
bool canRetryTrackedScan(ScanTrackerState s, String jobId) =>
    s.phase == TrackerPhase.ready &&
    s.job?.id == jobId &&
    s.job?.status == ScanJobStatus.degraded &&
    s.lastCapture != null;

/// [canRetryTrackedScan], watched.
bool watchCanRetryScan(WidgetRef ref, String jobId) => ref.watch(
  scanJobTrackerProvider.select((s) => canRetryTrackedScan(s, jobId)),
);

/// After a server dismiss: drops the tracker's pill when it is showing this
/// scan, so it stops offering View and Try again for an erased scan (its
/// `retry_of` would be ignored and the retry charged as a new scan). The
/// tracker's dismiss is local-only.
void clearTrackedScanPill(ProviderContainer container, String jobId) {
  if (container.read(scanJobTrackerProvider).job?.id != jobId) return;
  container.read(scanJobTrackerProvider.notifier).dismiss();
}

/// Awaits a started [ScanJobTracker.retry] and reports a refusal or a
/// failure on [messenger].
Future<void> reportScanRetry(
  Future<void> retrying, {
  required ScanMode mode,
  ScaffoldMessengerState? messenger,
}) async {
  try {
    await retrying;
  } on ScanRefused catch (e) {
    final message = scanRefusalMessage(e, mode: mode);
    if (message != null) {
      messenger?.showSnackBar(SnackBar(content: Text(message)));
    }
  } catch (e) {
    debugPrint('[SCAN_JOB] Retry failed: $e');
    messenger?.showSnackBar(
      const SnackBar(content: Text("Couldn't start the check. Try again.")),
    );
  }
}
