import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/shot_files.dart';

/// Scan-2 audit L9: shot files are deleted once nothing needs them.
void main() {
  late List<String> deleted;
  late ProviderContainer container;
  late CaptureSession session;
  final provider = captureSessionProvider(ScanMode.diagnose);

  setUp(() {
    deleted = [];
    container = ProviderContainer(
      overrides: [shotFileDeleterProvider.overrideWithValue(deleted.addAll)],
    );
    container.listen(provider, (_, _) {});
    session = container.read(provider.notifier);
  });

  tearDown(() => container.dispose());

  test('a shot replaced in its step deletes the old file', () {
    session.addShot('/s/problem-1.jpg');
    session.jumpTo(CaptureRole.problem);
    session.addShot('/s/problem-2.jpg');
    expect(deleted, ['/s/problem-1.jpg']);
  });

  test('retake deletes the retaken shot', () {
    session.addShot('/s/problem.jpg');
    session.retake(CaptureRole.problem);
    expect(deleted, ['/s/problem.jpg']);
  });

  test('switching mode deletes the shots the new mode has no step for', () {
    session.addShot('/s/problem.jpg'); // diagnose only
    session.addShot('/s/leaf.jpg');
    session.setMode(ScanMode.identify);
    expect(deleted, ['/s/problem.jpg']);
  });

  test('an abandoned session deletes its shots when it is disposed', () {
    session.addShot('/s/problem.jpg');
    session.addShot('/s/leaf.jpg');
    container.dispose();
    expect(deleted, unorderedEquals(['/s/problem.jpg', '/s/leaf.jpg']));
    container = ProviderContainer(); // for tearDown
  });

  test('shots handed to a scan by finish are not deleted on dispose', () {
    session.addShot('/s/problem.jpg');
    session.finish();
    container.dispose();
    expect(deleted, isEmpty);
    container = ProviderContainer(); // for tearDown
  });

  test('deleteShotFiles removes real files and skips missing ones', () async {
    final dir = await Directory.systemTemp.createTemp('shots');
    addTearDown(() => dir.delete(recursive: true));
    final a = File('${dir.path}/a.jpg')..writeAsBytesSync([1]);
    deleteShotFiles([a.path, '${dir.path}/missing.jpg']);
    for (var i = 0; i < 50 && a.existsSync(); i++) {
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    expect(a.existsSync(), isFalse);
  });
}
