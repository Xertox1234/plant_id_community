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

  testWidgets('a card disposed before the highlight ends still reports done '
      '(audit F22), so it is not replayed when built again', (tester) async {
    var done = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: LiveFlash(onDone: () => done++, child: const Text('x')),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    // Scrolled past the cache extent: the card's State is disposed.
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
    await tester.pump();

    expect(done, 1);
    await tester.pump(const Duration(seconds: 3));
    expect(done, 1);
  });
}
