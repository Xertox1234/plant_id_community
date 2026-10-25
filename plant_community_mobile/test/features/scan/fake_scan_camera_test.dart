import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/frame_quality.dart';
import 'package:plant_community_mobile/features/scan/scan_camera.dart';

import 'fake_scan_camera.dart';

FrameSample _sample() => FrameSample(
  gridW: 1,
  gridH: 1,
  luma: Uint8List.fromList([1]),
  cb: Uint8List.fromList([128]),
  cr: Uint8List.fromList([128]),
);

void main() {
  test('failWith makes initialize throw that error', () async {
    final cam = FakeScanCamera()..failWith = ScanCameraError.denied;
    await expectLater(
      cam.initialize(),
      throwsA(
        isA<ScanCameraException>().having(
          (e) => e.error,
          'error',
          ScanCameraError.denied,
        ),
      ),
    );
    expect(cam.initializeCalls, 1);
  });

  test('emit reaches the callback only while streaming', () async {
    final cam = FakeScanCamera();
    await cam.initialize();
    final got = <FrameSample>[];
    await cam.startFrames(got.add);
    expect(cam.isStreaming, isTrue);
    cam.emit(_sample());
    expect(got, hasLength(1));
    await cam.stopFrames();
    expect(cam.isStreaming, isFalse);
    cam.emit(_sample());
    expect(got, hasLength(1));
  });

  test('dispose is idempotent-safe, counts calls and stops frames', () async {
    final cam = FakeScanCamera();
    await cam.startFrames((_) {});
    await cam.dispose();
    await cam.dispose();
    expect(cam.disposeCalls, 1);
    expect(cam.isStreaming, isFalse);
  });

  test('takePicture returns nextPicturePath; zoom clamps', () async {
    final cam = FakeScanCamera()
      ..nextPicturePath = '/tmp/a.jpg'
      ..maxZoom = 4;
    expect(await cam.takePicture(), '/tmp/a.jpg');
    await cam.setZoom(10);
    expect(cam.zoom, 4);
  });
}
