import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/scan_camera.dart';

void main() {
  const viewport = Size(400, 800);
  const aspect = 3 / 4; // portrait preview, wider than the 1:2 viewport

  test('coverSize fills the viewport and overflows one axis', () {
    expect(coverSize(viewport, aspect), const Size(600, 800));
    expect(
      coverSize(const Size(800, 600), aspect),
      const Size(800, 800 / 0.75),
    );
  });

  test('a centre tap focuses the centre of the preview', () {
    expect(
      focusPointFor(const Offset(200, 400), viewport, aspect),
      const Offset(0.5, 0.5),
    );
  });

  test('a tap at a cropped edge maps inside the image, not to its edge', () {
    // 100 px of preview are cropped off each side.
    final left = focusPointFor(const Offset(0, 400), viewport, aspect);
    expect(left.dx, closeTo(100 / 600, 1e-9));
    expect(left.dy, 0.5);
    final right = focusPointFor(const Offset(400, 0), viewport, aspect);
    expect(right.dx, closeTo(500 / 600, 1e-9));
    expect(right.dy, 0);
  });

  test('degenerate inputs stay in range', () {
    expect(
      focusPointFor(Offset.zero, Size.zero, aspect),
      const Offset(0.5, 0.5),
    );
    final p = focusPointFor(const Offset(-50, 900), viewport, 0);
    expect(p.dx, inInclusiveRange(0, 1));
    expect(p.dy, inInclusiveRange(0, 1));
  });
}
