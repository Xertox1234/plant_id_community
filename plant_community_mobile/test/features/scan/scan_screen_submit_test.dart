import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_camera.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/features/scan/scan_screen.dart';
import 'package:plant_community_mobile/features/scan/widgets/submit_overlay.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import 'fake_scan_camera.dart';
import 'fake_scan_job_tracker.dart';

ScanAllowance _allowance({
  bool isPremium = false,
  int diagnoseLimit = 1,
  int premiumDiagnoseLimit = 3,
}) => ScanAllowance(
  isPremium: isPremium,
  diagnoseRemaining: 0,
  diagnoseLimit: diagnoseLimit,
  identifyRemaining: 0,
  identifyLimit: 5,
  resetsAt: DateTime.utc(2026, 11, 3),
  plantIdAvailable: true,
  slowAfterSeconds: 45,
  premiumDiagnoseLimit: premiumDiagnoseLimit,
);

void main() {
  late FakeScanCamera fake;
  late FakeScanJobTracker tracker;
  late GoRouter router;

  setUp(() {
    fake = FakeScanCamera()..nextPicturePath = 'p.jpg';
  });

  Future<void> pump(
    WidgetTester tester, {
    ScanTrackerState state = const ScanTrackerState(),
    ScanAllowance? allowance,
    ScanMode initialMode = ScanMode.diagnose,
  }) async {
    tracker = FakeScanJobTracker(state);
    // The camera is pushed over a page, so closing it has somewhere to go.
    router = GoRouter(
      initialLocation: '/camera',
      routes: [
        GoRoute(
          path: '/',
          builder: (_, _) => const Text('home-page'),
          routes: [
            GoRoute(
              path: 'camera',
              builder: (_, _) => ScanScreen(initialMode: initialMode),
            ),
          ],
        ),
        GoRoute(
          path: '/scans/:id',
          builder: (_, s) => Text('scan-${s.pathParameters['id']}'),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          scanCameraFactoryProvider.overrideWithValue(() => fake),
          scanJobTrackerProvider.overrideWith(() => tracker),
          scanAllowanceProvider.overrideWith((ref) async => allowance),
        ],
        child: MaterialApp.router(
          theme: AppTheme.build(Brightness.light, AppDensity.cozy),
          routerConfig: router,
        ),
      ),
    );
    // A running job's indeterminate bar never settles.
    if (state.phase == TrackerPhase.idle || state.phase == TrackerPhase.ready) {
      await tester.pumpAndSettle();
    } else {
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
    }
  }

  Future<void> shoot(WidgetTester tester) async {
    await tester.tap(find.byKey(ScanScreen.shutterKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
  }

  Future<void> shootAndDone(WidgetTester tester) async {
    await shoot(tester);
    // Done straight from the second step: one shot is enough.
    expect(find.text('Now the whole leaf'), findsOneWidget);
    await tester.tap(find.byKey(ScanScreen.doneKey));
    await tester.pump();
  }

  /// Lets the refusal's awaits run, then the SnackBar animation.
  Future<void> settle(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
  }

  LinearProgressIndicator bar(WidgetTester tester) =>
      tester.widget(find.byKey(const Key('scan-submit-progress')));

  testWidgets('locks portrait on mount and restores on unmount', (
    tester,
  ) async {
    final calls = <List<dynamic>>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'SystemChrome.setPreferredOrientations') {
          calls.add(call.arguments as List<dynamic>);
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    await pump(tester);
    expect(calls.last, ['DeviceOrientation.portraitUp']);

    await tester.pumpWidget(const SizedBox());
    expect(calls.last, isEmpty);
  });

  testWidgets('Done uploads every shot then closes the camera', (tester) async {
    await pump(tester);
    tracker.submitGate = Completer<void>();
    await shoot(tester);
    await shoot(tester);
    await tester.tap(find.byKey(ScanScreen.doneKey));
    await tester.pump();

    expect(tracker.submitted, hasLength(1));
    expect(tracker.submitted.single.mode, ScanMode.diagnose);
    expect(tracker.submitted.single.shots.keys, [
      CaptureRole.problem,
      CaptureRole.leaf,
    ]);

    // The overlay follows the tracker's upload progress.
    expect(find.text(SubmitOverlay.copy), findsOneWidget);
    expect(bar(tester).value, isNull);
    tracker.emit(
      ScanTrackerState(
        phase: TrackerPhase.uploading,
        uploadProgress: 0.4,
        lastCapture: tracker.submitted.single,
      ),
    );
    await tester.pump();
    expect(bar(tester).value, 0.4);

    // The overlay blocks the controls underneath.
    await tester.tap(find.byKey(ScanScreen.shutterKey), warnIfMissed: false);
    expect(fake.takePictureCalls, 2);

    tracker.submitGate!.complete();
    await tester.pumpAndSettle();
    expect(find.byType(ScanScreen), findsNothing);
    expect(find.text('home-page'), findsOneWidget);
  });

  testWidgets('the camera is torn down while submitting', (tester) async {
    fake.hasFlash = true;
    await pump(tester);
    tracker.submitGate = Completer<void>();
    await tester.tap(find.byKey(ScanScreen.torchKey));
    await tester.pump();
    expect(fake.torchOn, isTrue);
    expect(fake.isStreaming, isTrue);

    await shootAndDone(tester);
    await tester.pump();
    expect(find.text(SubmitOverlay.copy), findsOneWidget);
    expect(fake.isStreaming, isFalse);
    expect(fake.torchOn, isFalse);
    expect(fake.disposeCalls, 1);

    // A resume mid-submit must not bring the camera back under the overlay.
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(fake.initializeCalls, 1);
    expect(fake.isStreaming, isFalse);

    tracker.submitGate!.complete();
    await tester.pumpAndSettle();
    expect(find.byType(ScanScreen), findsNothing);
  });

  testWidgets('allowance exhausted shows the free copy and keeps the camera', (
    tester,
  ) async {
    await pump(tester, allowance: _allowance());
    tracker.submitError = const ScanRefused(
      code: 'allowance_exhausted',
      kind: 'diagnose',
    );
    await shootAndDone(tester);
    await settle(tester);

    expect(
      find.text('No checks left today · Go premium for 3'),
      findsOneWidget,
    );
    expect(find.byType(ScanScreen), findsOneWidget);
    expect(find.text(SubmitOverlay.copy), findsNothing);
    // The shots are kept and the camera is back.
    expect(find.byKey(const ValueKey('tray-problem')), findsOneWidget);
    await tester.pumpAndSettle();
    expect(fake.initializeCalls, 2);
    expect(find.byKey(const Key('fake-preview')), findsOneWidget);
  });

  testWidgets('the free copy takes the premium limit from the allowance', (
    tester,
  ) async {
    await pump(tester, allowance: _allowance(premiumDiagnoseLimit: 7));
    tracker.submitError = const ScanRefused(
      code: 'allowance_exhausted',
      kind: 'diagnose',
    );
    await shootAndDone(tester);
    await settle(tester);
    expect(
      find.text('No checks left today · Go premium for 7'),
      findsOneWidget,
    );
  });

  testWidgets('allowance exhausted for premium names the daily limit', (
    tester,
  ) async {
    final allowance = _allowance(isPremium: true, diagnoseLimit: 4);
    await pump(tester, allowance: allowance);
    tracker.submitError = const ScanRefused(
      code: 'allowance_exhausted',
      kind: 'diagnose',
    );
    await shootAndDone(tester);
    await settle(tester);
    // Rolling 24h window (scan-2 audit M1): the time, not "midnight".
    expect(
      find.text(
        "You've used today's 4 checks. More at ${allowance.resetsAtLabel}.",
      ),
      findsOneWidget,
    );
  });

  testWidgets('allowance exhausted without an allowance is generic', (
    tester,
  ) async {
    await pump(tester);
    tracker.submitError = const ScanRefused(
      code: 'allowance_exhausted',
      kind: 'diagnose',
    );
    await shootAndDone(tester);
    await settle(tester);
    expect(find.text('No checks left today'), findsOneWidget);
  });

  testWidgets('identify allowance exhausted', (tester) async {
    await pump(tester, allowance: _allowance(), initialMode: ScanMode.identify);
    tracker.submitError = const ScanRefused(
      code: 'allowance_exhausted',
      kind: 'identify',
    );
    await shoot(tester);
    await tester.tap(find.byKey(ScanScreen.doneKey));
    await settle(tester);
    expect(find.text('No identifies left today'), findsOneWidget);
    expect(find.byType(ScanScreen), findsOneWidget);
  });

  testWidgets('plant_id_busy shows the busy copy', (tester) async {
    await pump(tester, allowance: _allowance());
    tracker.submitError = const ScanRefused(code: 'plant_id_busy');
    await shootAndDone(tester);
    await settle(tester);
    expect(
      find.text('Plant checks are busy right now, try again later'),
      findsOneWidget,
    );
    expect(find.byType(ScanScreen), findsOneWidget);
  });

  testWidgets('scan_in_progress switches to the status view, no SnackBar', (
    tester,
  ) async {
    await pump(tester);
    tracker.submitError = const ScanRefused(code: 'scan_in_progress');
    await shootAndDone(tester);
    await settle(tester);
    expect(find.byType(SnackBar), findsNothing);
    expect(find.byKey(ScanScreen.statusViewKey), findsOneWidget);
    expect(find.byKey(ScanScreen.shutterKey), findsNothing);
    expect(find.byKey(const Key('fake-preview')), findsNothing);
  });

  testWidgets('a scan already running switches to the status view (L12)', (
    tester,
  ) async {
    await pump(tester);
    tracker.submitError = ScanAlreadyRunning();
    await shootAndDone(tester);
    await settle(tester);
    expect(find.byType(SnackBar), findsNothing);
    expect(find.byKey(ScanScreen.statusViewKey), findsOneWidget);
  });

  testWidgets('any other StateError is a failure, not a running scan (L12)', (
    tester,
  ) async {
    await pump(tester);
    tracker.submitError = StateError('something else broke');
    await shootAndDone(tester);
    await settle(tester);
    expect(find.byKey(ScanScreen.statusViewKey), findsNothing);
    expect(find.text("Couldn't start the check. Try again."), findsOneWidget);
  });

  testWidgets('another failure shows a SnackBar and keeps the shots', (
    tester,
  ) async {
    await pump(tester);
    tracker.submitError = ApiException('The server is down.');
    await shootAndDone(tester);
    await settle(tester);

    expect(find.text('The server is down.'), findsOneWidget);
    expect(find.text(SubmitOverlay.copy), findsNothing);
    expect(find.byKey(const ValueKey('tray-problem')), findsOneWidget);
    expect(find.byKey(ScanScreen.doneKey), findsOneWidget);
    await tester.pumpAndSettle();
    expect(fake.initializeCalls, 2);
  });

  testWidgets(
    'opening the camera while a job is waiting shows the status view, not the camera',
    (tester) async {
      await pump(
        tester,
        state: ScanTrackerState(
          phase: TrackerPhase.waiting,
          job: fakeScanJob(),
          lastCapture: fakeCapture,
        ),
      );
      expect(fake.initializeCalls, 0);
      expect(find.byKey(ScanScreen.statusViewKey), findsOneWidget);
      expect(find.text('Checking your plant…'), findsOneWidget);
      expect(find.byKey(ScanScreen.shutterKey), findsNothing);

      // A resume does not start the camera behind the status view.
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(fake.initializeCalls, 0);

      // Close leaves the screen.
      await tester.tap(find.byKey(ScanScreen.closeKey));
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(ScanScreen), findsNothing);
    },
  );

  testWidgets('the status view follows the job and cancels it', (tester) async {
    await pump(
      tester,
      state: ScanTrackerState(
        phase: TrackerPhase.slow,
        job: fakeScanJob(),
        lastCapture: fakeCapture,
      ),
    );
    expect(
      find.text('This scan is taking a little longer than usual.'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('scan-pill-cancel')));
    await tester.pumpAndSettle();
    expect(tracker.calls, ['cancel']);
    // Nothing is running any more: the camera starts.
    expect(find.byKey(ScanScreen.statusViewKey), findsNothing);
    expect(fake.initializeCalls, 1);
    expect(find.byKey(ScanScreen.shutterKey), findsOneWidget);
  });

  testWidgets('a ready job opens the camera, not the status view', (
    tester,
  ) async {
    await pump(
      tester,
      state: ScanTrackerState(
        phase: TrackerPhase.ready,
        job: fakeScanJob(status: ScanJobStatus.done),
      ),
    );
    expect(find.byKey(ScanScreen.statusViewKey), findsNothing);
    expect(fake.initializeCalls, 1);
  });

  testWidgets('status view → View replaces the camera with the result', (
    tester,
  ) async {
    await pump(
      tester,
      state: ScanTrackerState(
        phase: TrackerPhase.waiting,
        job: fakeScanJob(),
        lastCapture: fakeCapture,
      ),
    );
    expect(find.byKey(ScanScreen.statusViewKey), findsOneWidget);

    tracker.emit(
      ScanTrackerState(
        phase: TrackerPhase.ready,
        job: fakeScanJob(status: ScanJobStatus.done),
        lastCapture: fakeCapture,
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('scan-pill-view')));
    await tester.pumpAndSettle();

    expect(find.text('scan-job-1'), findsOneWidget);
    expect(find.byType(ScanScreen, skipOffstage: false), findsNothing);
    // The result screen marks it viewed once loaded; the camera does not
    // drop the job first.
    expect(tracker.calls, isNot(contains('dismiss')));
    // Replaced, not pushed: back goes home, not to the camera.
    router.pop();
    await tester.pumpAndSettle();
    expect(find.text('home-page'), findsOneWidget);
  });

  testWidgets('status view → ready × dismisses and starts the camera', (
    tester,
  ) async {
    await pump(
      tester,
      state: ScanTrackerState(
        phase: TrackerPhase.waiting,
        job: fakeScanJob(),
        lastCapture: fakeCapture,
      ),
    );
    tracker.emit(
      ScanTrackerState(
        phase: TrackerPhase.ready,
        job: fakeScanJob(status: ScanJobStatus.done),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('scan-pill-dismiss')));
    await tester.pumpAndSettle();
    expect(tracker.calls, ['dismiss']);
    expect(find.byKey(ScanScreen.statusViewKey), findsNothing);
    expect(find.byKey(ScanScreen.shutterKey), findsOneWidget);
  });
}
