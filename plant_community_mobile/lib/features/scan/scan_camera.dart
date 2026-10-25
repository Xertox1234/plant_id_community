import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/widgets.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'frame_quality.dart';

part 'scan_camera.g.dart';

enum ScanCameraError { denied, restricted, unavailable }

class ScanCameraException implements Exception {
  ScanCameraException(this.error, [this.detail]);

  final ScanCameraError error;
  final String? detail;

  @override
  String toString() => 'ScanCameraException($error, $detail)';
}

/// The guided camera's view of the device camera. Tests use a fake.
abstract interface class ScanCamera {
  /// Throws [ScanCameraException].
  Future<void> initialize();
  Widget buildPreview();
  bool get hasFlash;
  double get minZoom;
  double get maxZoom;

  /// Returns a local JPEG path.
  Future<String> takePicture();
  Future<void> setTorch(bool on);

  /// [normalized] is 0..1 in preview space.
  Future<void> setFocusPoint(Offset normalized);

  /// Clamped to [minZoom, maxZoom].
  Future<void> setZoom(double level);
  Future<void> startFrames(void Function(FrameSample sample) onSample);
  Future<void> stopFrames();

  /// Idempotent; stops the frame stream first if running.
  Future<void> dispose();
}

/// Minimum gap between delivered frame samples.
const Duration kScanFrameInterval = Duration(milliseconds: 200);

class PluginScanCamera implements ScanCamera {
  CameraController? _controller;
  bool _hasFlash = false;
  double _minZoom = 1;
  double _maxZoom = 1;
  bool _disposed = false;

  // Frame stream state.
  void Function(FrameSample sample)? _onSample;
  bool _streaming = false;
  DateTime? _lastSample;

  @override
  bool get hasFlash => _hasFlash;
  @override
  double get minZoom => _minZoom;
  @override
  double get maxZoom => _maxZoom;

  @override
  Future<void> initialize() async {
    // Re-initialising must not leak a previous controller.
    final old = _controller;
    _controller = null;
    await _safeDispose(old);
    CameraController? controller;
    try {
      final cameras = await availableCameras();
      final back = cameras
          .where((c) => c.lensDirection == CameraLensDirection.back)
          .firstOrNull;
      if (back == null) {
        throw ScanCameraException(
          ScanCameraError.unavailable,
          'No back camera',
        );
      }
      if (_disposed) {
        throw ScanCameraException(ScanCameraError.unavailable, 'disposed');
      }
      controller = CameraController(
        back,
        ResolutionPreset.veryHigh,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );
      _controller = controller;
      await controller.initialize();
      if (_disposed) {
        throw ScanCameraException(ScanCameraError.unavailable, 'disposed');
      }
      try {
        _minZoom = await controller.getMinZoomLevel();
        _maxZoom = await controller.getMaxZoomLevel();
      } catch (_) {
        _minZoom = 1.0;
        _maxZoom = 1.0;
      }
      if (_disposed) {
        throw ScanCameraException(ScanCameraError.unavailable, 'disposed');
      }
      // Never turn the torch on here; probing with `off` flashes nothing.
      // Known gap: on iOS this throws when there is no flash unit, but on
      // Android (camera_android_camerax 0.7.2) setFlashMode only stores a
      // field and never throws, so Android ALWAYS reports hasFlash = true.
      // Follow-up: ask CameraX `hasFlashUnit` through a platform channel.
      try {
        await controller.setFlashMode(FlashMode.off);
        _hasFlash = true;
      } catch (_) {
        _hasFlash = false;
      }
      if (_disposed) {
        throw ScanCameraException(ScanCameraError.unavailable, 'disposed');
      }
    } catch (e) {
      if (controller != null) {
        if (identical(_controller, controller)) _controller = null;
        await _safeDispose(controller);
      }
      if (e is ScanCameraException) rethrow;
      if (e is CameraException) {
        throw ScanCameraException(_mapCode(e.code), e.description);
      }
      throw ScanCameraException(ScanCameraError.unavailable, e.toString());
    }
  }

