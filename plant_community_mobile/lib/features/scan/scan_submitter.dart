import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../models/plant.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import '../../services/plant_identification_service.dart';
import 'capture_session.dart';
import 'capture_steps.dart';

part 'scan_submitter.g.dart';

/// The one shot sent to identification: `leaf`, then `whole`, `problem`,
/// `flower`, whichever exists first.
///
/// Temporary: the endpoint takes a single image until Part 2.
String primaryShotFor(CaptureResult r) {
  for (final role in const [
    CaptureRole.leaf,
    CaptureRole.whole,
    CaptureRole.problem,
    CaptureRole.flower,
  ]) {
    final path = r.shots[role];
    if (path != null) return path;
  }
  throw StateError('A capture with no shots cannot be submitted.');
}

/// Maps a submit failure to the message the user sees.
String scanErrorMessage(Object error) => switch (error) {
  ApiException(:final message) => 'API Error: $message',
  PlantIdentificationException(:final message) => message,
  _ => 'Failed to identify plant. Please try again.',
};

/// Interim submitter: identifies the plant from [primaryShotFor]. State is the
/// upload progress (0..1), null until the first progress report.
@riverpod
class ScanSubmitter extends _$ScanSubmitter {
  @override
  AsyncValue<double?> build() => const AsyncData(null);

  Future<Plant> submit(CaptureResult r) async {
    state = const AsyncData(null);
    try {
      final plant = await ref
          .read(plantIdentificationServiceProvider.notifier)
          .identifyPlant(
            primaryShotFor(r),
            onUploadProgress: (p) {
              if (ref.mounted) state = AsyncData(p);
            },
          );
      _persistPlantOffline(plant);
      return plant;
    } catch (e, st) {
      if (ref.mounted) state = AsyncError(e, st);
      rethrow;
    }
  }

  /// Fire-and-forget: the local cache write is immediate while the server
  /// round-trip may never finish offline, so awaiting it would block
  /// navigation. Skipped when signed out.
  void _persistPlantOffline(Plant plant) {
    final uid = ref.read(currentUserIdProvider);
    if (uid == null || uid.isEmpty) return;
    unawaited(
      ref
          .read(firestoreServiceProvider.notifier)
          .savePlant(uid, plant)
          .catchError((Object e) {
            debugPrint('[SCAN] Offline persist failed: $e');
          }),
    );
  }
}
