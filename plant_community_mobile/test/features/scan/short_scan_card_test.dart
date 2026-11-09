import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/widgets/short_scan_card.dart';

final _now = DateTime.utc(2026, 11, 6, 12);

ScanJob _job({
  ScanMode mode = ScanMode.diagnose,
  ScanJobStatus status = ScanJobStatus.done,
  ScanDiagnosis? diagnosis = const ScanDiagnosis(
    state: 'found',
    name: 'Leaf spot',
    probability: 0.8,
  ),
  double? confidence = 0.92,
  Duration left = const Duration(hours: 18, minutes: 40),
}) => ScanJob(
  id: 'job-9',
  mode: mode,
  status: status,
  chargedAs: mode.name,
  result: ScanJobResult(
    plantName: 'Fiddle-leaf fig',
    scientificName: 'Ficus lyrata',
    confidence: confidence,
    description: 'A long description the short card never shows.',
    diagnosis: diagnosis,
  ),
  photos: const {},
  coverPhoto: null,
  createdAt: DateTime.utc(2026, 11, 6, 10),
  decision: ScanDecision.undecided,
  decideBy: _now.add(left),
);

Future<List<String>> _pump(
  WidgetTester tester,
  ScanJob job, {
  bool withTryAgain = false,
  Brightness brightness = Brightness.light,
}) async {
  final calls = <String>[];
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.build(brightness, AppDensity.cozy),
        home: Scaffold(
          body: ShortScanCard(
            job: job,
            now: () => _now,
            onView: () => calls.add('view'),
            onDismiss: () async => calls.add('dismiss'),
            onTryAgain: withTryAgain ? () => calls.add('retry') : null,
          ),
        ),
      ),
    ),
  );
  return calls;
}

void main() {
  testWidgets(
    'short card shows name, 92%, diagnosis line and Deletes in 18 h',
    (tester) async {
      final calls = await _pump(tester, _job());
      expect(find.text('Fiddle-leaf fig'), findsOneWidget);
      expect(find.text('92%'), findsOneWidget);
      expect(find.text('Leaf spot'), findsOneWidget);
      expect(find.text('Deletes in 18 h'), findsOneWidget);
      expect(find.textContaining('long description'), findsNothing);
      expect(find.text('Try again'), findsNothing);

      await tester.tap(find.text('View'));
      await tester.tap(find.text('Dismiss'));
      await tester.pump();
      expect(calls, ['view', 'dismiss']);
    },
  );

  testWidgets('shows minutes under an hour', (tester) async {
    await _pump(tester, _job(left: const Duration(minutes: 42, seconds: 5)));
    expect(find.text('Deletes in 42 min'), findsOneWidget);
  });

  testWidgets('a few seconds left still reads 1 min', (tester) async {
    await _pump(tester, _job(left: const Duration(seconds: 20)));
    expect(find.text('Deletes in 1 min'), findsOneWidget);
  });

  testWidgets('identify scan shows Identified only', (tester) async {
    await _pump(tester, _job(mode: ScanMode.identify, diagnosis: null));
    expect(find.text('Identified only'), findsOneWidget);
  });

  testWidgets('degraded scan shows Health check didn\'t run and Try again', (
    tester,
  ) async {
    final calls = await _pump(
      tester,
      _job(
        status: ScanJobStatus.degraded,
        diagnosis: const ScanDiagnosis(state: 'unavailable'),
      ),
      withTryAgain: true,
    );
    expect(find.text("Health check didn't run"), findsOneWidget);
    await tester.tap(find.text('Try again'));
    expect(calls, ['retry']);
  });

  testWidgets('healthy scan reads Looks healthy; no confidence hides the %', (
    tester,
  ) async {
    await _pump(
      tester,
      _job(diagnosis: const ScanDiagnosis(state: 'healthy'), confidence: null),
    );
    expect(find.text('Looks healthy'), findsOneWidget);
    expect(find.textContaining('%'), findsNothing);
  });

  testWidgets('fits a 320-wide phone at text scale 2 in dark mode', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await _pump(
      tester,
      _job(),
      withTryAgain: true,
      brightness: Brightness.dark,
    );
    expect(tester.takeException(), isNull);
    final h = tester.getSize(find.text('View').first);
    expect(h.height, greaterThan(0));
  });
}
