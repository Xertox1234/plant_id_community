import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_decisions.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

const _uid = 'user-1';
const _jobId = '11111111-2222-3333-4444-555555555555';

ScanJob _job({bool withResult = true}) => ScanJob(
  id: _jobId,
  mode: ScanMode.diagnose,
  status: ScanJobStatus.done,
  chargedAs: 'diagnose',
  result: withResult
      ? const ScanJobResult(
          plantName: 'Monstera',
          scientificName: 'Monstera deliciosa',
          confidence: 0.9,
          description: 'A climbing aroid.',
          diagnosis: null,
        )
      : null,
  photos: const {},
  coverPhoto:
      'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/whole/',
  createdAt: DateTime.utc(2026, 11, 2, 9, 30),
  decision: ScanDecision.undecided,
);

class _FakeApi extends ScanJobApi {
  _FakeApi(this.calls) : super(ApiService(baseUrl: 'https://api.test'));

  final List<String> calls;
  Object? error;
  int undecidedCalls = 0;

  @override
  Future<ScanJob> keep(String id) async {
    calls.add('api.keep:$id');
    if (error != null) throw error!;
    return _job();
  }

  @override
  Future<void> dismiss(String id) async {
    calls.add('api.dismiss:$id');
    if (error != null) throw error!;
  }

  @override
  Future<void> remove(String id) async {
    calls.add('api.remove:$id');
    if (error != null) throw error!;
  }

  @override
  Future<List<ScanJob>> undecided() async {
    undecidedCalls++;
    return const [];
  }
}

class _FakeStore extends FirestoreService {
  _FakeStore(this.calls);
  final List<String> calls;
  final saved = <Plant>[];

  @override
  Future<void> savePlant(String userId, Plant plant) async {
    calls.add('fs.save:$userId:${plant.id}');
    saved.add(plant);
  }

  @override
  Future<void> deletePlant(String userId, String plantId) async {
    calls.add('fs.delete:$userId:$plantId');
  }
}

class _Rig {
  _Rig({String? uid = _uid}) {
    api = _FakeApi(calls);
    store = _FakeStore(calls);
    container = ProviderContainer(
      overrides: [
        scanJobApiProvider.overrideWithValue(api),
        currentUserIdProvider.overrideWith((ref) => uid),
        firestoreServiceProvider.overrideWith(() => store),
      ],
    );
  }

  final calls = <String>[];
  late final _FakeApi api;
  late final _FakeStore store;
  late final ProviderContainer container;

  ScanDecisions get decisions => container.read(scanDecisionsProvider);
}

Plant _plant({String id = 'p1', String? imageUrl}) => Plant(
  id: id,
  name: 'Monstera',
  scientificName: 'Monstera deliciosa',
  description: '',
  care: const [],
  imageUrl: imageUrl,
  timestamp: DateTime.utc(2026, 11, 2),
);

void main() {
  test('undecidedScansProvider is empty while signed out', () async {
    final container = ProviderContainer(
      overrides: [currentUserIdProvider.overrideWith((ref) => null)],
    );
    addTearDown(container.dispose);
    expect(await container.read(undecidedScansProvider.future), isEmpty);
  });

  test('keep calls api then firestore in that order', () async {
    final rig = _Rig();
    addTearDown(rig.container.dispose);
    await rig.decisions.keep(_job());
    expect(rig.calls, ['api.keep:$_jobId', 'fs.save:$_uid:$_jobId']);
    final p = rig.store.saved.single;
    expect(p.id, _jobId);
    expect(p.name, 'Monstera');
    expect(p.scientificName, 'Monstera deliciosa');
    expect(p.description, 'A climbing aroid.');
    expect(p.care, isEmpty);
    expect(p.imageUrl, _job().coverPhoto);
    expect(p.timestamp, DateTime.utc(2026, 11, 2, 9, 30));
  });

  test('keep does not write firestore when api keep fails', () async {
    final rig = _Rig();
    addTearDown(rig.container.dispose);
    final err = ApiException('offline', statusCode: 500);
    rig.api.error = err;
    await expectLater(rig.decisions.keep(_job()), throwsA(same(err)));
    expect(rig.calls, ['api.keep:$_jobId']);
  });

  test(
    'keep throws StateError without a result or a user, before any call',
    () async {
      final rig = _Rig();
      addTearDown(rig.container.dispose);
      await expectLater(
        rig.decisions.keep(_job(withResult: false)),
        throwsStateError,
      );
      final out = _Rig(uid: null);
      addTearDown(out.container.dispose);
      await expectLater(out.decisions.keep(_job()), throwsStateError);
      expect(rig.calls, isEmpty);
      expect(out.calls, isEmpty);
    },
  );

  test('dismiss invalidates the undecided list', () async {
    final rig = _Rig();
    addTearDown(rig.container.dispose);
    rig.container.listen(undecidedScansProvider, (_, _) {});
    await rig.container.read(undecidedScansProvider.future);
    expect(rig.api.undecidedCalls, 1);
    await rig.decisions.dismiss(_jobId);
    await rig.container.read(undecidedScansProvider.future);
    expect(rig.calls, ['api.dismiss:$_jobId']);
    expect(rig.api.undecidedCalls, 2);
  });

  final scanUrl =
      'https://api.test/api/v1/plant-identification/scans/$_jobId/photos/whole/';

  test(
    'removePlant on a scan plant calls api remove then deletePlant in that order',
    () async {
      final rig = _Rig();
      addTearDown(rig.container.dispose);
      await rig.decisions.removePlant(_plant(imageUrl: scanUrl));
      expect(rig.calls, ['api.remove:$_jobId', 'fs.delete:$_uid:p1']);
    },
  );

  test('removePlant does not delete the doc when api remove fails', () async {
    final rig = _Rig();
    addTearDown(rig.container.dispose);
    final err = ApiException('offline');
    rig.api.error = err;
    await expectLater(
      rig.decisions.removePlant(_plant(imageUrl: scanUrl)),
      throwsA(same(err)),
    );
    expect(rig.calls, ['api.remove:$_jobId']);
  });

  test(
    'removePlant ignores a 404 from api remove and still deletes the doc',
    () async {
      final rig = _Rig();
      addTearDown(rig.container.dispose);
      rig.api.error = ApiException('gone', statusCode: 404);
      await rig.decisions.removePlant(_plant(imageUrl: scanUrl));
      expect(rig.calls, ['api.remove:$_jobId', 'fs.delete:$_uid:p1']);
    },
  );

  test('removePlant on a legacy plant calls only deletePlant', () async {
    final rig = _Rig();
    addTearDown(rig.container.dispose);
    await rig.decisions.removePlant(
      _plant(imageUrl: 'https://firebasestorage.googleapis.com/x.jpg'),
    );
    expect(rig.calls, ['fs.delete:$_uid:p1']);
  });
}
