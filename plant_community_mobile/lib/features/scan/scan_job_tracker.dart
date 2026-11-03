import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../models/plant.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import 'capture_session.dart';
import 'capture_steps.dart';
import 'scan_job_api.dart';

part 'scan_job_tracker.g.dart';

/// Secure-storage key holding the id of the job still being tracked, so a
/// scan survives the app being killed.
const scanJobPendingIdKey = 'scan_job.pending_id';

/// How often a running job is re-read.
const scanJobPollInterval = Duration(seconds: 3);

/// Used when no allowance was read (a restored or adopted job).
const defaultSlowAfterSeconds = 45;

/// Injected so tests can use the package's in-memory platform.
final scanTrackerStorageProvider = Provider<FlutterSecureStorage>(
  (ref) => const FlutterSecureStorage(),
);

/// Injected so tests can move time for the "slow" check.
final scanTrackerClockProvider = Provider<DateTime Function()>(
  (ref) => DateTime.now,
);

enum TrackerPhase { idle, uploading, waiting, slow, ready, failed }

class ScanTrackerState {
  const ScanTrackerState({
    this.phase = TrackerPhase.idle,
    this.uploadProgress,
    this.job,
    this.lastCapture,
  });

  final TrackerPhase phase;

  /// 0..1 while [TrackerPhase.uploading]; null before the first report.
  final double? uploadProgress;
  final ScanJob? job;

  /// The capture last submitted, kept so a failed scan can be retried.
  final CaptureResult? lastCapture;
}

/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval], and saves a finished plant to My Collection once.
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET or save that lands after one
/// of them is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten, and
/// a result is only ever saved to its owner's collection.
@Riverpod(keepAlive: true)
class ScanJobTracker extends _$ScanJobTracker {
  /// The tracked job, mirrored in storage under [scanJobPendingIdKey].
  String? _pendingId;
  int _gen = 0;
  Timer? _timer;
  AppLifecycleListener? _lifecycle;
  bool _paused = false;

  /// Set from [submit]'s first check until it ends, so a double tap can't
  /// start two uploads.
  bool _submitting = false;

  /// Generation of the GET in flight, so ticks can't stack calls.
  int? _fetchingGen;

  /// The job whose terminal status was handled. Set before the first await
  /// so a second poll or push for the same finished job does nothing.
  String? _handledId;
  DateTime? _uploadFinishedAt;
  int _slowAfterSeconds = defaultSlowAfterSeconds;
  Future<void>? _restoring;

  /// The user the tracked job (and the shown state) belongs to.
  String? _ownerUid;

  /// Set when a restore had no signed-in user (or was refused with 401/403):
  /// the next sign-in runs it.
  bool _restoreDeferred = false;

  FlutterSecureStorage get _storage => ref.read(scanTrackerStorageProvider);
  ScanJobApi get _api => ref.read(scanJobApiProvider);
  DateTime _now() => ref.read(scanTrackerClockProvider)();

  @override
  ScanTrackerState build() {
    _lifecycle = AppLifecycleListener(onPause: _onPause, onResume: _onResume);
    ref.onDispose(() {
      _timer?.cancel();
      _lifecycle?.dispose();
    });
    ref.listen<String?>(currentUserIdProvider, (_, next) => _onUser(next));
    _restoring = restore();
    unawaited(_restoring);
    return const ScanTrackerState();
  }

  /// Completes once [restore] (started by `build`) has finished.
  Future<void> get restored => _restoring ?? Future<void>.value();

  /// Starts a scan of [r]. Throws [ScanRefused] without uploading when the
  /// allowance says no; rethrows other server refusals and [ApiException]s.
  /// A 409 `scan_in_progress` is adopted: that job is tracked instead.
  Future<void> submit(CaptureResult r) async {
    await restored;
    if (_submitting || _isActive(state.phase)) {
      throw StateError('A scan is already running.');
    }
    _submitting = true;
    try {
      await _submit(r);
    } finally {
      _submitting = false;
    }
  }

