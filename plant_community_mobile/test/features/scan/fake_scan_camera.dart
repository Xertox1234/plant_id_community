import 'package:flutter/widgets.dart';
import 'package:plant_community_mobile/features/scan/frame_quality.dart';
import 'package:plant_community_mobile/features/scan/scan_camera.dart';

/// Test double for [ScanCamera]; drive frames with [emit].
class FakeScanCamera implements ScanCamera {
  ScanCameraError? failWith;
  @override
  bool hasFlash = false;
  @override
  double minZoom = 1;
  @override
  double maxZoom = 1;
  int initializeCalls = 0;
  int disposeCalls = 0;
  String nextPicturePath = '/tmp/fake_scan.jpg';

  bool torchOn = false;
  double zoom = 1;
  Offset? lastFocusPoint;
  int takePictureCalls = 0;

  void Function(FrameSample sample)? _onSample;
  bool _disposed = false;

  bool get isStreaming => _onSample != null;

  void emit(FrameSample s) => _onSample?.call(s);

  @override
  Future<void> initialize() async {
    initializeCalls++;
    final error = failWith;
    if (error != null) throw ScanCameraException(error, 'fake');
  }

  @override
  Widget buildPreview() =>
      const ColoredBox(key: Key('fake-preview'), color: Color(0xFF000000));

  @override
  Future<String> takePicture() async {
    takePictureCalls++;
    return nextPicturePath;
  }

  @override
  Future<void> setTorch(bool on) async => torchOn = on;

  @override
  Future<void> setFocusPoint(Offset normalized) async =>
      lastFocusPoint = normalized;

  @override
  Future<void> setZoom(double level) async =>
      zoom = level.clamp(minZoom, maxZoom).toDouble();

  @override
  Future<void> startFrames(void Function(FrameSample sample) onSample) async =>
      _onSample = onSample;

  @override
  Future<void> stopFrames() async => _onSample = null;

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    disposeCalls++;
    _onSample = null;
  }
}
