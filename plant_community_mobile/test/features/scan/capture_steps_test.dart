import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';

void main() {
  group('stepsFor', () {
    test('diagnose order', () {
      expect(stepsFor(ScanMode.diagnose), [
        CaptureRole.problem,
        CaptureRole.leaf,
        CaptureRole.whole,
        CaptureRole.flower,
      ]);
    });
    test('identify order has no problem', () {
      expect(stepsFor(ScanMode.identify), [
        CaptureRole.leaf,
        CaptureRole.whole,
        CaptureRole.flower,
      ]);
      expect(stepsFor(ScanMode.identify), isNot(contains(CaptureRole.problem)));
    });
  });

  test('requiredRole per mode', () {
    expect(requiredRole(ScanMode.diagnose), CaptureRole.problem);
    expect(requiredRole(ScanMode.identify), CaptureRole.leaf);
  });

  test('chip labels', () {
    expect(CaptureRole.problem.chipLabel, 'Problem');
    expect(CaptureRole.leaf.chipLabel, 'Leaf');
    expect(CaptureRole.whole.chipLabel, 'Whole');
    expect(CaptureRole.flower.chipLabel, 'Flower');
  });

  test('titles', () {
    expect(
      titleFor(CaptureRole.problem, ScanMode.diagnose),
      "Show me what's wrong",
    );
    expect(titleFor(CaptureRole.leaf, ScanMode.diagnose), 'Now the whole leaf');
    expect(titleFor(CaptureRole.whole, ScanMode.diagnose), 'Whole plant');
    expect(
      titleFor(CaptureRole.flower, ScanMode.diagnose),
      'A flower, if it has one',
    );
  });

  test('prompts', () {
    expect(
      promptFor(CaptureRole.problem, ScanMode.diagnose),
      'Point at the problem',
    );
    expect(promptFor(CaptureRole.leaf, ScanMode.identify), 'Point at a leaf');
  });
}
