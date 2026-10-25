import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/frame_quality.dart';
import 'package:plant_community_mobile/features/scan/hint_stabilizer.dart';
import 'package:plant_community_mobile/features/scan/scan_camera.dart';
import 'package:plant_community_mobile/features/scan/scan_screen.dart';
import 'package:plant_community_mobile/features/scan/widgets/viewfinder_frame.dart';

import 'fake_scan_camera.dart';

FrameSample _sample({
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

final _greenSharp = _sample(luma: 128, cb: 100, cr: 110, checker: true);
final _dark = _sample(luma: 30, checker: true);

void main() {
  late FakeScanCamera fake;
  late DateTime fakeNow;
  late int factoryCalls;
  CaptureResult? done;

  setUp(() {
    fake = FakeScanCamera();
    fakeNow = DateTime(2026, 10, 24, 12);
    factoryCalls = 0;
    done = null;
  });

  Future<void> pumpScreen(
    WidgetTester tester, {
    Brightness brightness = Brightness.light,
  }) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          scanCameraFactoryProvider.overrideWithValue(() {
            factoryCalls++;
            return fake;
          }),
          hintClockProvider.overrideWithValue(() => fakeNow),
        ],
        child: MaterialApp(
          theme: AppTheme.build(brightness, AppDensity.cozy),
          home: ScanScreen(onDone: (r) => done = r),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> advance(WidgetTester tester, Duration d) async {
    fakeNow = fakeNow.add(d);
    await tester.pump(d);
  }

  Future<void> tapAndSettle(WidgetTester tester, Finder f) async {
    await tester.tap(f);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
  }

  Finder viewfinder({required bool locked}) =>
      find.byWidgetPredicate((w) => w is ViewfinderFrame && w.locked == locked);

  void expectDoneEnabled(WidgetTester tester, bool enabled) => expect(
    tester.getSemantics(find.byKey(ScanScreen.doneKey)),
    isSemantics(hasEnabledState: true, isEnabled: enabled),
  );

  testWidgets('initial render: problem step, preview, no Skip, Done off', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await pumpScreen(tester);

    expect(find.text("Show me what's wrong"), findsOneWidget);
    expect(find.text('Point at the problem'), findsOneWidget);
    expect(find.byKey(const Key('fake-preview')), findsOneWidget);
    expect(find.byKey(ScanScreen.skipKey), findsNothing);
    expect(find.byKey(ScanScreen.doneKey), findsOneWidget);
    expectDoneEnabled(tester, false);
    expect(fake.isStreaming, isTrue);
    handle.dispose();
  });

  testWidgets('shutter fills the problem slot and moves to the leaf step', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    fake.nextPicturePath = 'p.jpg';
    await pumpScreen(tester);

    await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));

    expect(fake.takePictureCalls, 1);
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('tray-problem')),
        matching: find.byKey(const ValueKey('tray-check')),
      ),
      findsOneWidget,
    );
    expect(find.text('Now the whole leaf'), findsOneWidget);
    expect(find.byKey(ScanScreen.skipKey), findsOneWidget);
    expect(find.byKey(ScanScreen.doneKey), findsNothing);
    handle.dispose();
  });

  testWidgets('Done appears enabled on a retaken required step', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    fake.nextPicturePath = 'p.jpg';
    await pumpScreen(tester);
    await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));
    // Back on the required step with its shot still in place: Done, enabled.
    await tapAndSettle(tester, find.byKey(const ValueKey('step-chip-problem')));
    expect(find.byKey(ScanScreen.skipKey), findsNothing);
    expectDoneEnabled(tester, true);
    handle.dispose();
  });

  testWidgets('Skip on leaf goes to Whole plant', (tester) async {
    fake.nextPicturePath = 'p.jpg';
    await pumpScreen(tester);
    await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));
    await tapAndSettle(tester, find.byKey(ScanScreen.skipKey));
    expect(find.text('Whole plant'), findsOneWidget);
  });

  testWidgets('mode chip switches to identify and back', (tester) async {
    await pumpScreen(tester);
    expect(find.text('Just identify it'), findsOneWidget);

    await tapAndSettle(tester, find.byKey(ScanScreen.modeChipKey));
    expect(find.text('Point at a leaf'), findsOneWidget);
    expect(find.byKey(const ValueKey('step-chip-problem')), findsNothing);
    expect(find.byKey(const ValueKey('step-chip-leaf')), findsOneWidget);
    expect(find.text("Something's wrong?"), findsOneWidget);

    await tapAndSettle(tester, find.byKey(ScanScreen.modeChipKey));
    expect(find.text("Show me what's wrong"), findsOneWidget);
    expect(find.byKey(const ValueKey('step-chip-problem')), findsOneWidget);
  });

  testWidgets('a held green sharp frame locks the viewfinder with one haptic', (
    tester,
  ) async {
    final haptics = <MethodCall>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'HapticFeedback.vibrate') haptics.add(call);
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    await pumpScreen(tester);
    expect(viewfinder(locked: false), findsOneWidget);

    fake.emit(_greenSharp);
    await advance(tester, const Duration(milliseconds: 400));
    fake.emit(_greenSharp);
    await tester.pump(const Duration(milliseconds: 300));

    expect(viewfinder(locked: true), findsOneWidget);
    // Still locked on the next frame: no second haptic.
    fake.emit(_greenSharp);
    await advance(tester, const Duration(milliseconds: 200));

    expect(haptics, hasLength(1));
    expect(haptics.single.arguments, 'HapticFeedbackType.selectionClick');
  });

  for (final reduceMotion in [false, true]) {
    testWidgets(
      'lock snap ${reduceMotion ? 'jumps to its end state with '
                'reduce motion' : 'animates from slightly large'}',
      (tester) async {
        if (reduceMotion) {
          tester.platformDispatcher.accessibilityFeaturesTestValue =
              const FakeAccessibilityFeatures(disableAnimations: true);
          addTearDown(
            tester.platformDispatcher.clearAccessibilityFeaturesTestValue,
          );
        }
        await pumpScreen(tester);
        fake.emit(_greenSharp);
        await advance(tester, const Duration(milliseconds: 400));
        fake.emit(_greenSharp);
        await tester.pump();

        expect(viewfinder(locked: true), findsOneWidget);
        final scale = tester
            .widget<ScaleTransition>(
              find.descendant(
                of: find.byType(ViewfinderFrame),
                matching: find.byType(ScaleTransition),
              ),
            )
            .scale
            .value;
        expect(scale, reduceMotion ? 1.0 : greaterThan(1.0));
        await tester.pump(const Duration(milliseconds: 300));
      },
    );
  }

  testWidgets('a dark frame held for 450 ms shows the torch hint', (
    tester,
  ) async {
    await pumpScreen(tester);
    fake.emit(_dark);
    await advance(tester, const Duration(milliseconds: 450));
    fake.emit(_dark);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Too dark, tap ⚡'), findsOneWidget);
  });

  testWidgets('a step change resets the hint to the step prompt', (
    tester,
  ) async {
    fake.nextPicturePath = 'p.jpg';
    await pumpScreen(tester);
    fake.emit(_dark);
    await advance(tester, const Duration(milliseconds: 450));
    fake.emit(_dark);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Too dark, tap ⚡'), findsOneWidget);

    await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));
    expect(find.text('Too dark, tap ⚡'), findsNothing);
  });

  group('camera errors', () {
    testWidgets('denied shows the copy and Open Settings', (tester) async {
      fake.failWith = ScanCameraError.denied;
      await pumpScreen(tester);
      expect(
        find.text(
          'Camera access is off. Houseplant MD needs the camera to check '
          'your plant.',
        ),
        findsOneWidget,
      );
      expect(find.text('Open Settings'), findsOneWidget);
      expect(find.byKey(ScanScreen.closeKey), findsOneWidget);
      expect(find.byKey(const Key('fake-preview')), findsNothing);
    });

    testWidgets('restricted shows the copy without a button', (tester) async {
      fake.failWith = ScanCameraError.restricted;
      await pumpScreen(tester);
      expect(
        find.text(
          'Camera access is off. Houseplant MD needs the camera to check '
          'your plant.',
        ),
        findsOneWidget,
      );
      expect(find.text('Open Settings'), findsNothing);
      expect(find.text('Choose from photos'), findsNothing);
      expect(find.byKey(ScanScreen.closeKey), findsOneWidget);
    });

    testWidgets('unavailable offers Choose from photos', (tester) async {
      fake.failWith = ScanCameraError.unavailable;
      await pumpScreen(tester);
      expect(
        find.text("Camera isn't available on this device."),
        findsOneWidget,
      );
      expect(find.text('Choose from photos'), findsOneWidget);
      expect(find.byKey(ScanScreen.closeKey), findsOneWidget);
    });
  });

  testWidgets('no flash hides the torch; flash shows it and toggles', (
    tester,
  ) async {
    await pumpScreen(tester);
    expect(find.byKey(ScanScreen.torchKey), findsNothing);
  });

  testWidgets('torch toggles when the device has a flash', (tester) async {
    fake.hasFlash = true;
    await pumpScreen(tester);
    await tapAndSettle(tester, find.byKey(ScanScreen.torchKey));
    expect(fake.torchOn, isTrue);
    await tapAndSettle(tester, find.byKey(ScanScreen.torchKey));
    expect(fake.torchOn, isFalse);
  });

  testWidgets('pinch with no zoom range throws nothing', (tester) async {
    await pumpScreen(tester);
    final center = tester.getCenter(find.byKey(const Key('fake-preview')));
    final a = await tester.startGesture(center - const Offset(20, 0));
    final b = await tester.startGesture(center + const Offset(20, 0));
    await tester.pump();
    await a.moveBy(const Offset(-60, 0));
    await b.moveBy(const Offset(60, 0));
    await tester.pump();
    await a.up();
    await b.up();
    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(fake.zoom, 1);
  });

  testWidgets('pinch zooms when there is a zoom range', (tester) async {
    fake.maxZoom = 4;
    await pumpScreen(tester);
    final center = tester.getCenter(find.byKey(const Key('fake-preview')));
    final a = await tester.startGesture(center - const Offset(20, 0));
    final b = await tester.startGesture(center + const Offset(20, 0));
    await tester.pump();
    await a.moveBy(const Offset(-40, 0));
    await b.moveBy(const Offset(40, 0));
    await tester.pump();
    await a.up();
    await b.up();
    await tester.pump();
    expect(fake.zoom, greaterThan(1));
  });

  testWidgets('tap on the preview sets a normalized focus point', (
    tester,
  ) async {
    await pumpScreen(tester);
    await tester.tapAt(const Offset(400, 300));
    await tester.pump();
    final p = fake.lastFocusPoint;
    expect(p, isNotNull);
    expect(p!.dx, inInclusiveRange(0, 1));
    expect(p.dy, inInclusiveRange(0, 1));
  });

  testWidgets('background and resume keeps the session and rebuilds once', (
    tester,
  ) async {
    fake.nextPicturePath = 'p.jpg';
    await pumpScreen(tester);
    await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    expect(fake.disposeCalls, 1);
    expect(fake.isStreaming, isFalse);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();

    expect(fake.disposeCalls, 1);
    expect(factoryCalls, 2);
    expect(fake.initializeCalls, 2);
    expect(fake.isStreaming, isTrue);
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('tray-problem')),
        matching: find.byKey(const ValueKey('tray-check')),
      ),
      findsOneWidget,
    );
    expect(find.text('Now the whole leaf'), findsOneWidget);
  });

  testWidgets('Done after only the problem shot hands back that shot', (
    tester,
  ) async {
    fake.nextPicturePath = 'p.jpg';
    await pumpScreen(tester);
    await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));
    // Skip to the last step, where Done replaces Skip.
    await tapAndSettle(tester, find.byKey(ScanScreen.skipKey));
    await tapAndSettle(tester, find.byKey(ScanScreen.skipKey));
    await tapAndSettle(tester, find.byKey(ScanScreen.doneKey));

    expect(done, isNotNull);
    expect(done!.mode, ScanMode.diagnose);
    expect(done!.shots, equals({CaptureRole.problem: 'p.jpg'}));
  });

  for (final brightness in Brightness.values) {
    for (final size in const [Size(320, 640), Size(375, 812)]) {
      testWidgets('no overflow at 200% text, ${brightness.name}, '
          '${size.width.toInt()}w', (tester) async {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = 2;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        fake
          ..hasFlash = true
          ..nextPicturePath = 'p.jpg';
        await pumpScreen(tester, brightness: brightness);
        expect(tester.takeException(), isNull);
        await tapAndSettle(tester, find.byKey(ScanScreen.shutterKey));
        expect(tester.takeException(), isNull);
        expect(find.byKey(ScanScreen.skipKey), findsOneWidget);
        // The longest title, on the last step.
        await tapAndSettle(tester, find.byKey(ScanScreen.skipKey));
        await tapAndSettle(tester, find.byKey(ScanScreen.skipKey));
        expect(find.text('A flower, if it has one'), findsOneWidget);
        expect(tester.takeException(), isNull);
        // Identify mode swaps in the longer mode chip label.
        await tapAndSettle(tester, find.byKey(ScanScreen.modeChipKey));
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets('controls meet tap-target guidelines', (tester) async {
    final handle = tester.ensureSemantics();
    fake.hasFlash = true;
    await pumpScreen(tester);
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    handle.dispose();
  });
}