  Future<void> _submit(CaptureResult r) async {
    // The pre-check runs before anything changes, so a refusal leaves the
    // current job (and its pending save) untouched. A cancel, dismiss or user
    // change during it bumps [_gen] or changes the user: then nothing starts.
    final before = _gen;
    final uid = ref.read(currentUserIdProvider);
    ScanAllowance? allowance;
    try {
      allowance = await _api.allowance();
    } on Exception catch (e) {
      // The server checks again on create; don't block a scan on this read.
      debugPrint('[SCAN_JOB] Allowance pre-check failed: $e');
    }
    if (!_current(before) || ref.read(currentUserIdProvider) != uid) return;
    if (allowance != null) {
      if (allowance.remainingFor(r.mode) <= 0) {
        throw ScanRefused(code: 'allowance_exhausted', kind: r.mode.name);
      }
      if (r.mode == ScanMode.diagnose && !allowance.plantIdAvailable) {
        throw const ScanRefused(code: 'plant_id_busy');
      }
    }

    final gen = ++_gen;
    _stopTimer();
    _pendingId = null;
    _handledId = null;
    _restoreDeferred = false;
    _ownerUid = uid;
    _slowAfterSeconds = allowance?.slowAfterSeconds ?? defaultSlowAfterSeconds;

    state = ScanTrackerState(phase: TrackerPhase.uploading, lastCapture: r);
    ScanJob job;
    try {
      job = await _api.create(
        r,
        onProgress: (p) {
          if (_current(gen) && state.phase == TrackerPhase.uploading) {
            state = ScanTrackerState(
              phase: TrackerPhase.uploading,
              uploadProgress: p,
              lastCapture: r,
            );
          }
        },
      );
    } on ScanRefused catch (e) {
      final adopted = e.jobId;
      if (e.code != 'scan_in_progress' || adopted == null) {
        if (_current(gen)) state = ScanTrackerState(lastCapture: r);
        rethrow;
      }
      if (!_current(gen)) return;
      await _track(adopted);
      if (!_current(gen)) return;
      _uploadFinishedAt = null;
      try {
        job = await _api.get(adopted);
      } on Exception catch (e) {
        // Polling recovers it; the id is stored.
        debugPrint('[SCAN_JOB] Adopted job read failed: $e');
        if (!_current(gen)) return;
        state = ScanTrackerState(phase: TrackerPhase.waiting, lastCapture: r);
        _startTimer();
        return;
      }
      if (!_current(gen)) return;
      state = ScanTrackerState(
        phase: TrackerPhase.waiting,
        job: job,
        lastCapture: r,
      );
      _apply(job, gen);
      return;
    } catch (_) {
      if (_current(gen)) state = ScanTrackerState(lastCapture: r);
      rethrow;
    }
    if (!_current(gen)) {
      // Cancelled or dismissed during the upload: the server job exists
      // now, so cancel it rather than leave it holding the scan slot.
      unawaited(
        _api
            .cancel(job.id)
            .then<void>(
              (_) {},
              onError: (Object e) {
                debugPrint('[SCAN_JOB] Cancel after upload failed: $e');
              },
            ),
      );
      return;
    }
    _uploadFinishedAt = _now();
    await _track(job.id);
    if (!_current(gen)) return;
    state = ScanTrackerState(
      phase: TrackerPhase.waiting,
      job: job,
      lastCapture: r,
    );
    _apply(job, gen);
  }

  /// Cancels the running job, clears the stored id and returns to idle.
  /// During the upload there is no id yet: the job is cancelled as soon as
  /// the upload answers. When
  /// the job already finished (409 `not_active`), its result is applied
  /// instead, since the scan was charged.
  Future<void> cancel() async {
    final id = _pendingId;
    final gen = ++_gen;
    _stopTimer();
    if (id == null) {
      state = const ScanTrackerState();
      return;
    }
    ScanJob job;
    try {
      try {
        job = await _api.cancel(id);
      } on ApiException catch (e) {
        if (e.code != 'not_active') rethrow;
        job = await _api.get(id);
      }
    } catch (_) {
      // Still running as far as we know: keep tracking it.
      if (_current(gen)) _startTimer();
      rethrow;
    }
    if (!_current(gen)) return;
    if (job.status.hasResult || job.status == ScanJobStatus.failed) {
      _apply(job, gen);
      return;
    }
    _pendingId = null;
    state = const ScanTrackerState();
    await _clearStored();
  }

  /// Re-submits [ScanTrackerState.lastCapture]. Only valid in `failed`.
  Future<void> retry() async {
    final capture = state.lastCapture;
    if (state.phase != TrackerPhase.failed || capture == null) {
      throw StateError('Only a failed scan with its capture can be retried.');
    }
    await submit(capture);
  }

