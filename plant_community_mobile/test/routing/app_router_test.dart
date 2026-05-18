import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/core/routing/navigation_extensions.dart';
import 'package:plant_community_mobile/features/splash/splash_screen.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

// TODO: Add Firebase mocking to enable widget tests
// See test/routing/TEST_STATUS.md for details
//
// Recommended solution: Add firebase_auth_mocks package
//
// dev_dependencies:
//   firebase_auth_mocks: ^0.13.0
//
// Then initialize Firebase in setUp():
//   setUp(() => Firebase.initializeApp());

void main() {
  group('AppRouter Tests', () {
    testWidgets('Initial route should be splash screen', (
      WidgetTester tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));

      // One frame to build the initial route (without settling timers)
      await tester.pump();

      // Initial route should be splash (/)
      expect(router.routerDelegate.currentConfiguration.uri.path, equals('/'));

      // Cancel pending timers by advancing past splash auto-navigation
      await tester.pump(const Duration(seconds: 3));
    });

    testWidgets('Should navigate to home screen', (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));

      // Navigate to home
      router.go(AppRoutes.home);
      await tester.pump(const Duration(milliseconds: 100));

      expect(
        router.routerDelegate.currentConfiguration.uri.path,
        equals(AppRoutes.home),
      );

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('Should navigate to camera screen', (
      WidgetTester tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));

      // Navigate to camera
      router.go(AppRoutes.camera);
      // Pump one frame to complete navigation (before splash timer fires at ~1.8s)
      await tester.pump(const Duration(milliseconds: 100));

      expect(
        router.routerDelegate.currentConfiguration.uri.path,
        equals(AppRoutes.camera),
      );

      // Drain remaining splash timers
      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('Should navigate to results with plant data', (
      WidgetTester tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);
      final testPlant = Plant(
        id: 'test-123',
        name: 'Test Plant',
        scientificName: 'Testus planticus',
        description: 'A test plant for routing tests',
        care: const ['Water regularly', 'Full sun'],
        imageUrl: 'https://example.com/plant.jpg',
        timestamp: DateTime.now(),
      );

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));

      // Navigate to results with plant data
      router.go(AppRoutes.results, extra: testPlant);
      await tester.pump(const Duration(milliseconds: 100));

      expect(
        router.routerDelegate.currentConfiguration.uri.path,
        equals(AppRoutes.results),
      );

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets(
      'Should show error screen when navigating to results without plant data',
      (WidgetTester tester) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockUnauthenticatedAuthNotifier.new,
            ),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(MaterialApp.router(routerConfig: router));

        // Navigate to results WITHOUT plant data
        router.go(AppRoutes.results);
        // Pump one frame to unmount SplashScreen (cancelling its timer), then settle
        await tester.pump();
        await tester.pumpAndSettle(const Duration(milliseconds: 100));

        // Should show error screen
        expect(find.text('Oops! Something went wrong'), findsOneWidget);
        expect(find.byIcon(Icons.error_outline), findsOneWidget);

        await tester.pump(const Duration(seconds: 4));
      },
    );

    testWidgets('Should handle invalid route', (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(MaterialApp.router(routerConfig: router));

      // Navigate to invalid route
      router.go('/this-route-does-not-exist');
      // Pump one frame to unmount SplashScreen (cancelling its timer), then settle
      await tester.pump();
      await tester.pumpAndSettle(const Duration(milliseconds: 100));

      // Should show error screen
      expect(find.text('Oops! Something went wrong'), findsOneWidget);

      await tester.pump(const Duration(seconds: 4));
    });

    group('Authentication Guard Tests', () {
      testWidgets(
        'Should redirect unauthenticated user to login when accessing protected route',
        (WidgetTester tester) async {
          // Create container with unauthenticated state
          final container = ProviderContainer(
            overrides: [
              authServiceProvider.overrideWith(
                _MockUnauthenticatedAuthNotifier.new,
              ),
            ],
          );
          addTearDown(container.dispose);

          final router = container.read(appRouterProvider);

          await tester.pumpWidget(
            UncontrolledProviderScope(
              container: container,
              child: MaterialApp.router(routerConfig: router),
            ),
          );

          // Try to navigate to protected route (profile)
          router.go(AppRoutes.profile);
          await tester.pump(const Duration(milliseconds: 100));

          // Should be redirected to login
          expect(
            router.routerDelegate.currentConfiguration.uri.path,
            equals(AppRoutes.login),
          );

          await tester.pump(const Duration(seconds: 4));
        },
      );

      testWidgets('Should allow authenticated user to access protected route', (
        WidgetTester tester,
      ) async {
        // Create container with authenticated state
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockAuthenticatedAuthNotifier.new,
            ),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );

        // Navigate to a protected route. Use /garden (a placeholder screen)
        // rather than /profile — ProfileScreen performs network I/O on mount,
        // which a pure routing test should not exercise.
        router.go(AppRoutes.garden);
        await tester.pump(const Duration(milliseconds: 100));

        // The auth guard should allow an authenticated user through.
        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.garden),
        );

        // Drain the SplashScreen's pending timer (initial route) so it does
        // not outlive the widget tree.
        await tester.pump(const Duration(seconds: 4));
      });

      testWidgets('Should redirect authenticated user away from login screen', (
        WidgetTester tester,
      ) async {
        // Create container with authenticated state
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockAuthenticatedAuthNotifier.new,
            ),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );

        // Try to navigate to login while authenticated
        router.go(AppRoutes.login);
        await tester.pump(const Duration(milliseconds: 100));

        // Should be redirected to home
        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.home),
        );

        await tester.pump(const Duration(seconds: 4));
      });
    });

    group('Navigation Extension Tests', () {
      testWidgets('goToHome() should navigate to home', (
        WidgetTester tester,
      ) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockUnauthenticatedAuthNotifier.new,
            ),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(MaterialApp.router(routerConfig: router));

        final context = tester.element(find.byType(SplashScreen));
        context.goToHome();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.home),
        );

        await tester.pump(const Duration(seconds: 4));
      });

      testWidgets('goToCamera() should navigate to camera', (
        WidgetTester tester,
      ) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockUnauthenticatedAuthNotifier.new,
            ),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(MaterialApp.router(routerConfig: router));

        final context = tester.element(find.byType(SplashScreen));
        context.goToCamera();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.camera),
        );

        await tester.pump(const Duration(seconds: 4));
      });

      testWidgets('goToResults() should navigate to results with plant data', (
        WidgetTester tester,
      ) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockUnauthenticatedAuthNotifier.new,
            ),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);
        final testPlant = Plant(
          id: 'test-123',
          name: 'Test Plant',
          scientificName: 'Testus planticus',
          description: 'A test plant for routing tests',
          care: const ['Water regularly', 'Full sun'],
          imageUrl: 'https://example.com/plant.jpg',
          timestamp: DateTime.now(),
        );

        await tester.pumpWidget(MaterialApp.router(routerConfig: router));

        final context = tester.element(find.byType(SplashScreen));
        context.goToResults(testPlant);
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.results),
        );

        await tester.pump(const Duration(seconds: 4));
      });
    });

    group('Deep Link Tests', () {
      test('DeepLinks.home() should generate correct URI', () {
        final uri = DeepLinks.home();
        expect(uri.scheme, equals('plantcommunity'));
        expect(uri.path, equals(AppRoutes.home));
      });

      test('DeepLinks.results() should generate correct URI with plant ID', () {
        final uri = DeepLinks.results('plant-123');
        expect(uri.scheme, equals('plantcommunity'));
        expect(uri.path, equals(AppRoutes.results));
        expect(uri.queryParameters['id'], equals('plant-123'));
      });

      test('DeepLinks.garden() should generate correct URI', () {
        final uri = DeepLinks.garden();
        expect(uri.scheme, equals('plantcommunity'));
        expect(uri.path, equals(AppRoutes.garden));
      });

      test('DeepLinks.gardenBed() should generate correct URI with bed ID', () {
        final uri = DeepLinks.gardenBed('bed-456');
        expect(uri.scheme, equals('plantcommunity'));
        expect(uri.path, equals(AppRoutes.garden));
        expect(uri.queryParameters['bed_id'], equals('bed-456'));
      });
    });
  });
}

// ============================================
// MOCK AUTH SERVICES FOR TESTING
// ============================================
//
// These mocks extend AuthService and override the firebaseAuth getter to avoid
// triggering Firebase.initializeApp() at construction time.

class _MockFirebaseAuth extends Fake implements FirebaseAuth {
  @override
  User? get currentUser => null;

  @override
  Stream<User?> authStateChanges() => const Stream.empty();
}

class _MockUnauthenticatedAuthNotifier extends AuthService {
  @override
  FirebaseAuth get firebaseAuth => _MockFirebaseAuth();

  @override
  AuthState build() {
    return const AuthState(
      firebaseUser: null,
      jwtToken: null,
      isLoading: false,
    );
  }
}

class _MockAuthenticatedAuthNotifier extends AuthService {
  @override
  FirebaseAuth get firebaseAuth => _MockFirebaseAuth();

  @override
  AuthState build() {
    return const AuthState(
      firebaseUser: null,
      jwtToken: 'mock-jwt-token',
      isLoading: false,
    );
  }
}
