import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/frame_quality.dart';

FrameSample sample({
  required int luma,
  int cb = 128,
  int cr = 128,
  bool checker = false,
}) {
  const w = 64;
  const h = 48;
  final y = Uint8List(w * h);
  for (var r = 0; r < h; r++) {
    for (var c = 0; c < w; c++) {
      final delta = checker ? (((r + c) & 1) == 0 ? 20 : -20) : 0;
      y[r * w + c] = (luma + delta).clamp(0, 255);
    }
  }
  return FrameSample(
    gridW: w,
    gridH: h,
    luma: y,
    cb: Uint8List(w * h)..fillRange(0, w * h, cb),
    cr: Uint8List(w * h)..fillRange(0, w * h, cr),
  );
}

void main() {
  test('dark frame is tooDark', () {
    expect(
      assessFrame(sample(luma: 30, checker: true), null, CaptureRole.leaf),
      FrameHint.tooDark,
    );
  });

  test('flat (blurry) frame is holdSteady', () {
    expect(
      assessFrame(sample(luma: 128), null, CaptureRole.leaf),
      FrameHint.holdSteady,
    );
  });

  test('large luma shift vs previous is holdSteady', () {
    expect(
      assessFrame(
        sample(luma: 128, checker: true),
        sample(luma: 168, checker: true),
        CaptureRole.leaf,
      ),
      FrameHint.holdSteady,
    );
  });

  test('sharp grey frame is moveCloser for leaf', () {
    expect(
      assessFrame(sample(luma: 128, checker: true), null, CaptureRole.leaf),
      FrameHint.moveCloser,
    );
  });

  test('sharp green frame is good for leaf', () {
    expect(
      assessFrame(
        sample(luma: 128, cb: 100, cr: 110, checker: true),
        null,
        CaptureRole.leaf,
      ),
      FrameHint.good,
    );
  });

  test('yellow-brown counts for problem but not leaf', () {
    final s = sample(luma: 128, cb: 90, cr: 145, checker: true);
    expect(assessFrame(s, null, CaptureRole.problem), FrameHint.good);
    expect(assessFrame(s, null, CaptureRole.leaf), FrameHint.moveCloser);
  });

  test('flower skips the coverage check', () {
    expect(
      assessFrame(sample(luma: 128, checker: true), null, CaptureRole.flower),
      FrameHint.good,
    );
  });
}