  /// Forgets the job (after its result was viewed, or a failure closed).
  void dismiss() {
    _gen++;
    _stopTimer();
    _pendingId = null;
    state = const ScanTrackerState();
    unawaited(_clearStored());
  }

  /// Picks up the job stored before the app was killed.
  ///
  /// With nobody signed in yet it waits for the sign-in. A job id stored by
  /// another user is answered 404 by the server and cleared.
  Future<void> restore() async {
    final gen = _gen;
    final uid = ref.read(currentUserIdProvider);
    if (uid == null || uid.isEmpty) {
      _restoreDeferred = true;
      return;
    }
    _restoreDeferred = false;
    String? id;
    try {
      id = await _storage.read(key: scanJobPendingIdKey);
    } catch (e) {
      debugPrint('[SCAN_JOB] Pending id read failed: $e');
    }
    if (id == null || !ref.mounted || !_current(gen)) return;
    _pendingId = id;
    _ownerUid = uid;
    _uploadFinishedAt = null;
    ScanJob job;
    try {
      job = await _api.get(id);
    } on ApiException catch (e) {
      if (!_current(gen) || _handledReadError(e)) return;
      debugPrint('[SCAN_JOB] Restored job read failed: $e');
      state = const ScanTrackerState(phase: TrackerPhase.waiting);
      _startTimer();
      return;
    } catch (e) {
      debugPrint('[SCAN_JOB] Restored job read failed: $e');
      if (!_current(gen)) return;
      state = const ScanTrackerState(phase: TrackerPhase.waiting);
      _startTimer();
      return;
    }
    if (!_current(gen)) return;
    state = ScanTrackerState(phase: TrackerPhase.waiting, job: job);
    _apply(job, gen);
  }

  /// A push said [jobId] finished: re-read it now when it is ours.
  Future<void> onPush(String jobId) async {
    if (jobId != _pendingId) return;
    await _poll();
  }

  bool _current(int gen) => ref.mounted && gen == _gen;

  /// Drops the tracked job and returns to idle. The stored id is kept when
  /// [keepStored], so a later restore can pick the job up again.
  void _forget({required bool keepStored}) {
    _gen++;
    _stopTimer();
    _pendingId = null;
    _handledId = null;
    _ownerUid = null;
    state = const ScanTrackerState();
    if (!keepStored) unawaited(_clearStored());
  }

  /// Handles a job read that will not succeed by asking again. True when
  /// [e] was one: 404 (gone, or not this user's) forgets the job; 401/403
  /// stops polling but keeps the stored id for a restore after sign-in.
  bool _handledReadError(ApiException e) {
    switch (e.statusCode) {
      case 404:
        _forget(keepStored: false);
        return true;
      case 401 || 403:
        _forget(keepStored: true);
        _restoreDeferred = true;
        return true;
      default:
        return false;
    }
  }

  void _onUser(String? uid) {
    if (_ownerUid != null && uid != _ownerUid) {
      // Signed out, or someone else signed in: nothing of this job may
      // show, poll or save in their session. The bump is synchronous, so no
      // continuation acts on the job; the state write waits a microtask,
      // because this can run inside our own `ref.read` (mid-[_apply]), where
      // a nested state write does not stick.
      _gen++;
      _stopTimer();
      _pendingId = null;
      _handledId = null;
      _ownerUid = null;
      final gen = _gen;
      scheduleMicrotask(() {
        if (_current(gen)) _forget(keepStored: false);
      });
      return;
    }
    if (_restoreDeferred && uid != null && uid.isNotEmpty) {
      _restoring = restore();
      unawaited(_restoring);
    }
  }

  static bool _isActive(TrackerPhase p) =>
      p == TrackerPhase.uploading ||
      p == TrackerPhase.waiting ||
      p == TrackerPhase.slow;

  Future<void> _track(String id) async {
    _pendingId = id;
    try {
      await _storage.write(key: scanJobPendingIdKey, value: id);
    } catch (e) {
      debugPrint('[SCAN_JOB] Pending id write failed: $e');
    }
  }

  Future<void> _clearStored() async {
    try {
      await _storage.delete(key: scanJobPendingIdKey);
    } catch (e) {
      debugPrint('[SCAN_JOB] Pending id clear failed: $e');
    }
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = null;
    if (_paused) return;
    _timer = Timer.periodic(scanJobPollInterval, (_) => unawaited(_poll()));
  }

  void _stopTimer() {
    _timer?.cancel();
    _timer = null;
  }

  void _onPause() {
    _paused = true;
    _stopTimer();
  }

