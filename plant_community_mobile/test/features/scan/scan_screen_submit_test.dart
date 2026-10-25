import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/scan/scan_camera.dart';
import 'package:plant_community_mobile/features/scan/scan_screen.dart';
import 'package:plant_community_mobile/features/scan/widgets/submit_overlay.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/plant_identification_service.dart';

import 'fake_scan_camera.dart';

class _HoldingIdService extends PlantIdentificationService {
  late final completer = Completer<Plant>();
  void Function(double)? report;

  @override
  Future<Plant> identifyPlant(
    String imagePath, {
    Function(double progress)? onUploadProgress,
  }) {
    report = onUploadProgress;
    return completer.future;
  }
}

final _plant = Plant(
  id: 'x',
  name: 'Fern',
  scientificName: 'Pteridophyta',
  description: 'd',
  care: const [],
  timestamp: DateTime(2026),
);

void main() {
  late FakeScanCamera fake;
  late _HoldingIdService service;
  late GoRouter router;

  setUp(() {
    fake = FakeScanCamera()..nextPicturePath = 'p.jpg';
    service = _HoldingIdService();
  });

  Future<void> pump(WidgetTester tester) async {
    router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, _) => const ScanScreen()),
        GoRoute(
          path: AppRoutes.results,
          builder: (_, _) => const Text('results-page'),
        ),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          scanCameraFactoryProvider.overrideWithValue(() => fake),
          plantIdentificationServiceProvider.overrideWith(() => service),
          currentUserIdProvider.overrideWithValue(null),
        ],
        child: MaterialApp.router(
          theme: AppTheme.build(Brightness.light, AppDensity.cozy),
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  /// Lets the chained awaits of a completed upload run, then the route and
  /// SnackBar animations.
  Future<void> settleAsync(WidgetTester tester) async {
    await tester.runAsync(() => Future<void>.delayed(Duration.zero));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
  }

  Future<void> shootAndDone(WidgetTester tester) async {
    await tester.tap(find.byKey(ScanScreen.shutterKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.tap(find.byKey(const ValueKey('step-chip-problem')));
    await tester.pump(const Duration(milliseconds: 400));
    await tester.tap(find.byKey(ScanScreen.doneKey));
    await tester.pump();
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

  testWidgets('Done shows a progress overlay, then replaces with results', (
    tester,
  ) async {
    await pump(tester);
    expect(find.text(SubmitOverlay.copy), findsNothing);
    await shootAndDone(tester);

    expect(find.text('Checking your plant…'), findsOneWidget);
    expect(bar(tester).value, isNull);

    service.report!(0.4);
    await tester.pump();
    expect(bar(tester).value, 0.4);

    // The overlay blocks the controls underneath.
    await tester.tap(find.byKey(ScanScreen.shutterKey), warnIfMissed: false);
    expect(fake.takePictureCalls, 1);

    service.completer.complete(_plant);
    await settleAsync(tester);
    expect(find.text('results-page'), findsOneWidget);
  });

  testWidgets('a failure shows a SnackBar and keeps the shots', (tester) async {
    await pump(tester);
    await shootAndDone(tester);
    expect(find.text(SubmitOverlay.copy), findsOneWidget);
    expect(service.report, isNotNull);

    service.completer.completeError(
      PlantIdentificationException('No plant could be identified.'),
    );
    await settleAsync(tester);

    expect(find.text('No plant could be identified.'), findsOneWidget);
    expect(find.text(SubmitOverlay.copy), findsNothing);
    expect(find.byKey(const ValueKey('tray-problem')), findsOneWidget);
    expect(find.byKey(ScanScreen.doneKey), findsOneWidget);
  });
}
