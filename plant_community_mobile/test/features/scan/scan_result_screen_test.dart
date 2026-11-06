import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/error_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/results/results_screen.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_decisions.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/features/scan/scan_result_screen.dart';
import 'package:plant_community_mobile/features/scan/widgets/short_scan_card.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';

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

/// Records keep/dismiss without the API or Firestore. Configured through
/// [_decisionError] and [_keepGate] because the provider builds lazily, on
/// the first tap; both are reset by every pump.
class _FakeDecisions extends ScanDecisions {
  _FakeDecisions(super.ref);

  @override
  Future<void> keep(ScanJob job) async {
    _decisionCalls.add('keep:${job.id}');
    final g = _keepGate;
    if (g != null) await g.future;
    if (_decisionError != null) throw _decisionError!;
  }

  @override
  Future<void> dismiss(String jobId) async {
    _decisionCalls.add('dismiss:$jobId');
    if (_decisionError != null) throw _decisionError!;
  }
}

var _decisionCalls = <String>[];

/// Thrown by keep and dismiss after recording, when set.
Object? _decisionError;

/// Holds a keep open while set.
Completer<void>? _keepGate;

/// The signed-in user's saved plants, as the plants stream reports them.
/// Holds the scan by default, so a kept scan reads as in the collection.
var _collection = <Plant>[];

Plant _savedPlant(String id) => Plant(
  id: id,
  name: 'Monstera',
  scientificName: 'Monstera deliciosa',
  description: '',
  care: const [],
  timestamp: DateTime.utc(2026, 11, 2),
);

void _resetDecisions() {
  _decisionCalls = <String>[];
  _decisionError = null;
  _keepGate = null;
  _collection = [_savedPlant('job-9')];
}

/// Signed in as `user-1`, with [_collection] as the saved plants.
List<Override> get _userOverrides => [
  currentUserIdProvider.overrideWithValue('user-1'),
  plantsStreamProvider(
    'user-1',
  ).overrideWith((ref) => Stream.value(PlantsSnapshot(plants: _collection))),
];

ScanJob _job(
  ScanJobStatus status, {
  ScanJobResult? result,
  ScanDecision decision = ScanDecision.kept,
  DateTime? decideBy,
}) => ScanJob(
  id: 'job-9',
  mode: ScanMode.diagnose,
  status: status,
  chargedAs: 'diagnose',
  result: result,
  photos: const {},
  coverPhoto: 'https://a.test/api/v1/scans/job-9/photos/whole/',
  createdAt: DateTime.utc(2026, 11, 2, 9, 30),
  decision: decision,
  decideBy: decideBy,
);

