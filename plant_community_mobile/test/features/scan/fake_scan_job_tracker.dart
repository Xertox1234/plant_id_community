import 'dart:async';

import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';

/// A finished or running job for widget tests.
ScanJob fakeScanJob({
  String id = 'job-1',
  ScanJobStatus status = ScanJobStatus.pending,
}) => ScanJob(
  id: id,
  mode: ScanMode.diagnose,
  status: status,
  chargedAs: '',
  result: null,
  photos: const {},
  coverPhoto: null,
  createdAt: DateTime.utc(2026, 11, 2, 9, 30),
);

const fakeCapture = CaptureResult(
  mode: ScanMode.diagnose,
  shots: {CaptureRole.problem: '/tmp/p.jpg'},
);

/// Replaces the real tracker: no lifecycle listener, no auth listen, no
/// restore, no network. Seeded with [initial]; every call is recorded.
class FakeScanJobTracker extends ScanJobTracker {
  FakeScanJobTracker([this.initial = const ScanTrackerState()]);

  final ScanTrackerState initial;
  final submitted = <CaptureResult>[];

  /// The `retryOf` each [submit] received, in order.
  final retryOfs = <String?>[];
  final calls = <String>[];

  /// Thrown by [submit] after recording, when set.
  Object? submitError;

  /// When set, [submit] waits for it, reporting progress through [emit].
  Completer<void>? submitGate;

  @override
  ScanTrackerState build() => initial;

  /// Moves the state, as the real tracker's polling would.
  void emit(ScanTrackerState s) => state = s;

  @override
  Future<void> submit(CaptureResult r, {String? retryOf}) async {
    submitted.add(r);
    retryOfs.add(retryOf);
    calls.add('submit');
    final error = submitError;
    if (error != null) throw error;
    state = ScanTrackerState(phase: TrackerPhase.uploading, lastCapture: r);
    final gate = submitGate;
    if (gate != null) await gate.future;
    state = ScanTrackerState(
      phase: TrackerPhase.waiting,
      job: fakeScanJob(),
      lastCapture: r,
    );
  }

  @override
  Future<void> cancel() async {
    calls.add('cancel');
    state = const ScanTrackerState();
  }

  @override
  Future<void> retry() async {
    calls.add('retry');
  }

  @override
  Future<void> viewed(String jobId, {ScanJob? job}) async {
    calls.add('viewed:$jobId');
  }

  @override
  void dismiss() {
    calls.add('dismiss');
    state = const ScanTrackerState();
  }
}
