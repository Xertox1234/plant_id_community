import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/home/home_page.dart';
import 'package:plant_community_mobile/features/scan/capture_session.dart';
import 'package:plant_community_mobile/features/scan/capture_steps.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/features/scan/scan_job_tracker.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_label.dart';
import 'package:plant_community_mobile/shared/widgets/feature_card.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

ScanAllowance _allowance({
  bool isPremium = false,
  int remaining = 1,
  int premiumLimit = 3,
}) => ScanAllowance(
  isPremium: isPremium,
  diagnoseRemaining: remaining,
  diagnoseLimit: isPremium ? premiumLimit : 1,
  identifyRemaining: 5,
  identifyLimit: 5,
  resetsAt: DateTime.utc(2026, 11, 3),
  plantIdAvailable: true,
  slowAfterSeconds: 45,
  premiumDiagnoseLimit: premiumLimit,
);

Widget _wrap({ScanAllowance? allowance}) => ProviderScope(
  overrides: [scanAllowanceProvider.overrideWith((ref) async => allowance)],
  child: MaterialApp(
    theme: AppTheme.build(Brightness.light, AppDensity.cozy),
    home: const HomePage(),
  ),
);

/// The server side of one scan: the allowance drops when a job is created
/// and comes back when it is cancelled.
class _ScanServer extends ScanJobApi {
  _ScanServer() : super(ApiService(baseUrl: 'https://api.test'));

  int remaining = 1;
  ScanJobStatus next = ScanJobStatus.processing;

  ScanJob _job(ScanJobStatus status) => ScanJob(
    id: 'job-1',
    mode: ScanMode.diagnose,
    status: status,
    chargedAs: 'diagnose',
    result: null,
    photos: const {},
    coverPhoto: null,
    createdAt: DateTime.utc(2026, 11, 2, 9, 30),
  );

  @override
  Future<ScanAllowance> allowance() async => _allowance(remaining: remaining);

  @override
  Future<ScanJob> create(
    CaptureResult r, {
    String? retryOf,
    void Function(double)? onProgress,
  }) async {
    remaining = 0;
    return _job(ScanJobStatus.pending);
  }

  @override
  Future<ScanJob> get(String id) async => _job(next);

  @override
  Future<ScanJob> cancel(String id) async {
    remaining = 1;
    return _job(ScanJobStatus.cancelled);
  }
}

const _capture = CaptureResult(
  mode: ScanMode.diagnose,
  shots: {CaptureRole.problem: '/tmp/p.jpg'},
);