/// An undecided job with most of a day left to decide.
ScanJob _undecided(ScanJobStatus status) => _job(
  status,
  result: _result,
  decision: ScanDecision.undecided,
  decideBy: DateTime.now().add(const Duration(hours: 18, minutes: 30)),
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
  _resetDecisions();
  _tracker = FakeScanJobTracker(tracker);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        scanJobApiProvider.overrideWithValue(api),
        scanJobTrackerProvider.overrideWith(() => _tracker),
        scanDecisionsProvider.overrideWith(_FakeDecisions.new),
        ..._userOverrides,
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
  _resetDecisions();
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (_, _) => const Text('home-page')),
      GoRoute(path: '/home', builder: (_, _) => const Text('home-root')),
      GoRoute(
        path: '/collection',
        builder: (_, _) => const Text('my-plants-page'),
      ),
      GoRoute(
        path: '/scans/:id',
        builder: (_, s) => ScanResultScreen(jobId: s.pathParameters['id']!),
        routes: [
          GoRoute(
            path: 'full',
            builder: (_, s) =>
                ScanFullResultScreen(jobId: s.pathParameters['id']!),
          ),
        ],
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        scanJobApiProvider.overrideWithValue(_FakeApi(job)),
        scanJobTrackerProvider.overrideWith(() => _tracker),
        scanDecisionsProvider.overrideWith(_FakeDecisions.new),
        ..._userOverrides,
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

    testWidgets('a double tap retries once (L10)', (tester) async {
      final job = _job(ScanJobStatus.degraded, result: _result);
      await _pumpPushed(tester, job, tracker: _trackerAt(job));

      await tester.tap(find.byKey(ResultsScreen.retryKey));
      await tester.pump(); // the pop has started; the button is still there
      expect(find.byKey(ResultsScreen.retryKey), findsOneWidget);
      expect(
        find.byKey(ResultsScreen.retryKey).hitTestable(),
        findsNothing,
        reason: 'the popping route ignores pointers',
      );
      await tester.tap(find.byKey(ResultsScreen.retryKey), warnIfMissed: false);
      await _settle(tester);

      expect(_tracker.calls.where((c) => c == 'retry'), hasLength(1));
      expect(find.text('home-page'), findsOneWidget);
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

  group('keep or dismiss', () {
    testWidgets('undecided job opens the short card', (tester) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      expect(find.byType(ShortScanCard), findsOneWidget);
      expect(find.byType(ResultsScreen), findsNothing);
      expect(find.text('Monstera'), findsOneWidget);
      expect(find.text('Deletes in 18 h'), findsOneWidget);
      expect(find.text('Add to My Collection'), findsNothing);
      expect(_tracker.calls, contains('viewed:job-9'));
    });

    testWidgets('View opens the full result with Add to My Collection', (
      tester,
    ) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      await tester.tap(find.text('View'));
      await _settle(tester);
      expect(find.byType(ResultsScreen), findsOneWidget);
      expect(find.text('A climbing aroid.'), findsOneWidget);
      expect(find.text('Add to My Collection'), findsOneWidget);
      expect(find.byKey(ScanDecisionBar.dismissKey), findsOneWidget);
    });

    testWidgets('Add calls keep and shows In My Collection', (tester) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      await tester.tap(find.text('View'));
      await _settle(tester);
      _keepGate = Completer<void>();
      await tester.tap(find.text('Add to My Collection'));
      await tester.pump();
      // In flight: both buttons are off, but the way back still works.
      expect(_decisionCalls, ['keep:job-9']);
      final dismiss = tester.widget<ClayButton>(
        find.byKey(ScanDecisionBar.dismissKey),
      );
      expect(dismiss.onPressed, isNull);
      expect(find.byType(BackButton), findsOneWidget);

      _keepGate!.complete();
      await _settle(tester);
      expect(find.text('In My Collection'), findsOneWidget);
      expect(find.text('Add to My Collection'), findsNothing);
      expect(find.byKey(ScanDecisionBar.dismissKey), findsNothing);
    });

    testWidgets('a failed Add shows the error and offers Add again', (
      tester,
    ) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      await tester.tap(find.text('View'));
      await _settle(tester);
      _decisionError = ApiException('Scan already decided.', statusCode: 409);
      await tester.tap(find.text('Add to My Collection'));
      await _settle(tester);
      expect(find.text('Scan already decided.'), findsOneWidget);
      expect(find.text('Add to My Collection'), findsOneWidget);
      expect(find.text('In My Collection'), findsNothing);
    });

    testWidgets('Dismiss calls dismiss and leaves', (tester) async {
      final router = await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      await tester.tap(find.byKey(ShortScanCard.dismissKey));
      await _settle(tester);
      expect(_decisionCalls, ['dismiss:job-9']);
      expect(find.text('home-page'), findsOneWidget);
      expect(router.canPop(), isFalse);
    });

    testWidgets('Dismiss on the full result goes to My Plants', (tester) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      await tester.tap(find.text('View'));
      await _settle(tester);
      await tester.tap(find.byKey(ScanDecisionBar.dismissKey));
      await _settle(tester);
      expect(_decisionCalls, ['dismiss:job-9']);
      expect(find.text('my-plants-page'), findsOneWidget);
    });

    testWidgets('a failed Dismiss stays on the card', (tester) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.done),
        tracker: const ScanTrackerState(),
      );
      _decisionError = ApiException('offline');
      await tester.tap(find.byKey(ShortScanCard.dismissKey));
      await _settle(tester);
      expect(find.byType(ShortScanCard), findsOneWidget);
      expect(
        find.text("Couldn't dismiss the scan. Try again."),
        findsOneWidget,
      );
    });

    testWidgets('shows deleted state on 404', (tester) async {
      await _pump(
        tester,
        _job(ScanJobStatus.done),
        error: ApiException('Not found.', statusCode: 404),
      );
      await tester.pump();
      expect(find.text('This scan was deleted'), findsOneWidget);
      expect(find.byType(ErrorScreen), findsNothing);
    });

    testWidgets('a past-due undecided job reads as deleted', (tester) async {
      await _pump(
        tester,
        _job(
          ScanJobStatus.done,
          result: _result,
          decision: ScanDecision.undecided,
          decideBy: DateTime.now().subtract(const Duration(minutes: 1)),
        ),
      );
      await tester.pump();
      expect(find.text('This scan was deleted'), findsOneWidget);
      expect(find.byType(ShortScanCard), findsNothing);
    });

    testWidgets('kept job shows In My Collection and no Add', (tester) async {
      await _pump(tester, _job(ScanJobStatus.done, result: _result));
      await tester.pump();
      expect(find.byType(ResultsScreen), findsOneWidget);
      expect(find.text('In My Collection'), findsOneWidget);
      expect(find.text('Add to My Collection'), findsNothing);
      expect(find.byType(ShortScanCard), findsNothing);
    });

    testWidgets('half-result offers Try again', (tester) async {
      final job = _undecided(ScanJobStatus.degraded);
      await _pumpPushed(tester, job, tracker: _trackerAt(job));
      expect(find.byType(ShortScanCard), findsOneWidget);
      expect(find.text("Health check didn't run"), findsOneWidget);
      await tester.tap(find.text('Try again'));
      await _settle(tester);
      expect(_tracker.calls, contains('retry'));
      expect(find.text('home-page'), findsOneWidget);
    });

    testWidgets('a half-result without the capture offers no Try again', (
      tester,
    ) async {
      final job = _undecided(ScanJobStatus.degraded);
      await _pumpPushed(
        tester,
        job,
        tracker: _trackerAt(job, withCapture: false),
      );
      expect(find.byType(ShortScanCard), findsOneWidget);
      expect(find.text('Try again'), findsNothing);
    });

    testWidgets('kept job missing from collection offers Add again', (
      tester,
    ) async {
      await _pump(tester, _job(ScanJobStatus.done, result: _result));
      _collection = [_savedPlant('another-plant')];
      await tester.pump();
      await tester.pump();
      expect(find.byType(ResultsScreen), findsOneWidget);
      expect(find.text('In My Collection'), findsNothing);
      expect(find.text('Add to My Collection'), findsOneWidget);
      // A kept scan cannot be dismissed, only written again.
      expect(find.byKey(ScanDecisionBar.dismissKey), findsNothing);

      await tester.tap(find.text('Add to My Collection'));
      await tester.pump();
      await tester.pump();
      expect(_decisionCalls, ['keep:job-9']);
      expect(find.text('In My Collection'), findsOneWidget);
    });

    testWidgets('dismissing a half-result clears the tracker pill', (
      tester,
    ) async {
      final job = _undecided(ScanJobStatus.degraded);
      await _pumpPushed(tester, job, tracker: _trackerAt(job));
      await tester.tap(find.byKey(ShortScanCard.dismissKey));
      await _settle(tester);
      expect(_decisionCalls, ['dismiss:job-9']);
      expect(_tracker.calls, contains('dismiss'));
      expect(find.text('home-page'), findsOneWidget);
    });

    testWidgets('dismissing from the full result clears the tracker pill', (
      tester,
    ) async {
      final job = _undecided(ScanJobStatus.degraded);
      await _pumpPushed(tester, job, tracker: _trackerAt(job));
      await tester.tap(find.text('View'));
      await _settle(tester);
      await tester.tap(find.byKey(ScanDecisionBar.dismissKey));
      await _settle(tester);
      expect(_tracker.calls, contains('dismiss'));
      expect(find.text('my-plants-page'), findsOneWidget);
    });

    testWidgets('dismissing leaves the pill of another job alone', (
      tester,
    ) async {
      await _pumpPushed(
        tester,
        _undecided(ScanJobStatus.degraded),
        tracker: _trackerAt(fakeScanJob(status: ScanJobStatus.degraded)),
      );
      await tester.tap(find.byKey(ShortScanCard.dismissKey));
      await _settle(tester);
      expect(_decisionCalls, ['dismiss:job-9']);
      expect(_tracker.calls, isNot(contains('dismiss')));
    });
  });
}
