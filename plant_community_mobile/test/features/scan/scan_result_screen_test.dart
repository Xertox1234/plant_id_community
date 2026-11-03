import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/error_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/results/results_screen.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_result_screen.dart';
import 'package:plant_community_mobile/services/api_service.dart';

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

Future<_FakeApi> _pump(
  WidgetTester tester,
  ScanJob job, {
  Object? error,
}) async {
  final api = _FakeApi(job, error: error);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [scanJobApiProvider.overrideWithValue(api)],
      child: MaterialApp(
        theme: AppTheme.build(Brightness.light, AppDensity.cozy),
        home: const ScanResultScreen(jobId: 'job-9'),
      ),
    ),
  );
  return api;
}

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
}
