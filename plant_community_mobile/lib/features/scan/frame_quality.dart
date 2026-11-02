import 'dart:typed_data';

import 'package:camera/camera.dart';

import 'capture_steps.dart';

// All thresholds below are starting values, to be tuned on a real device in
// Task 8.

/// Mean luma (0-255) below which the frame is too dark.
const int kDarkLuma = 50;

/// Mean absolute luma difference against the previous sample above which the
/// camera is considered moving.
const double kMotionDiff = 12;

/// Laplacian variance of the luma grid below which the frame is blurry.
const double kBlurVar = 60;

/// Stricter blur threshold for the `problem` step (lesions need detail).
const double kBlurVarProblem = 100;

/// Minimum fraction of subject cells for leaf / whole.
const double kCoverage = 0.25;

/// Minimum fraction of subject cells for the `problem` step.
const double kCoverageProblem = 0.35;

/// Green cell test: `cb < kGreenCb && cr < kGreenCr`.
const int kGreenCb = 118;
const int kGreenCr = 125;

/// Plant-ish cell test (problem step): chroma distance from neutral
/// (128, 128) above [kChromaMin] and `cr < kPlantCrMax`.
const double kChromaMin = 10;
const int kPlantCrMax = 150;

/// A downsampled `gridW x gridH` view of a camera frame.
class FrameSample {
  const FrameSample({
    required this.gridW,
    required this.gridH,
    required this.luma,
    required this.cb,
    required this.cr,
  });

  final int gridW;
  final int gridH;

  /// Y, 0-255, row-major.
  final Uint8List luma;

  /// Cb and Cr on the same grid, 0-255.
  final Uint8List cb;
  final Uint8List cr;

  /// Block-averages a `yuv420` [CameraImage] into a grid.
  ///
  /// Android delivers three planes (Y, U, V) whose pixel stride may be 2;
  /// iOS delivers two (Y, interleaved CbCr / NV12). Chroma is subsampled 2x2.
  factory FrameSample.fromCameraImage(
    CameraImage image, {
    int gridW = 64,
    int gridH = 48,
  }) {
    final planes = image.planes;
    if (planes.length < 2) {
      throw ArgumentError('Expected a yuv420 image with 2 or 3 planes');
    }
    final yPlane = planes[0];
    final Plane uPlane;
    final Plane? vPlane;
    if (planes.length >= 3) {
      uPlane = planes[1];
      vPlane = planes[2];
    } else {
      uPlane = planes[1];
      vPlane = null;
    }

    final width = image.width;
    final height = image.height;
    final cw = (width + 1) >> 1;
    final ch = (height + 1) >> 1;

    final yBytes = yPlane.bytes;
    final yRow = yPlane.bytesPerRow;
    final yPix = yPlane.bytesPerPixel ?? 1;

    final uBytes = uPlane.bytes;
    final uRow = uPlane.bytesPerRow;
    final uPix = uPlane.bytesPerPixel ?? (vPlane == null ? 2 : 1);
    final vBytes = vPlane?.bytes;
    final vRow = vPlane?.bytesPerRow ?? uRow;
    final vPix = vPlane?.bytesPerPixel ?? uPix;
    // Interleaved NV12: Cb at the pixel offset, Cr one byte after.
    final crOffset = vPlane == null ? 1 : 0;

    final luma = Uint8List(gridW * gridH);
    final cb = Uint8List(gridW * gridH);
    final cr = Uint8List(gridW * gridH);

    // At most 4x4 taps per cell keeps this cheap on large frames.
    for (var gy = 0; gy < gridH; gy++) {
      final y0 = gy * height ~/ gridH;
      final y1 = ((gy + 1) * height ~/ gridH).clamp(y0 + 1, height);
      final yStep = ((y1 - y0) + 3) ~/ 4;
      final c0 = gy * ch ~/ gridH;
      final c1 = ((gy + 1) * ch ~/ gridH).clamp(c0 + 1, ch);
      final cyStep = ((c1 - c0) + 3) ~/ 4;
      for (var gx = 0; gx < gridW; gx++) {
        final x0 = gx * width ~/ gridW;
        final x1 = ((gx + 1) * width ~/ gridW).clamp(x0 + 1, width);
        final xStep = ((x1 - x0) + 3) ~/ 4;
        var sum = 0;
        var n = 0;
        for (var y = y0; y < y1; y += yStep) {
          final rowBase = y * yRow;
          for (var x = x0; x < x1; x += xStep) {
            sum += yBytes[rowBase + x * yPix];
            n++;
          }
        }
        final i = gy * gridW + gx;
        luma[i] = n == 0 ? 0 : sum ~/ n;

        final cx0 = gx * cw ~/ gridW;
        final cx1 = ((gx + 1) * cw ~/ gridW).clamp(cx0 + 1, cw);
        final cxStep = ((cx1 - cx0) + 3) ~/ 4;
        var uSum = 0;
        var vSum = 0;
        var cn = 0;
        for (var y = c0; y < c1; y += cyStep) {
          for (var x = cx0; x < cx1; x += cxStep) {
            uSum += uBytes[y * uRow + x * uPix];
            vSum += vBytes != null
                ? vBytes[y * vRow + x * vPix]
                : uBytes[y * uRow + x * uPix + crOffset];
            cn++;
          }
        }
        cb[i] = cn == 0 ? 128 : uSum ~/ cn;
        cr[i] = cn == 0 ? 128 : vSum ~/ cn;
      }
    }
    return FrameSample(gridW: gridW, gridH: gridH, luma: luma, cb: cb, cr: cr);
  }
}

