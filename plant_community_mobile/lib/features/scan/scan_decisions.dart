import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/plant.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import 'scan_job_api.dart';

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
    await _ref.read(scanJobApiProvider).keep(job.id);
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
    await _ref.read(scanJobApiProvider).dismiss(jobId);
    _ref.invalidate(undecidedScansProvider);
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
  }
}

final scanDecisionsProvider = Provider<ScanDecisions>(ScanDecisions.new);