  static Future<void> _safeDispose(CameraController? c) async {
    if (c == null) return;
    try {
      await c.dispose();
    } catch (_) {
      // Already gone or failed to release; nothing more to do.
    }
  }

  static ScanCameraError _mapCode(String code) => switch (code) {
    'CameraAccessDenied' ||
    'CameraAccessDeniedWithoutPrompt' => ScanCameraError.denied,
    'CameraAccessRestricted' => ScanCameraError.restricted,
    _ => ScanCameraError.unavailable,
  };

  CameraController get _c {
    final c = _controller;
    if (c == null || !c.value.isInitialized) {
      throw StateError('ScanCamera is not initialized');
    }
    return c;
  }

  @override
  Widget buildPreview() => CameraPreview(_c);

  @override
  Future<String> takePicture() async {
    final controller = _c;
    final resume = _streaming;
    if (resume) await _stopStream();
    try {
      final file = await controller.takePicture();
      return file.path;
    } finally {
      if (resume && !_disposed && _onSample != null) {
        try {
          await _startStream();
        } catch (_) {
          // Capture result stands; frames stay stopped (_streaming reset).
        }
      }
    }
  }

  @override
  Future<void> setTorch(bool on) async {
    if (!_hasFlash) return;
    try {
      await _c.setFlashMode(on ? FlashMode.torch : FlashMode.off);
    } on CameraException {
      // A torch toggle never throws to the UI.
    }
  }

  @override
  Future<void> setFocusPoint(Offset normalized) async {
    final controller = _c;
    final p = Offset(
      normalized.dx.clamp(0.0, 1.0),
      normalized.dy.clamp(0.0, 1.0),
    );
    try {
      if (controller.value.focusPointSupported) {
        await controller.setFocusPoint(p);
      }
      if (controller.value.exposurePointSupported) {
        await controller.setExposurePoint(p);
      }
    } on CameraException {
      // Tap-to-focus is best effort.
    }
  }

  @override
  Future<void> setZoom(double level) async {
    if (level.isNaN || _maxZoom <= _minZoom) return;
    await _c.setZoomLevel(level.clamp(_minZoom, _maxZoom).toDouble());
  }

  @override
  Future<void> startFrames(void Function(FrameSample sample) onSample) async {
    _onSample = onSample;
    _lastSample = null;
    await _startStream();
  }

  Future<void> _startStream() async {
    final controller = _c;
    if (_streaming || controller.value.isStreamingImages) return;
    _streaming = true;
    try {
      await controller.startImageStream(_handleImage);
    } catch (_) {
      _streaming = false;
      rethrow;
    }
  }

  // Sample building is synchronous, so frames cannot overlap; the 200 ms
  // throttle is what drops the frames in between.
  void _handleImage(CameraImage image) {
    final cb = _onSample;
    if (!_streaming || cb == null) return;
    final now = DateTime.now();
    final last = _lastSample;
    if (last != null && now.difference(last) < kScanFrameInterval) return;
    _lastSample = now;
    final FrameSample sample;
    try {
      sample = FrameSample.fromCameraImage(image);
    } catch (_) {
      return; // Drop the frame.
    }
    cb(sample);
  }

  Future<void> _stopStream() async {
    _streaming = false;
    final controller = _controller;
    if (controller != null && controller.value.isStreamingImages) {
      await controller.stopImageStream();
    }
  }

  @override
  Future<void> stopFrames() async {
    _onSample = null;
    await _stopStream();
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _onSample = null;
    try {
      await _stopStream();
    } catch (_) {
      // Disposing anyway.
    }
    final c = _controller;
    _controller = null;
    await _safeDispose(c);
  }
}

/// A factory so tests can override the camera. Screens call the result.
@riverpod
ScanCamera Function() scanCameraFactory(Ref ref) => PluginScanCamera.new;
