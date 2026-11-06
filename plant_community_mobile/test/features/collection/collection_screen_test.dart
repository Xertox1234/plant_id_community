import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/collection/collection_screen.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_decisions.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/features/scan/widgets/short_scan_card.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

import '../scan/fake_scan_job_tracker.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(Brightness.light, AppDensity.cozy),
  home: child,
);

Plant _plant(String id, String name) => Plant(
  id: id,
  name: name,
  scientificName: '$name scientificus',
  description: 'desc',
  care: const [],
  timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
);

/// Pump [widget] on a portrait phone-sized surface and let the stream provider
/// deliver its first emission (loading -> data). The default 800x600 surface
/// makes the aspect-0.8 grid cells very tall and pushes content out of the
/// findable region.
Future<void> _pump(WidgetTester tester, Widget widget) async {
  await tester.binding.setSurfaceSize(const Size(400, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(widget);
  await tester.pump();
  await tester.pump();
}

/// Records removePlant/dismiss without the API or Firestore.
class _FakeDecisions extends ScanDecisions {
  _FakeDecisions(super.ref);

  @override
  Future<void> removePlant(Plant plant) async {
    _calls.add('remove:${plant.id}');
    if (_decisionError != null) throw _decisionError!;
  }

  @override
  Future<void> dismiss(String jobId) async {
    _calls.add('dismiss:$jobId');
    if (_decisionError != null) throw _decisionError!;
  }
}

var _calls = <String>[];
Object? _decisionError;

/// No undecided scans, so the screen never reaches the network.
final _noUndecided = undecidedScansProvider.overrideWith(
  (ref) async => const <ScanJob>[],
);

/// The fixed clock every undecided-card test reads.
final _now = DateTime.utc(2026, 11, 6, 12);

ScanJob _undecided(
  String id,
  String name, {
  required DateTime createdAt,
  DateTime? decideBy,
  ScanJobStatus status = ScanJobStatus.done,
}) => ScanJob(
  id: id,
  mode: ScanMode.diagnose,
  status: status,
  chargedAs: 'diagnose',
  result: ScanJobResult(
    plantName: name,
    scientificName: '$name sp.',
    confidence: 0.9,
    description: '',
    diagnosis: const ScanDiagnosis(state: 'healthy'),
  ),
  photos: const {},
  coverPhoto: null,
  createdAt: createdAt,
  decision: ScanDecision.undecided,
  decideBy: decideBy ?? _now.add(const Duration(hours: 18)),
);

/// Signed in, with [plants] kept and [undecided] (or [undecidedError])
/// waiting for a decision.
Future<FakeScanJobTracker> _pumpScreen(
  WidgetTester tester, {
  List<Plant> plants = const [],
  List<ScanJob> undecided = const [],
  Object? undecidedError,
  ScanTrackerState tracker = const ScanTrackerState(),
  DateTime Function()? clock,
}) async {
  _calls = <String>[];
  _decisionError = null;
  final fakeTracker = FakeScanJobTracker(tracker);
  final overrides = <Override>[
    currentUserIdProvider.overrideWithValue('test-uid'),
    plantsStreamProvider(
      'test-uid',
    ).overrideWith((ref) => Stream.value(PlantsSnapshot(plants: plants))),
    undecidedScansProvider.overrideWith((ref) async {
      if (undecidedError != null) throw undecidedError;
      return undecided;
    }),
    scanJobTrackerProvider.overrideWith(() => fakeTracker),
    scanDecisionsProvider.overrideWith(_FakeDecisions.new),
  ];
  await _pump(
    tester,
    ProviderScope(
      overrides: overrides,
      child: _wrap(CollectionScreen(now: clock ?? () => _now)),
    ),
  );
  return fakeTracker;
}

void main() {
  const uid = 'test-uid';

  testWidgets('shows undecided cards above kept plants', (tester) async {
    await _pumpScreen(
      tester,
      plants: [_plant('1', 'Monstera')],
      undecided: [
        _undecided(
          'old',
          'Fern',
          createdAt: _now.subtract(const Duration(hours: 3)),
        ),
        _undecided(
          'new',
          'Pothos',
          createdAt: _now.subtract(const Duration(hours: 1)),
        ),
      ],
    );

    expect(find.byType(ShortScanCard), findsNWidgets(2));
    expect(find.text('Deletes in 18 h'), findsNWidgets(2));
    final pothos = tester.getTopLeft(find.text('Pothos')).dy;
    final fern = tester.getTopLeft(find.text('Fern')).dy;
    final kept = tester.getTopLeft(find.text('Monstera')).dy;
    expect(pothos, lessThan(fern), reason: 'newest first');
    expect(fern, lessThan(kept), reason: 'undecided above kept plants');
  });

  testWidgets('hides an undecided card whose decide_by passed', (tester) async {
    await _pumpScreen(
      tester,
      undecided: [
        _undecided(
          'gone',
          'Fern',
          createdAt: _now.subtract(const Duration(days: 1)),
          decideBy: _now.subtract(const Duration(minutes: 1)),
        ),
        _undecided('live', 'Pothos', createdAt: _now),
      ],
    );

    expect(find.byType(ShortScanCard), findsOneWidget);
    expect(find.text('Pothos'), findsOneWidget);
    expect(find.text('Fern'), findsNothing);
    // A live card keeps the empty state away.
    expect(find.text('No plants yet'), findsNothing);
  });

  testWidgets('the minute tick drops a card once its time runs out', (
    tester,
  ) async {
    var at = _now;
    await _pumpScreen(
      tester,
      clock: () => at,
      undecided: [
        _undecided(
          'soon',
          'Fern',
          createdAt: _now,
          decideBy: _now.add(const Duration(seconds: 90)),
        ),
      ],
    );
    expect(find.text('Deletes in 1 min'), findsOneWidget);

    at = _now.add(const Duration(minutes: 2));
    await tester.pump(const Duration(minutes: 1));

    expect(find.byType(ShortScanCard), findsNothing);
    expect(find.text('No plants yet'), findsOneWidget);
  });

  testWidgets('count shows kept plants only', (tester) async {
    await _pumpScreen(
      tester,
      plants: [_plant('1', 'Monstera')],
      undecided: [
        _undecided('a', 'Fern', createdAt: _now),
        _undecided('b', 'Pothos', createdAt: _now),
      ],
    );

    expect(find.text('1 PLANT IDENTIFIED'), findsOneWidget);
  });

  testWidgets('long-press Remove confirms then calls removePlant', (
    tester,
  ) async {
    await _pumpScreen(tester, plants: [_plant('p1', 'Monstera')]);

    await tester.longPress(find.text('Monstera'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(CollectionScreen.removeActionKey));
    await tester.pumpAndSettle();

    expect(find.text('Remove Monstera from My Plants?'), findsOneWidget);
    expect(_calls, isEmpty, reason: 'nothing removed before confirming');

    await tester.tap(find.byKey(CollectionScreen.removeConfirmKey));
    await tester.pumpAndSettle();

    expect(_calls, ['remove:p1']);
  });

  testWidgets('Cancel on the Remove sheet removes nothing', (tester) async {
    await _pumpScreen(tester, plants: [_plant('p1', 'Monstera')]);

    await tester.longPress(find.text('Monstera'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(CollectionScreen.removeActionKey));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(_calls, isEmpty);
    expect(find.text('Remove Monstera from My Plants?'), findsNothing);
  });

  testWidgets('a failed Remove shows the error', (tester) async {
    await _pumpScreen(tester, plants: [_plant('p1', 'Monstera')]);
    _decisionError = StateError('nope');

    await tester.longPress(find.text('Monstera'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(CollectionScreen.removeActionKey));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(CollectionScreen.removeConfirmKey));
    await tester.pumpAndSettle();

    expect(_calls, ['remove:p1']);
    expect(find.byType(SnackBar), findsOneWidget);
  });

  testWidgets('undecided list error still shows kept grid', (tester) async {
    await _pumpScreen(
      tester,
      plants: [_plant('1', 'Monstera')],
      undecidedError: Exception('offline'),
    );

    expect(find.byType(ShortScanCard), findsNothing);
    expect(find.text('Monstera'), findsOneWidget);
    expect(find.text('1 PLANT IDENTIFIED'), findsOneWidget);
  });

  testWidgets('a degraded tracked scan offers Try again', (tester) async {
    final job = _undecided(
      'deg',
      'Fern',
      createdAt: _now,
      status: ScanJobStatus.degraded,
    );
    final tracker = await _pumpScreen(
      tester,
      undecided: [
        job,
        _undecided('other', 'Pothos', createdAt: _now),
      ],
      tracker: ScanTrackerState(
        phase: TrackerPhase.ready,
        job: job,
        lastCapture: fakeCapture,
      ),
    );

    expect(find.byKey(ShortScanCard.tryAgainKey), findsOneWidget);
    await tester.tap(find.byKey(ShortScanCard.tryAgainKey));
    await tester.pump();
    expect(tracker.calls, contains('retry'));
  });

  testWidgets('Dismiss on a card dismisses it and clears its pill', (
    tester,
  ) async {
    final job = _undecided('deg', 'Fern', createdAt: _now);
    final tracker = await _pumpScreen(
      tester,
      undecided: [job],
      tracker: ScanTrackerState(phase: TrackerPhase.ready, job: job),
    );

    await tester.tap(find.byKey(ShortScanCard.dismissKey));
    await tester.pump();

    expect(_calls, ['dismiss:deg']);
    expect(tracker.calls, contains('dismiss'));
  });

  testWidgets('signed-out users see a sign-in prompt', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [currentUserIdProvider.overrideWithValue(null)],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('Sign in to see your collection'), findsOneWidget);
  });

  testWidgets('renders identified plants from the stream', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          _noUndecided,
          plantsStreamProvider(uid).overrideWith(
            (ref) => Stream.value(
              PlantsSnapshot(
                plants: [_plant('1', 'Monstera'), _plant('2', 'Peace Lily')],
              ),
            ),
          ),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('2 PLANTS IDENTIFIED'), findsOneWidget);
    expect(find.text('Monstera'), findsOneWidget);
    expect(find.text('Peace Lily'), findsOneWidget);
    expect(find.text('Identify a plant'), findsOneWidget); // the "add" tile
  });

  testWidgets('shows an empty state when the collection is empty', (
    tester,
  ) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          _noUndecided,
          plantsStreamProvider(
            uid,
          ).overrideWith((ref) => Stream.value(PlantsSnapshot.empty)),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('No plants yet'), findsOneWidget);
    expect(find.text('0 PLANTS IDENTIFIED'), findsOneWidget);
  });

  testWidgets('shows an Offline badge when data is from cache', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          _noUndecided,
          plantsStreamProvider(uid).overrideWith(
            (ref) => Stream.value(
              PlantsSnapshot(
                plants: [_plant('1', 'Monstera')],
                isFromCache: true,
              ),
            ),
          ),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('Offline'), findsOneWidget);
  });

  testWidgets('shows a Syncing badge when writes are pending', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          _noUndecided,
          plantsStreamProvider(uid).overrideWith(
            (ref) => Stream.value(
              PlantsSnapshot(
                plants: [_plant('1', 'Monstera')],
                hasPendingWrites: true,
              ),
            ),
          ),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('Syncing…'), findsOneWidget);
  });
}
