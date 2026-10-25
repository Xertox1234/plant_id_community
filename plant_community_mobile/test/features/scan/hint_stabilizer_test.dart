import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/frame_quality.dart';
import 'package:plant_community_mobile/features/scan/hint_stabilizer.dart';

void main() {
  test('holds a hint before switching and flags the lock once', () {
    var now = DateTime(2026, 1, 1);
    final t0 = now;
    final s = HintStabilizer(clock: () => now);
    void at(int ms) => now = t0.add(Duration(milliseconds: ms));

    at(0);
    expect(s.push(FrameHint.moveCloser), isNull);
    at(450);
    expect(s.push(FrameHint.moveCloser), FrameHint.moveCloser);
    expect(s.justLocked, isFalse);

    at(500);
    expect(s.push(FrameHint.good), FrameHint.moveCloser);
    at(700);
    expect(s.push(FrameHint.good), FrameHint.moveCloser);
    at(820);
    expect(s.push(FrameHint.good), FrameHint.good);
    expect(s.justLocked, isTrue);
    at(900);
    expect(s.push(FrameHint.good), FrameHint.good);
    expect(s.justLocked, isFalse);
  });

  test('a flicker back to the displayed hint resets the pending one', () {
    var now = DateTime(2026, 1, 1);
    final t0 = now;
    final s = HintStabilizer(clock: () => now);
    void at(int ms) => now = t0.add(Duration(milliseconds: ms));

    at(0);
    s.push(FrameHint.holdSteady);
    at(450);
    expect(s.push(FrameHint.holdSteady), FrameHint.holdSteady);
    at(500);
    s.push(FrameHint.tooDark);
    at(600);
    s.push(FrameHint.holdSteady);
    at(900);
    expect(s.push(FrameHint.tooDark), FrameHint.holdSteady);
  });
}
