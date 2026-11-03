import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/error_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/results/results_screen.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/features/scan/scan_result_screen.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import 'fake_scan_job_tracker.dart';

class _FakeApi extends ScanJobApi {
  _FakeApi(this.job, {this.error})
    : super(ApiService(baseUrl: 'https://a.test'));
  final ScanJob job;
  final Object? error;
  final asked = <String>[];

  @override
  Future<ScanJob> get(String id) async {
    asked.add(id);
    if (error != null) throw error!;
    return job;
  }
}

ScanJob _job(ScanJobStatus status, {ScanJobResult? result}) => ScanJob(
  id: 'job-9',
  mode: ScanMode.diagnose,
  status: status,
  chargedAs: 'diagnose',
  result: result,
  photos: const {},
  coverPhoto: 'https://a.test/api/v1/scans/job-9/photos/whole/',
  createdAt: DateTime.utc(2026, 11, 2, 9, 30),
);

const _result = ScanJobResult(
  plantName: 'Monstera',
  scientificName: 'Monstera deliciosa',
  confidence: 0.91,
  description: 'A climbing aroid.',
  diagnosis: ScanDiagnosis(state: 'healthy'),
);

late FakeScanJobTracker _tracker;

Future<_FakeApi> _pump(
  WidgetTester tester,
  ScanJob job, {
  Object? error,
  ScanTrackerState tracker = const ScanTrackerState(),
}) async {
  final api = _FakeApi(job, error: error);
  _tracker = FakeScanJobTracker(tracker);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        scanJobApiProvider.overrideWithValue(api),
        scanJobTrackerProvider.overrideWith(() => _tracker),
      ],
      child: MaterialApp(
        theme: AppTheme.build(Brightness.light, AppDensity.cozy),
        home: const ScanResultScreen(jobId: 'job-9'),
      ),
    ),
  );
  return api;
}

/// The result pushed over a home page, as the pill and a push open it.
Future<GoRouter> _pumpPushed(
  WidgetTester tester,
  ScanJob job, {
  required ScanTrackerState tracker,
}) async {
  _tracker = FakeScanJobTracker(tracker);
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (_, _) => const Text('home-page')),
      GoRoute(
        path: '/scans/:id',
        builder: (_, s) => ScanResultScreen(jobId: s.pathParameters['id']!),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        scanJobApiProvider.overrideWithValue(_FakeApi(job)),
        scanJobTrackerProvider.overrideWith(() => _tracker),
      ],
      child: MaterialApp.router(
        theme: AppTheme.build(Brightness.light, AppDensity.cozy),
        routerConfig: router,
      ),
    ),
  );
  router.push('/scans/job-9');
  await _settle(tester);
  return router;
}

/// The cover image's spinner never settles: pump through the transition.
Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
  await tester.pump(const Duration(milliseconds: 500));
}

ScanTrackerState _trackerAt(ScanJob job, {bool withCapture = true}) =>
    ScanTrackerState(
      phase: TrackerPhase.ready,
      job: job,
      lastCapture: withCapture ? fakeCapture : null,
    );

void main() {
  testWidgets('scan result loads job by id and renders ResultsScreen', (
    tester,
  ) async {
    final api = await _pump(tester, _job(ScanJobStatus.done, result: _result));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    await tester.pump();
    expect(api.asked, ['job-9']);
    expect(find.byType(ResultsScreen), findsOneWidget);
    expect(find.text('Monstera'), findsOneWidget);
    expect(find.text('Looks healthy'), findsOneWidget);
    expect(find.text('91% match'), findsOneWidget);
  });

  testWidgets('scan result for a degraded job shows the degraded copy', (
    tester,
  ) async {
    await _pump(tester, _job(ScanJobStatus.degraded, result: _result));
    await tester.pump();
    expect(
      find.text(
        "We named your plant but couldn't check its health. "
        "Your check wasn't used.",
      ),
      findsOneWidget,
    );
  });

  testWidgets('scan result without a result shows the failed copy', (
    tester,
  ) async {
    await _pump(tester, _job(ScanJobStatus.failed));
    await tester.pump();
    expect(find.text("We couldn't check your plant"), findsOneWidget);
    expect(find.text('Close'), findsOneWidget);
    expect(find.byType(ResultsScreen), findsNothing);
  });

  testWidgets('scan result with a done job but null result is handled', (
    tester,
  ) async {
    await _pump(tester, _job(ScanJobStatus.done));
    await tester.pump();
    expect(find.text("We couldn't check your plant"), findsOneWidget);
  });

  testWidgets('scan result load error shows ErrorScreen', (tester) async {
    await _pump(tester, _job(ScanJobStatus.done), error: Exception('boom'));
    await tester.pump();
    expect(find.byType(ErrorScreen), findsOneWidget);
  });

  testWidgets('a loaded result tells the tracker it was viewed', (
    tester,
  ) async {
    await _pump(tester, _job(ScanJobStatus.done, result: _result));
    await tester.pump();
    await tester.pump();
    expect(_tracker.calls, ['viewed:job-9']);
  });

  testWidgets('a job without a result is not marked viewed', (tester) async {
    await _pump(tester, _job(ScanJobStatus.failed));
    await tester.pump();
    await tester.pump();
    expect(_tracker.calls, isEmpty);
  });

  group('Try again on a degraded result', () {
    testWidgets('shown while the tracker holds this job\'s capture; it '
        'retries and goes back to where the pill shows', (tester) async {
      final job = _job(ScanJobStatus.degraded, result: _result);
      final router = await _pumpPushed(tester, job, tracker: _trackerAt(job));
      expect(find.byKey(ResultsScreen.retryKey), findsOneWidget);

      await tester.tap(find.byKey(ResultsScreen.retryKey));
      await _settle(tester);

      expect(_tracker.calls, contains('retry'));
      expect(find.text('home-page'), findsOneWidget);
      expect(find.byType(ScanResultScreen), findsNothing);
      expect(router.canPop(), isFalse);
    });

    testWidgets('hidden once the capture is gone (after a kill)', (
      tester,
    ) async {
      final job = _job(ScanJobStatus.degraded, result: _result);
      await _pumpPushed(
        tester,
        job,
        tracker: _trackerAt(job, withCapture: false),
      );
      expect(find.byType(ResultsScreen), findsOneWidget);
      expect(find.byKey(ResultsScreen.retryKey), findsNothing);
    });

    testWidgets('hidden when the tracker holds another job', (tester) async {
      final job = _job(ScanJobStatus.degraded, result: _result);
      await _pumpPushed(
        tester,
        job,
        tracker: _trackerAt(fakeScanJob(status: ScanJobStatus.degraded)),
      );
      expect(find.byKey(ResultsScreen.retryKey), findsNothing);
    });

    testWidgets('a non-degraded result offers no Try again', (tester) async {
      final job = _job(ScanJobStatus.done, result: _result);
      await _pumpPushed(tester, job, tracker: _trackerAt(job));
      expect(find.byType(ResultsScreen), findsOneWidget);
      expect(find.byKey(ResultsScreen.retryKey), findsNothing);
    });
  });
}
