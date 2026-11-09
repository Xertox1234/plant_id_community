import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/plant.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import '../../shared/widgets/api_image.dart';
import 'scan_job_api.dart';

/// One scan job, fetched fresh by id (the tracker's copy is gone after a
/// restart or a push tap). No automatic retry: a failure shows the error
/// screen at once rather than spinning through Riverpod's backoff.
final scanJobProvider = FutureProvider.autoDispose.family<ScanJob, String>(
  (ref, id) => ref.watch(scanJobApiProvider).get(id),
  retry: (_, _) => null,
);

/// Finished scans the user has not kept or dismissed yet (My Plants shows
/// them as cards). Empty while signed out.
final undecidedScansProvider = FutureProvider.autoDispose<List<ScanJob>>((
  ref,
) async {
  if (ref.watch(currentUserIdProvider) == null) return const [];
  return ref.watch(scanJobApiProvider).undecided();
});

/// Keep, dismiss and remove: the server decision comes first and Firestore
/// follows, so a failed call (offline, refused) changes nothing on the phone.
/// An [ApiException] from the server step propagates for the UI to show.
class ScanDecisions {
  ScanDecisions(this._ref);

  final Ref _ref;

  String _requireUid() {
    final uid = _ref.read(currentUserIdProvider);
    if (uid == null) throw StateError('Sign in to keep or remove a scan.');
    return uid;
  }

  /// Keeps [job]: the server marks it kept, then the plant is saved to
  /// Firestore (the one place a scan becomes a saved plant).
  Future<void> keep(ScanJob job) async {
    final result = job.result;
    if (result == null) {
      throw StateError('Cannot keep a scan that has no result.');
    }
    final uid = _requireUid();
    await _refreshIfRefused(
      job.id,
      () => _ref.read(scanJobApiProvider).keep(job.id),
    );
    await _ref
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
            timestamp: job.createdAt,
          ),
        );
    _ref.invalidate(undecidedScansProvider);
  }

  Future<void> dismiss(String jobId) async {
    await _refreshIfRefused(
      jobId,
      () => _ref.read(scanJobApiProvider).dismiss(jobId),
    );
    _ref.invalidate(undecidedScansProvider);
    await _evictPhotos(jobId);
  }

  /// Runs the server step of a decision. A refusal (404: the scan is gone;
  /// 409: another device decided first) also reloads the undecided list and
  /// the job, so the screen re-renders from the server's answer; the error
  /// still propagates for the SnackBar.
  Future<void> _refreshIfRefused(
    String jobId,
    Future<void> Function() call,
  ) async {
    try {
      await call();
    } on ApiException catch (e) {
      if (e.statusCode == 404 || e.statusCode == 409) {
        _ref.invalidate(undecidedScansProvider);
        _ref.invalidate(scanJobProvider(jobId));
      }
      rethrow;
    }
  }

  /// Drops the erased scan's photos from the phone's photo caches. Never
  /// fails the decision: the server step already succeeded.
  Future<void> _evictPhotos(String jobId) async {
    try {
      await evictScanPhotos(_ref.read(privatePhotoCacheProvider), jobId);
    } catch (e) {
      debugPrint('[SCAN_JOB] Photo eviction failed: ${e.runtimeType}');
    }
  }

  /// Removes a saved plant. A scan plant (its image is one of our scan photo
  /// URLs) is removed on the server first; a legacy plant only loses its doc.
  Future<void> removePlant(Plant plant) async {
    final uid = _requireUid();
    final jobId = ScanJobApi.jobIdFromPhotoUrl(plant.imageUrl);
    if (jobId != null) {
      try {
        await _ref.read(scanJobApiProvider).remove(jobId);
      } on ApiException catch (e) {
        // 404: the server already forgot it; finish the local delete.
        if (e.statusCode != 404) rethrow;
      }
    }
    await _ref
        .read(firestoreServiceProvider.notifier)
        .deletePlant(uid, plant.id);
    if (jobId != null) await _evictPhotos(jobId);
  }
}

final scanDecisionsProvider = Provider<ScanDecisions>(ScanDecisions.new);
