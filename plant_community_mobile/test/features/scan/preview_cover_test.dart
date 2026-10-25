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

  group('landscape viewport (iPad multitasking ignores the portrait lock)', () {
    const landscape = Size(800, 600);

    test('previewAspectFor un-inverts the ratio only in landscape', () {
      expect(previewAspectFor(viewport, aspect), aspect);
      expect(previewAspectFor(landscape, aspect), closeTo(4 / 3, 1e-9));
      // Square counts as portrait; degenerate input passes through.
      expect(previewAspectFor(const Size(500, 500), aspect), aspect);
      expect(previewAspectFor(landscape, 0), 0);
    });

    test('a 4:3 landscape preview covers a 4:3 landscape screen exactly', () {
      final a = previewAspectFor(landscape, aspect);
      expect(coverSize(landscape, a), landscape);
      expect(
        focusPointFor(const Offset(400, 300), landscape, a),
        const Offset(0.5, 0.5),
      );
      final corner = focusPointFor(const Offset(800, 0), landscape, a);
      expect(corner.dx, closeTo(1, 1e-9));
      expect(corner.dy, closeTo(0, 1e-9));
    });

    test(
      'a wide landscape screen crops the landscape preview top and bottom',
      () {
        const wide = Size(1000, 600);
        final a = previewAspectFor(wide, aspect);
        expect(coverSize(wide, a), const Size(1000, 750));
        final top = focusPointFor(const Offset(500, 0), wide, a);
        expect(top.dx, closeTo(0.5, 1e-9));
        expect(top.dy, closeTo(75 / 750, 1e-9));
      },
    );
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
