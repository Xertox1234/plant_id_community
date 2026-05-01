import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/firebase_storage_service.dart';

void main() {
  group('FirebaseStorageService validation', () {
    late Directory tempDir;
    late FirebaseStorageService service;

    setUp(() {
      tempDir = Directory.systemTemp.createTempSync('firebase_storage_service_test_');
      service = FirebaseStorageService();
    });

    tearDown(() {
      tempDir.deleteSync(recursive: true);
    });

    test('rejects unsupported file extensions before upload', () async {
      final file = File('${tempDir.path}/plant.txt')..writeAsStringSync('not an image');

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

    test('rejects files whose content does not match image extension', () async {
      final file = File('${tempDir.path}/plant.png')..writeAsStringSync('not really a png');

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
    });
  });
}