/// HomePage over the REAL tracker, so the allowance line sees what the
/// tracker does.
Future<(_ScanServer, ProviderContainer)> _pumpWithTracker(
  WidgetTester tester,
) async {
  FlutterSecureStorage.setMockInitialValues({});
  final server = _ScanServer();
  final container = ProviderContainer(
    overrides: [
      scanJobApiProvider.overrideWithValue(server),
      scanTrackerStorageProvider.overrideWithValue(
        const FlutterSecureStorage(),
      ),
      currentUserIdProvider.overrideWithValue('user-1'),
      firebaseFirestoreProvider.overrideWithValue(FakeFirebaseFirestore()),
    ],
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: AppTheme.build(Brightness.light, AppDensity.cozy),
        home: const HomePage(),
      ),
    ),
  );
  await tester.pump();
  return (server, container);
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void main() {
  group('allowance line follows the scan job', () {
    testWidgets('the home line updates after a job finishes', (tester) async {
      final (server, container) = await _pumpWithTracker(tester);
      expect(find.text('1 check left today'), findsOneWidget);
      final tracker = container.read(scanJobTrackerProvider.notifier);
      await tracker.restored;

      await tracker.submit(_capture);
      await _settle(tester);
      expect(find.text('No checks left today · Go premium for 3'), findsOne);

      // The health check never ran: the server refunds the check.
      server
        ..remaining = 1
        ..next = ScanJobStatus.degraded;
      await tester.pump(scanJobPollInterval);
      await _settle(tester);
      expect(container.read(scanJobTrackerProvider).phase, TrackerPhase.ready);
      expect(find.text('1 check left today'), findsOneWidget);
      tracker.dismiss();
      await _settle(tester);
    });

    testWidgets('the home line updates after a cancel', (tester) async {
      final (_, container) = await _pumpWithTracker(tester);
      final tracker = container.read(scanJobTrackerProvider.notifier);
      await tracker.restored;
      await tracker.submit(_capture);
      await _settle(tester);
      expect(find.text('No checks left today · Go premium for 3'), findsOne);

      await tracker.cancel();
      await _settle(tester);
      expect(find.text('1 check left today'), findsOneWidget);
    });
  });

  testWidgets('hero is diagnosis-first: label, headline, body, one CTA', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    expect(find.text('PLANT HEALTH CHECK'), findsOneWidget);
    expect(find.text("What's wrong with your plant?"), findsOneWidget);
    expect(
      find.text(
        "Photograph the problem. We'll name the plant, find the cause and "
        'tell you what to do.',
      ),
      findsOneWidget,
    );
    expect(find.byKey(HomePage.checkPlantKey), findsOneWidget);
    expect(find.text('Check a sick plant'), findsOneWidget);
    expect(find.byKey(HomePage.justIdentifyKey), findsOneWidget);
    expect(find.text('Join the forum'), findsNothing);
    expect(find.text('Instant Identification'), findsNothing);
    expect(find.text('Diagnose a Sick Plant'), findsNothing);
  });

  testWidgets('"plant?" is the accent-coloured word of the headline', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    final rich = tester.widget<RichText>(
      find.byWidgetPredicate(
        (w) =>
            w is RichText &&
            w.text.toPlainText() == "What's wrong with your plant?",
      ),
    );
    TextSpan? accent;
    rich.text.visitChildren((span) {
      if (span is TextSpan && span.text == 'plant?') accent = span;
      return true;
    });
    expect(accent, isNotNull);
    expect(
      accent!.style?.color,
      Theme.of(tester.element(find.byType(HomePage))).colorScheme.primary,
    );
  });

  group('allowance line', () {
    testWidgets('allowance line shows 1 check left today', (tester) async {
      await tester.pumpWidget(_wrap(allowance: _allowance()));
      await tester.pump();
      expect(find.text('1 check left today'), findsOneWidget);
    });

    testWidgets('plural when several are left', (tester) async {
      await tester.pumpWidget(
        _wrap(allowance: _allowance(isPremium: true, remaining: 2)),
      );
      await tester.pump();
      expect(find.text('2 checks left today'), findsOneWidget);
    });

    testWidgets('free with none shows go-premium copy', (tester) async {
      await tester.pumpWidget(
        _wrap(allowance: _allowance(remaining: 0, premiumLimit: 4)),
      );
      await tester.pump();
      expect(
        find.text('No checks left today · Go premium for 4'),
        findsOneWidget,
      );
    });

    testWidgets('premium with none says when the next check comes back', (
      tester,
    ) async {
      final allowance = _allowance(isPremium: true, remaining: 0);
      await tester.pumpWidget(_wrap(allowance: allowance));
      await tester.pump();
      // Rolling 24h window (scan-2 audit M1): not "midnight" any more.
      expect(
        find.text('More checks at ${allowance.resetsAtLabel}'),
        findsOneWidget,
      );
      expect(find.textContaining('midnight'), findsNothing);
    });

    testWidgets('hidden when allowance is null', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      expect(find.textContaining('left today'), findsNothing);
      expect(find.textContaining('Go premium'), findsNothing);
      expect(find.textContaining('midnight'), findsNothing);
      expect(find.byKey(HomePage.justIdentifyKey), findsOneWidget);
    });
  });

  group('hero actions open the camera', () {
    Future<List<String>> pumpRouted(WidgetTester tester) async {
      final pushed = <String>[];
      final router = GoRouter(
        routes: [
          GoRoute(path: '/', builder: (_, _) => const HomePage()),
          GoRoute(
            path: '/camera',
            builder: (_, state) {
              pushed.add(state.uri.toString());
              return const Scaffold(body: Text('camera'));
            },
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [scanAllowanceProvider.overrideWith((ref) async => null)],
          child: MaterialApp.router(
            theme: AppTheme.build(Brightness.light, AppDensity.cozy),
            routerConfig: router,
          ),
        ),
      );
      return pushed;
    }

    testWidgets('Check a sick plant goes to /camera', (tester) async {
      final pushed = await pumpRouted(tester);
      await tester.tap(find.text('Check a sick plant'));
      await tester.pumpAndSettle();
      expect(pushed, ['/camera']);
    });

    testWidgets('Just identify a plant goes to /camera?mode=identify', (
      tester,
    ) async {
      final pushed = await pumpRouted(tester);
      await tester.tap(find.text('Just identify a plant'));
      await tester.pumpAndSettle();
      expect(pushed, ['/camera?mode=identify']);
    });
  });

  testWidgets('shows the product mark and name, never a legacy identity', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    expect(find.byType(BrandMark), findsOneWidget);
    expect(find.text('Houseplant MD'), findsOneWidget);
    expect(find.text('Welcome to PlantID'), findsNothing);
  });

  testWidgets('CanopyGround fills the viewport, not the scrolled content', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap());
    expect(find.byType(CanopyGround), findsOneWidget);

    // The glow must be BEHIND the scroller, not inside it. A Stack inside a
    // SingleChildScrollView sizes to its non-positioned child, so a
    // CanopyGround nested under the scroll view is as tall as the content —
    // the glow then stretches and scrolls away instead of staying put, and
    // nothing about `findsOneWidget` would notice. Home's content is several
    // viewports tall, so the heights differ by a lot when this regresses.
    final screen = tester.view.physicalSize / tester.view.devicePixelRatio;
    final groundHeight = tester.getSize(find.byType(CanopyGround)).height;
    final contentHeight = tester
        .getSize(find.byType(SingleChildScrollView))
        .height;
    expect(groundHeight, lessThanOrEqualTo(screen.height));
    expect(groundHeight, greaterThanOrEqualTo(contentHeight));
  });

  testWidgets('eyebrow uses the one canonical label treatment', (tester) async {
    await tester.pumpWidget(_wrap());
    // CanopyLabel uppercases — Flutter has no `text-transform`.
    expect(find.byType(CanopyLabel), findsOneWidget);
    expect(find.text('PLANT HEALTH CHECK'), findsOneWidget);
  });

  testWidgets('Care feature card has onTap wired', (tester) async {
    await tester.pumpWidget(_wrap());
    final careCard = tester.widget<FeatureCard>(
      find.byWidgetPredicate(
        (w) => w is FeatureCard && w.title == 'Care Instructions',
      ),
    );
    expect(careCard.onTap, isNotNull);
  });
}
