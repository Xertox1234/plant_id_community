import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_submitter.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/plant_identification_service.dart';

class FakeIdService extends PlantIdentificationService {
  FakeIdService({this.error, this.plant});

  final Object? error;
  final Plant? plant;
  final paths = <String>[];
  void Function(double)? progress;

  @override
  Future<Plant> identifyPlant(
    String imagePath, {
    Function(double progress)? onUploadProgress,
  }) async {
    paths.add(imagePath);
    progress = onUploadProgress?.call;
    onUploadProgress?.call(0.5);
    if (error != null) throw error!;
    return plant!;
  }
}

CaptureResult _r(Map<CaptureRole, String> shots) =>
    CaptureResult(mode: ScanMode.diagnose, shots: shots);

void main() {
  group('primaryShotFor', () {
    test('problem only -> problem', () {
      expect(primaryShotFor(_r({CaptureRole.problem: 'p'})), 'p');
    });
    test('problem + leaf -> leaf', () {
      expect(
        primaryShotFor(_r({CaptureRole.problem: 'p', CaptureRole.leaf: 'l'})),
        'l',
      );
    });
    test('problem + whole -> whole', () {
      expect(
        primaryShotFor(_r({CaptureRole.problem: 'p', CaptureRole.whole: 'w'})),
        'w',
      );
    });
    test('flower only -> flower', () {
      expect(primaryShotFor(_r({CaptureRole.flower: 'f'})), 'f');
    });
  });

  group('scanErrorMessage', () {
    test('maps the three error families', () {
      expect(scanErrorMessage(ApiException('boom')), 'API Error: boom');
      expect(scanErrorMessage(PlantIdentificationException('nope')), 'nope');
      expect(
        scanErrorMessage(StateError('x')),
        'Failed to identify plant. Please try again.',
      );
    });
  });

  group('ScanSubmitter', () {
    ProviderContainer containerWith(FakeIdService fake) {
      final c = ProviderContainer(
        overrides: [
          plantIdentificationServiceProvider.overrideWith(() => fake),
          currentUserIdProvider.overrideWithValue(null),
        ],
      );
      addTearDown(c.dispose);
      c.listen(scanSubmitterProvider, (_, _) {});
      return c;
    }

    test('submits the primary shot and reports progress', () async {
      final fake = FakeIdService(
        plant: Plant(
          id: 'x',
          name: 'Fern',
          scientificName: 'Pteridophyta',
          description: 'd',
          care: const [],
          timestamp: DateTime(2026),
        ),
      );
      final c = containerWith(fake);
      final plant = await c
          .read(scanSubmitterProvider.notifier)
          .submit(
            _r({CaptureRole.problem: 'p.jpg', CaptureRole.leaf: 'l.jpg'}),
          );
      expect(fake.paths, ['l.jpg']);
      expect(plant.id, 'x');
      expect(c.read(scanSubmitterProvider).value, 0.5);
    });

    test('rethrows and leaves an error state', () async {
      final fake = FakeIdService(
        error: PlantIdentificationException(
          'No plant could be identified from this image.',
        ),
      );
      final c = containerWith(fake);
      await expectLater(
        c
            .read(scanSubmitterProvider.notifier)
            .submit(_r({CaptureRole.leaf: 'l'})),
        throwsA(isA<PlantIdentificationException>()),
      );
      expect(c.read(scanSubmitterProvider).hasError, isTrue);
    });
  });
}
