import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';

void main() {
  late ProviderContainer container;
  late CaptureSession notifier;
  CaptureSessionState read() => container.read(captureSessionProvider);

  setUp(() {
    container = ProviderContainer();
    addTearDown(container.dispose);
    container.listen(captureSessionProvider, (_, _) {});
    notifier = container.read(captureSessionProvider.notifier);
  });

  test('initial state', () {
    expect(read().mode, ScanMode.diagnose);
    expect(read().stepIndex, 0);
    expect(read().shots, isEmpty);
    expect(read().currentRole, CaptureRole.problem);
    expect(read().canFinish, isFalse);
    expect(read().isCurrentSkippable, isFalse);
    expect(read().hasShotForCurrent, isFalse);
    expect(read().isLastStep, isFalse);
  });

  test('skip on required step is a no-op', () {
    notifier.skip();
    expect(read().currentRole, CaptureRole.problem);
  });

  test('addShot stores and advances', () {
    notifier.addShot('p.jpg');
    expect(read().currentRole, CaptureRole.leaf);
    expect(read().canFinish, isTrue);
    expect(read().isCurrentSkippable, isTrue);
  });

  test(
    'skip never passes the last index; finish has only the problem shot',
    () {
      notifier.addShot('p.jpg');
      for (var i = 0; i < 3; i++) {
        notifier.skip();
      }
      expect(read().stepIndex, 3);
      expect(read().isLastStep, isTrue);
      notifier.skip();
      expect(read().stepIndex, 3);
      expect(notifier.finish().shots, {CaptureRole.problem: 'p.jpg'});
    },
  );

  test('addShot on last step stays put', () {
    notifier.addShot('p.jpg');
    notifier.jumpTo(CaptureRole.flower);
    notifier.addShot('f.jpg');
    expect(read().currentRole, CaptureRole.flower);
    expect(read().shots[CaptureRole.flower], 'f.jpg');
  });

  test('addShot advances to next step lacking a shot, never wraps', () {
    notifier.addShot('p.jpg');
    notifier.jumpTo(CaptureRole.whole);
    notifier.addShot('w.jpg');
    expect(read().currentRole, CaptureRole.flower);
    notifier.retake(CaptureRole.problem);
    notifier.addShot('p2.jpg');
    expect(read().currentRole, CaptureRole.leaf);
  });

  test('setMode identify with no shots', () {
    notifier.setMode(ScanMode.identify);
    expect(read().currentRole, CaptureRole.leaf);
    expect(read().canFinish, isFalse);
  });

  test('setMode identify keeps leaf, drops problem, resets to step 0', () {
    notifier.addShot('p.jpg');
    notifier.addShot('l.jpg');
    notifier.setMode(ScanMode.identify);
    expect(read().shots, {CaptureRole.leaf: 'l.jpg'});
    expect(read().stepIndex, 0);
    expect(read().canFinish, isTrue);
  });

  test('retake removes shot and jumps to it', () {
    notifier.addShot('p.jpg');
    notifier.addShot('l.jpg');
    notifier.retake(CaptureRole.leaf);
    expect(read().shots.containsKey(CaptureRole.leaf), isFalse);
    expect(read().currentRole, CaptureRole.leaf);
  });

  test('finish before required shot throws', () {
    expect(() => notifier.finish(), throwsStateError);
  });
}
