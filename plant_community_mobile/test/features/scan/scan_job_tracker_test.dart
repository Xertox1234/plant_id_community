import 'dart:async';
import 'dart:collection';

import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

const _uid = 'user-1';
const _jobId = 'job-1';
const _otherJobId = 'job-2';
const _poll = Duration(seconds: 3);

ScanJob _job(
  ScanJobStatus status, {
  String id = _jobId,
  ScanMode mode = ScanMode.diagnose,
  bool withResult = true,
}) => ScanJob(
  id: id,
  mode: mode,
  status: status,
  chargedAs: status.hasResult ? mode.name : '',
  result: status.hasResult && withResult
      ? const ScanJobResult(
          plantName: 'Monstera',
          scientificName: 'Monstera deliciosa',
          confidence: 0.9,
          description: 'A climbing aroid.',
          diagnosis: null,
        )
      : null,
  photos: const {},
  coverPhoto: 'https://api.test/scans/$id/photos/whole/',
  createdAt: DateTime.utc(2026, 11, 2, 9, 30),
);

ScanAllowance _allowance({
  int diagnoseRemaining = 1,
  int identifyRemaining = 5,
  bool plantIdAvailable = true,
  int slowAfterSeconds = 45,
}) => ScanAllowance(
  isPremium: false,
  diagnoseRemaining: diagnoseRemaining,
  diagnoseLimit: 1,
  identifyRemaining: identifyRemaining,
  identifyLimit: 5,
  resetsAt: DateTime.utc(2026, 11, 3),
  plantIdAvailable: plantIdAvailable,
  slowAfterSeconds: slowAfterSeconds,
  premiumDiagnoseLimit: 3,
);

const _capture = CaptureResult(
  mode: ScanMode.diagnose,
  shots: {CaptureRole.problem: '/tmp/p.jpg', CaptureRole.whole: '/tmp/w.jpg'},
);

/// Records every call in [calls]; `get` answers from [gets] in order and
/// repeats the last answer once the queue is down to one.
class _FakeScanJobApi extends ScanJobApi {
  _FakeScanJobApi() : super(ApiService(baseUrl: 'https://api.test'));

  final calls = <String>[];
  ScanAllowance allowanceValue = _allowance();
  Object? createError;
  Completer<void>? createGate;
  ScanJob createJob = _job(ScanJobStatus.pending);
  final gets = Queue<ScanJob>();
  ScanJob cancelJob = _job(ScanJobStatus.cancelled);

  @override
  Future<ScanAllowance> allowance() async {
    calls.add('allowance');
    return allowanceValue;
  }

  @override
  Future<ScanJob> create(
    CaptureResult r, {
    void Function(double)? onProgress,
  }) async {
    calls.add('create');
    onProgress?.call(0.5);
    await createGate?.future;
    if (createError != null) throw createError!;
    onProgress?.call(1);
    return createJob;
  }

  @override
  Future<ScanJob> get(String id) async {
    calls.add('get:$id');
    return gets.length > 1 ? gets.removeFirst() : gets.first;
  }

  @override
  Future<ScanJob> cancel(String id) async {
    calls.add('cancel:$id');
    return cancelJob;
  }
}

/// The real Firestore write path over a fake, plus a call count: a doc count
/// can't tell one write from two to the same id.
class _CountingFirestoreService extends FirestoreService {
  final saved = <Plant>[];

  /// When set, a save waits on it: an offline Firestore `set` can take long.
  Completer<void>? gate;
  Object? error;

  @override
  Future<void> savePlant(String userId, Plant plant) async {
    saved.add(plant);
    await gate?.future;
    if (error != null) throw error!;
    await super.savePlant(userId, plant);
  }
}

class _Harness {
  _Harness() {
    container = ProviderContainer(
      overrides: [
        scanJobApiProvider.overrideWithValue(api),
        scanTrackerStorageProvider.overrideWithValue(
          const FlutterSecureStorage(),
        ),
        scanTrackerClockProvider.overrideWithValue(() => now),
        currentUserIdProvider.overrideWithValue(_uid),
        firebaseFirestoreProvider.overrideWithValue(firestore),
        firestoreServiceProvider.overrideWith(() => store),
      ],
    );
    container.listen(scanJobTrackerProvider, (_, _) {});
  }

  final api = _FakeScanJobApi();
  final firestore = FakeFirebaseFirestore();
  final store = _CountingFirestoreService();
  DateTime now = DateTime.utc(2026, 11, 2, 9, 30);
  late final ProviderContainer container;

  ScanJobTracker get tracker => container.read(scanJobTrackerProvider.notifier);
  ScanTrackerState get state => container.read(scanJobTrackerProvider);

  Future<String?> storedId() =>
      const FlutterSecureStorage().read(key: scanJobPendingIdKey);

  Future<int> collectionDocs() async =>
      (await firestore
              .collection('users')
              .doc(_uid)
              .collection('identified_plants')
              .get())
          .docs
          .length;