  void _onResume() {
    _paused = false;
    if (_restoreDeferred) {
      // A 401/403 stopped polling; the token may have been refreshed since.
      _restoring = restore();
      unawaited(_restoring);
      return;
    }
    if (_pendingId == null || !_isActive(state.phase)) return;
    _startTimer();
    unawaited(_poll());
  }

  Future<void> _poll() async {
    final id = _pendingId;
    final gen = _gen;
    if (id == null || _fetchingGen == gen || _handledId == id) return;
    _fetchingGen = gen;
    try {
      final job = await _api.get(id);
      if (_current(gen)) _apply(job, gen);
    } on ApiException catch (e) {
      if (!_current(gen) || _handledReadError(e)) return;
      debugPrint('[SCAN_JOB] Poll failed: $e');
      _markSlowIfDue(state.job);
    } catch (e) {
      debugPrint('[SCAN_JOB] Poll failed: $e');
      if (_current(gen)) _markSlowIfDue(state.job);
    } finally {
      if (_fetchingGen == gen) _fetchingGen = null;
    }
  }

  /// Moves the state to match [job]. Terminal handling is synchronous up to
  /// the collection save, so a second tick or push finds [_handledId] set.
  void _apply(ScanJob job, int gen) {
    if (job.id != _pendingId || _handledId == job.id) return;
    final capture = state.lastCapture;
    if (job.status.isActive) {
      _markSlowIfDue(job);
      if (_timer == null) _startTimer();
      return;
    }
    _handledId = job.id;
    _stopTimer();
    if (job.status.hasResult) {
      state = ScanTrackerState(
        phase: TrackerPhase.ready,
        job: job,
        lastCapture: capture,
      );
      unawaited(_saveThenClear(job, gen));
    } else if (job.status == ScanJobStatus.failed) {
      state = ScanTrackerState(
        phase: TrackerPhase.failed,
        job: job,
        lastCapture: capture,
      );
      _pendingId = null;
      unawaited(_clearStored());
    } else {
      // Cancelled.
      _pendingId = null;
      state = const ScanTrackerState();
      unawaited(_clearStored());
    }
  }

  void _markSlowIfDue(ScanJob? job) {
    if (!_isActive(state.phase) || state.phase == TrackerPhase.uploading) {
      return;
    }
    // A restored or adopted job has no upload time here: count from when
    // the server created it.
    final since = _uploadFinishedAt ?? job?.createdAt;
    final slow =
        state.phase == TrackerPhase.slow ||
        (since != null &&
            _now().difference(since) >= Duration(seconds: _slowAfterSeconds));
    state = ScanTrackerState(
      phase: slow ? TrackerPhase.slow : TrackerPhase.waiting,
      job: job ?? state.job,
      lastCapture: state.lastCapture,
    );
  }

  /// The stored id is cleared only after the save, so a kill in between
  /// restores the job and saves it again under the same doc id.
  Future<void> _saveThenClear(ScanJob job, int gen) async {
    final result = job.result;
    final uid = ref.read(currentUserIdProvider);
    if (uid == null || uid.isEmpty || uid != _ownerUid) {
      // Nobody to save for (auth not restored yet), or not the job's owner.
      // Keep the stored id so its owner's next restore saves it.
      debugPrint('[SCAN_JOB] Job ${job.id} not saved: not its owner.');
      return;
    }
    if (result != null) {
      // The Firestore service auto-disposes; hold it for the whole write.
      final keep = ref.listen(firestoreServiceProvider, (_, _) {});
      try {
        await ref
            .read(firestoreServiceProvider.notifier)
            .savePlant(
              uid,
              Plant(
                id: job.id,
                name: result.plantName,
                scientificName: result.scientificName,
                description: result.description,
                care: const [],
                imageUrl: job.coverPhoto,
                // The job's own time, so a repeat save writes the same doc.
                timestamp: job.createdAt,
              ),
            );
      } catch (e) {
        // Keep the stored id: the next launch restores the job and saves
        // again (same doc id). A dismiss still clears it.
        debugPrint('[SCAN_JOB] Collection save failed: $e');
        return;
      } finally {
        keep.close();
      }
    } else {
      debugPrint('[SCAN_JOB] Finished job ${job.id} has no result to save.');
    }
    // A dismiss or new scan since then owns the stored id now.
    if (!_current(gen)) return;
    _pendingId = null;
    await _clearStored();
  }
}
