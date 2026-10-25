import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firebase_storage_service.dart';

void main() {
  group('FirebaseStorageService validation', () {
    late Directory tempDir;
    late FirebaseStorageService service;

    setUp(() {
      tempDir = Directory.systemTemp.createTempSync(
        'firebase_storage_service_test_',
      );
      service = FirebaseStorageService();
    });

    tearDown(() {
      tempDir.deleteSync(recursive: true);
    });

    test('plant image path matches the storage rules folder', () {
      expect(
        FirebaseStorageService.plantImagePath('uid123', 'abc', '.jpg'),
        'plant-identifications/uid123/abc.jpg',
      );
    });

    test('storage rules still allow the folder the app uploads to', () {
      // Drift guard: the 2026-10-24 bug was the app writing plant_images/ while
      // the rules only allowed plant-identifications/{userId}/.
      final rules = File('../firebase/storage.rules').readAsStringSync();
      expect(rules, contains('match /plant-identifications/{userId}/{imageId}'));
    });

    test('signed-out upload is refused before touching Storage', () async {
      final container = ProviderContainer(
        overrides: [currentUserIdProvider.overrideWithValue(null)],
      );
      addTearDown(container.dispose);
      final file = File('${tempDir.path}/plant.jpg')
        ..writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0, ...List.filled(64, 0)]);
      expect(
        () => container
            .read(firebaseStorageServiceProvider.notifier)
            .uploadPlantImage(file.path),
        throwsA(
          isA<FirebaseStorageServiceException>().having(
            (e) => e.message,
            'message',
            contains('Sign in'),
          ),
        ),
      );
    });

    test('rejects unsupported file extensions before upload', () async {
      final file = File('${tempDir.path}/plant.txt')
        ..writeAsStringSync('not an image');

      expect(
        () => service.uploadPlantImage(file.path),
        throwsA(
          isA<FirebaseStorageServiceException>().having(
            (error) => error.message,
            'message',
            contains('Unsupported image type'),
          ),
        ),
      );
    });

    test('rejects oversized image files before upload', () async {
      final file = File('${tempDir.path}/plant.jpg')
        ..writeAsBytesSync([
          0xFF,
          0xD8,
          0xFF,
          ...List<int>.filled(FirebaseStorageService.maxImageBytes + 1, 0),
        ]);

      expect(
        () => service.uploadPlantImage(file.path),
        throwsA(
          isA<FirebaseStorageServiceException>().having(
            (error) => error.message,
            'message',
            contains('5 MB or smaller'),
          ),
        ),
      );
    });

    test(
      'rejects files whose content does not match image extension',
      () async {
        final file = File('${tempDir.path}/plant.png')
          ..writeAsStringSync('not really a png');

        expect(
          () => service.uploadPlantImage(file.path),
          throwsA(
            isA<FirebaseStorageServiceException>().having(
              (error) => error.message,
              'message',
              contains('content does not match'),
            ),
          ),
        );
      },
    );
  });
}