  /// Advances fake time by one poll interval and drains the work it starts.
  Future<void> tick(WidgetTester tester) async {
    await tester.pump(_poll);
    await tester.pump();
  }
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('submit refuses before upload when diagnoses remaining is 0', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.allowanceValue = _allowance(diagnoseRemaining: 0);

    await expectLater(
      h.tracker.submit(_capture),
      throwsA(
        isA<ScanRefused>()
            .having((e) => e.code, 'code', 'allowance_exhausted')
            .having((e) => e.kind, 'kind', 'diagnose'),
      ),
    );

    expect(h.api.calls, isNot(contains('create')));
    expect(h.state.phase, TrackerPhase.idle);
    expect(await h.storedId(), isNull);
    h.container.dispose();
  });

  testWidgets(
    'submit uploads, stores the id, then polling to done saves the collection '
    'once and becomes ready',
    (tester) async {
      final h = _Harness();
      await h.tracker.restored;
      h.api.gets.addAll([
        _job(ScanJobStatus.processing),
        _job(ScanJobStatus.done),
      ]);

      await h.tracker.submit(_capture);

      expect(h.api.calls, containsAllInOrder(['allowance', 'create']));
      expect(h.state.phase, TrackerPhase.waiting);
      expect(h.state.job?.id, _jobId);
      expect(h.state.lastCapture, same(_capture));
      expect(await h.storedId(), _jobId);

      await h.tick(tester); // processing
      expect(h.state.phase, TrackerPhase.waiting);
      expect(h.store.saved, isEmpty);

      await h.tick(tester); // done
      expect(h.state.phase, TrackerPhase.ready);
      expect(h.state.job?.status, ScanJobStatus.done);

      // Later ticks find no timer and write nothing more.
      await h.tick(tester);
      await h.tick(tester);
      expect(h.store.saved, hasLength(1));
      final plant = h.store.saved.single;
      expect(plant.id, _jobId);
      expect(plant.name, 'Monstera');
      expect(plant.scientificName, 'Monstera deliciosa');
      expect(plant.description, 'A climbing aroid.');
      expect(plant.care, isEmpty);
      expect(plant.imageUrl, 'https://api.test/scans/$_jobId/photos/whole/');
      expect(await h.collectionDocs(), 1);
      expect(await h.storedId(), isNull);
      expect(h.api.calls.where((c) => c == 'get:$_jobId'), hasLength(2));
      h.container.dispose();
    },
  );

  testWidgets('goes slow after slowAfterSeconds with no result', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.allowanceValue = _allowance(slowAfterSeconds: 10);
    h.api.gets.add(_job(ScanJobStatus.processing));

    await h.tracker.submit(_capture);
    h.now = h.now.add(const Duration(seconds: 9));
    await h.tick(tester);
    expect(h.state.phase, TrackerPhase.waiting);

    h.now = h.now.add(const Duration(seconds: 1));
    await h.tick(tester);
    expect(h.state.phase, TrackerPhase.slow);

    // Slow keeps polling.
    h.api.gets
      ..clear()
      ..add(_job(ScanJobStatus.done));
    await h.tick(tester);
    expect(h.state.phase, TrackerPhase.ready);
    h.container.dispose();
  });

  testWidgets('cancel calls the API, clears storage, returns to idle', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.gets.add(_job(ScanJobStatus.processing));
    await h.tracker.submit(_capture);
    expect(await h.storedId(), _jobId);

    await h.tracker.cancel();

    expect(h.api.calls, contains('cancel:$_jobId'));
    expect(h.state.phase, TrackerPhase.idle);
    expect(h.state.job, isNull);
    expect(await h.storedId(), isNull);

    // Polling stopped.
    final gets = h.api.calls.where((c) => c.startsWith('get:')).length;
    await h.tick(tester);
    await h.tick(tester);
    expect(h.api.calls.where((c) => c.startsWith('get:')).length, gets);
    h.container.dispose();
  });

  testWidgets('failed keeps lastCapture and retry re-submits it', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.gets.add(_job(ScanJobStatus.failed));
    await h.tracker.submit(_capture);

    await h.tick(tester);
    expect(h.state.phase, TrackerPhase.failed);
    expect(h.state.lastCapture, same(_capture));
    expect(await h.storedId(), isNull);
    expect(h.store.saved, isEmpty);

    h.api.createJob = _job(ScanJobStatus.pending, id: _otherJobId);
    h.api.gets
      ..clear()
      ..add(_job(ScanJobStatus.processing, id: _otherJobId));
    await h.tracker.retry();

    expect(h.api.calls.where((c) => c == 'create'), hasLength(2));
    expect(h.state.phase, TrackerPhase.waiting);
    expect(h.state.job?.id, _otherJobId);
    expect(await h.storedId(), _otherJobId);
    h.container.dispose();
  });

  testWidgets(
    'restore after a kill: stored id + finished job → ready and one collection '
    'write',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({scanJobPendingIdKey: _jobId});
      final h = _Harness();
      h.api.gets.add(_job(ScanJobStatus.done));

      await h.tracker.restored;
      await tester.pump();

      expect(h.api.calls, ['get:$_jobId']);
      expect(h.state.phase, TrackerPhase.ready);
      expect(h.state.job?.id, _jobId);

      // A push for the same job landing after the save must not write again.
      await h.tracker.onPush(_jobId);
      await h.tick(tester);
      expect(h.store.saved, hasLength(1));
      expect(await h.collectionDocs(), 1);
      expect(await h.storedId(), isNull);
      h.container.dispose();
    },
  );

  testWidgets('onPush for another job id does nothing', (tester) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.gets.add(_job(ScanJobStatus.processing));
    await h.tracker.submit(_capture);
    final before = List.of(h.api.calls);

    await h.tracker.onPush(_otherJobId);

    expect(h.api.calls, before);
    expect(h.state.phase, TrackerPhase.waiting);
    expect(h.state.job?.id, _jobId);
    h.container.dispose();
  });

  testWidgets('create answering 409 scan_in_progress adopts that job and polls '
      'it', (tester) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.createError = const ScanRefused(
      code: 'scan_in_progress',
      jobId: _otherJobId,
    );
    h.api.gets.addAll([
      _job(ScanJobStatus.processing, id: _otherJobId),
      _job(ScanJobStatus.done, id: _otherJobId),
    ]);

    await h.tracker.submit(_capture);

    expect(h.state.phase, TrackerPhase.waiting);
    expect(h.state.job?.id, _otherJobId);
    expect(await h.storedId(), _otherJobId);

    await h.tick(tester);
    expect(h.state.phase, TrackerPhase.ready);
    expect(h.store.saved.single.id, _otherJobId);
    expect(h.api.calls.where((c) => c == 'get:$_otherJobId'), hasLength(2));
    h.container.dispose();
  });

  testWidgets('other refusals and API errors are rethrown', (tester) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.createError = const ScanRefused(code: 'plant_id_busy');
    await expectLater(h.tracker.submit(_capture), throwsA(isA<ScanRefused>()));
    expect(h.state.phase, TrackerPhase.idle);

    h.api.createError = ApiException('boom', statusCode: 500);
    await expectLater(h.tracker.submit(_capture), throwsA(isA<ApiException>()));
    expect(h.state.phase, TrackerPhase.idle);
    expect(await h.storedId(), isNull);
    h.container.dispose();
  });

  testWidgets(
    'a poll landing while the save is in flight writes nothing more',
    (tester) async {
      final h = _Harness();
      await h.tracker.restored;
      h.store.gate = Completer<void>();
      h.api.gets.add(_job(ScanJobStatus.processing));
      await h.tracker.submit(_capture);
      h.api.gets
        ..clear()
        ..add(_job(ScanJobStatus.done));

      await h.tick(tester); // done: the save starts and blocks
      expect(h.state.phase, TrackerPhase.ready);
      expect(h.store.saved, hasLength(1));

      // Ticks and a push arrive while the save is still open.
      await h.tick(tester);
      await h.tracker.onPush(_jobId);
      await h.tick(tester);
      expect(h.store.saved, hasLength(1));
      // Cleared only after the save, so a kill now restores and re-saves.
      expect(await h.storedId(), _jobId);

      h.store.gate!.complete();
      await tester.pump();
      expect(h.store.saved, hasLength(1));
      expect(await h.collectionDocs(), 1);
      expect(await h.storedId(), isNull);
      h.container.dispose();
    },
  );

  testWidgets('cancel during the upload cancels the job once it exists', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.createGate = Completer<void>();
    final submitting = h.tracker.submit(_capture);
    await tester.pump();
    expect(h.state.phase, TrackerPhase.uploading);

    await h.tracker.cancel();
    expect(h.state.phase, TrackerPhase.idle);

    h.api.createGate!.complete();
    await submitting;
    await tester.pump();
    expect(h.api.calls, contains('cancel:$_jobId'));
    expect(h.state.phase, TrackerPhase.idle);
    expect(await h.storedId(), isNull);
    h.container.dispose();
  });

  testWidgets('a failed collection save keeps the id for the next launch', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.store.error = StateError('offline');
    h.api.gets.add(_job(ScanJobStatus.done));
    await h.tracker.submit(_capture);
    await h.tick(tester);

    expect(h.state.phase, TrackerPhase.ready);
    expect(await h.storedId(), _jobId);

    h.tracker.dismiss();
    await tester.pump();
    expect(await h.storedId(), isNull);
    h.container.dispose();
  });

  testWidgets('pausing the app stops polling; resuming polls again', (
    tester,
  ) async {
    final h = _Harness();
    await h.tracker.restored;
    h.api.gets.add(_job(ScanJobStatus.processing));
    await h.tracker.submit(_capture);
    int gets() => h.api.calls.where((c) => c.startsWith('get:')).length;

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    final paused = gets();
    await h.tick(tester);
    await h.tick(tester);
    expect(gets(), paused);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(gets(), paused + 1); // immediate catch-up GET
    await h.tick(tester);
    expect(gets(), paused + 2);
    h.container.dispose();
  });
}