enum FrameHint { none, tooDark, holdSteady, moveCloser, good }

/// Judges a frame. Checks run in priority order; the first match wins.
FrameHint assessFrame(
  FrameSample current,
  FrameSample? previous,
  CaptureRole role,
) {
  final n = current.luma.length;
  if (n == 0) return FrameHint.none;

  var lumaSum = 0;
  for (var i = 0; i < n; i++) {
    lumaSum += current.luma[i];
  }
  if (lumaSum / n < kDarkLuma) return FrameHint.tooDark;

  final isProblem = role == CaptureRole.problem;

  if (previous != null && previous.luma.length == n) {
    var diff = 0;
    for (var i = 0; i < n; i++) {
      diff += (current.luma[i] - previous.luma[i]).abs();
    }
    if (diff / n > kMotionDiff) return FrameHint.holdSteady;
  }
  if (_laplacianVariance(current) < (isProblem ? kBlurVarProblem : kBlurVar)) {
    return FrameHint.holdSteady;
  }

  if (role != CaptureRole.flower) {
    var hits = 0;
    for (var i = 0; i < n; i++) {
      final b = current.cb[i];
      final r = current.cr[i];
      if (isProblem) {
        final db = b - 128;
        final dr = r - 128;
        if (db * db + dr * dr > kChromaMin * kChromaMin && r < kPlantCrMax) {
          hits++;
        }
      } else if (b < kGreenCb && r < kGreenCr) {
        hits++;
      }
    }
    if (hits / n < (isProblem ? kCoverageProblem : kCoverage)) {
      return FrameHint.moveCloser;
    }
  }
  return FrameHint.good;
}

/// Variance of the 4-neighbour Laplacian over the interior cells.
double _laplacianVariance(FrameSample s) {
  final w = s.gridW;
  final h = s.gridH;
  if (w < 3 || h < 3) return 0;
  final l = s.luma;
  var sum = 0.0;
  var sumSq = 0.0;
  var count = 0;
  for (var y = 1; y < h - 1; y++) {
    for (var x = 1; x < w - 1; x++) {
      final i = y * w + x;
      final v = (l[i - 1] + l[i + 1] + l[i - w] + l[i + w] - 4 * l[i])
          .toDouble();
      sum += v;
      sumSq += v * v;
      count++;
    }
  }
  final mean = sum / count;
  return sumSq / count - mean * mean;
}
