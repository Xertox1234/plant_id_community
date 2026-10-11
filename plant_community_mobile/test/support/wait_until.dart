import 'package:flutter_test/flutter_test.dart';

/// Polls until [done] holds, and fails naming [what] after about two seconds
/// instead of hanging until the suite timeout when a regression stops a
/// request from arriving (todo 498). Shared by the auth and API suites
/// (todo 500), which used to hand-roll the same loop.
Future<void> waitUntil(bool Function() done, String what) async {
  for (var poll = 0; poll < 400; poll++) {
    if (done()) return;
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
  fail('Timed out waiting for $what');
}
