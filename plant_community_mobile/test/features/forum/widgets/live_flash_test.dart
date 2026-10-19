// LiveFlash: the live-reply highlight (forum live replies, slice 4).
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/widgets/live_flash.dart';

void main() {
  testWidgets('with the OS reduce-motion setting the highlight still lasts '
      '2.5 s', (tester) async {
    // What iOS Reduce Motion sets: AnimationControllers read it from the
    // binding and would otherwise run at 5% of their duration.
    debugSemanticsDisableAnimations = true;
    addTearDown(() => debugSemanticsDisableAnimations = null);
    var done = false;
    await tester.pumpWidget(
      MaterialApp(
        home: LiveFlash(onDone: () => done = true, child: const Text('x')),
      ),
    );

    await tester.pump(const Duration(seconds: 2));
    expect(done, isFalse);
    await tester.pump(const Duration(milliseconds: 600));
    expect(done, isTrue);
  });

  testWidgets('the highlight lasts 2.5 s', (tester) async {
    var done = false;
    await tester.pumpWidget(
      MaterialApp(
        home: LiveFlash(onDone: () => done = true, child: const Text('x')),
      ),
    );

    await tester.pump(const Duration(seconds: 2));
    expect(done, isFalse);
    await tester.pump(const Duration(milliseconds: 600));
    expect(done, isTrue);
  });
}
