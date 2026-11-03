import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/features/scan/widgets/scan_job_pill.dart';

import 'fake_scan_job_tracker.dart';

void main() {
  late FakeScanJobTracker tracker;
  late GoRouter router;

  /// Pumps the pill the way main.dart places it: in the app builder, above
  /// the router's navigator.
  Future<void> pump(
    WidgetTester tester,
    ScanTrackerState state, {
    String initialLocation = '/',
    bool withRouter = true,
  }) async {
    tracker = FakeScanJobTracker(state);
    router = GoRouter(
      initialLocation: initialLocation,
      routes: [
        GoRoute(path: '/', builder: (_, _) => const Text('home-page')),
        GoRoute(
          path: AppRoutes.camera,
          builder: (_, _) => const Text('camera-page'),
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
          scanJobTrackerProvider.overrideWith(() => tracker),
          if (withRouter) appRouterProvider.overrideWithValue(router),
          if (!withRouter)
            appRouterProvider.overrideWith(
              (ref) => throw StateError('no router in this test'),
            ),
        ],
        child: MaterialApp.router(
          theme: AppTheme.build(Brightness.light, AppDensity.cozy),
          routerConfig: router,
          builder: (context, child) => Stack(
            fit: StackFit.expand,
            children: [
              child!,
              const Positioned(
                left: 16,
                right: 16,
                bottom: 16,
                child: Material(
                  type: MaterialType.transparency,
                  child: ScanJobPill(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    await tester.pump();
  }

  ScanTrackerState at(TrackerPhase phase, {bool withCapture = true}) =>
      ScanTrackerState(
        phase: phase,
        uploadProgress: phase == TrackerPhase.uploading ? 0.4 : null,
        job: phase == TrackerPhase.uploading ? null : fakeScanJob(),
        lastCapture: withCapture ? fakeCapture : null,
      );

  testWidgets('idle shows nothing', (tester) async {
    await pump(tester, const ScanTrackerState());
    expect(find.byType(ScanJobPill), findsOneWidget);
    expect(find.text(ScanJobPill.waitingCopy), findsNothing);
    expect(find.text(ScanJobPill.uploadingCopy), findsNothing);
  });

  testWidgets('uploading shows the copy and the upload progress', (
    tester,
  ) async {
    await pump(tester, at(TrackerPhase.uploading));
    expect(find.text('Uploading…'), findsOneWidget);
    final bar = tester.widget<LinearProgressIndicator>(
      find.byKey(const Key('scan-pill-progress')),
    );
    expect(bar.value, 0.4);
  });

  testWidgets('waiting shows Checking your plant…', (tester) async {
    await pump(tester, at(TrackerPhase.waiting));
    expect(find.text('Checking your plant…'), findsOneWidget);
  });

  testWidgets('slow shows the slow copy with Wait and Cancel', (tester) async {
    await pump(tester, at(TrackerPhase.slow));
    expect(
      find.text('This scan is taking a little longer than usual.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('scan-pill-wait')), findsOneWidget);
    expect(find.byKey(const Key('scan-pill-cancel')), findsOneWidget);
    expect(find.text('Wait'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);
  });

  testWidgets('slow → tap Cancel calls cancel()', (tester) async {
    await pump(tester, at(TrackerPhase.slow));
    await tester.tap(find.byKey(const Key('scan-pill-cancel')));
    await tester.pump();
    expect(tracker.calls, ['cancel']);
  });

  testWidgets('slow → Wait collapses to waiting until the phase changes', (
    tester,
  ) async {
    await pump(tester, at(TrackerPhase.slow));
    await tester.tap(find.byKey(const Key('scan-pill-wait')));
    await tester.pump();
    expect(find.text('Checking your plant…'), findsOneWidget);
    expect(find.byKey(const Key('scan-pill-cancel')), findsNothing);

    // A poll tick while still slow emits a fresh state: stay collapsed.
    tracker.emit(at(TrackerPhase.slow));
    await tester.pump();
    expect(find.byKey(const Key('scan-pill-cancel')), findsNothing);

    // A real phase change resets it.
    tracker.emit(at(TrackerPhase.waiting));
    await tester.pump();
    tracker.emit(at(TrackerPhase.slow));
    await tester.pump();
    expect(find.byKey(const Key('scan-pill-cancel')), findsOneWidget);
  });

  testWidgets('ready shows the ready copy with View', (tester) async {
    await pump(tester, at(TrackerPhase.ready));
    expect(find.text('Your plant check is ready'), findsOneWidget);
    expect(find.byKey(const Key('scan-pill-view')), findsOneWidget);
  });

  testWidgets('ready → tap View pushes /scans/<id>', (tester) async {
    await pump(tester, at(TrackerPhase.ready));
    await tester.tap(find.byKey(const Key('scan-pill-view')));
    await tester.pumpAndSettle();
    expect(find.text('scan-job-1'), findsOneWidget);
    expect(tracker.calls, ['dismiss']);
    // Pushed, not replaced: back returns to where the user was.
    expect(router.canPop(), isTrue);
  });

  testWidgets('failed shows the failed copy with Try again and dismiss', (
    tester,
  ) async {
    await pump(tester, at(TrackerPhase.failed));
    expect(find.text("We couldn't check your plant"), findsOneWidget);
    expect(find.byKey(const Key('scan-pill-retry')), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);

    await tester.tap(find.byKey(const Key('scan-pill-retry')));
    await tester.pump();
    expect(tracker.calls, ['retry']);

    await tester.tap(find.byKey(const Key('scan-pill-dismiss')));
    await tester.pump();
    expect(tracker.calls, ['retry', 'dismiss']);
    expect(find.text("We couldn't check your plant"), findsNothing);
  });

  testWidgets('a failed job restored without its capture hides Try again', (
    tester,
  ) async {
    await pump(tester, at(TrackerPhase.failed, withCapture: false));
    expect(find.text("We couldn't check your plant"), findsOneWidget);
    expect(find.byKey(const Key('scan-pill-retry')), findsNothing);
    expect(find.byKey(const Key('scan-pill-dismiss')), findsOneWidget);
  });

  testWidgets('the pill hides on the camera route', (tester) async {
    await pump(tester, at(TrackerPhase.waiting), initialLocation: '/camera');
    expect(find.text('camera-page'), findsOneWidget);
    expect(find.text('Checking your plant…'), findsNothing);

    // The waiting bar is indeterminate, so these pump instead of settling.
    router.go('/');
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Checking your plant…'), findsOneWidget);

    // A push onto the camera hides it again.
    router.push(AppRoutes.camera);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Checking your plant…'), findsNothing);
  });

  testWidgets('without a router the pill still shows', (tester) async {
    await pump(tester, at(TrackerPhase.waiting), withRouter: false);
    expect(tester.takeException(), isNull);
    expect(find.text('Checking your plant…'), findsOneWidget);
  });

  testWidgets('the pill buttons meet the tap target guideline', (tester) async {
    final handle = tester.ensureSemantics();
    await pump(tester, at(TrackerPhase.slow));
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await pump(tester, at(TrackerPhase.failed));
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    handle.dispose();
  });

  testWidgets('the pill fits a small phone at 2x text', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    for (final phase in [
      TrackerPhase.uploading,
      TrackerPhase.slow,
      TrackerPhase.ready,
      TrackerPhase.failed,
    ]) {
      await pump(tester, at(phase));
      expect(tester.takeException(), isNull, reason: '$phase');
    }
  });
}
