import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/core/routing/navigation_extensions.dart';
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
    testWidgets('Initial route should be splash screen',
        (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(
        MaterialApp.router(
          routerConfig: router,
        ),
      );

      // Initial route should be splash (/)
      expect(router.routerDelegate.currentConfiguration.uri.path, equals('/'));
    });

    testWidgets('Should navigate to home screen', (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(
        MaterialApp.router(
          routerConfig: router,
        ),
      );

      // Navigate to home
      router.go(AppRoutes.home);
      await tester.pumpAndSettle();

      expect(
        router.routerDelegate.currentConfiguration.uri.path,
        equals(AppRoutes.home),
      );
    });

    testWidgets('Should navigate to camera screen',
        (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(
        MaterialApp.router(
          routerConfig: router,
        ),
      );

      // Navigate to camera
      router.go(AppRoutes.camera);
      await tester.pumpAndSettle();

      expect(
        router.routerDelegate.currentConfiguration.uri.path,
        equals(AppRoutes.camera),
      );
    });

    testWidgets('Should navigate to results with plant data',
        (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
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

      await tester.pumpWidget(
        MaterialApp.router(
          routerConfig: router,
        ),
      );

      // Navigate to results with plant data
      router.go(AppRoutes.results, extra: testPlant);
      await tester.pumpAndSettle();

      expect(
        router.routerDelegate.currentConfiguration.uri.path,
        equals(AppRoutes.results),
      );
    });

    testWidgets('Should show error screen when navigating to results without plant data',
        (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(
        MaterialApp.router(
          routerConfig: router,
        ),
      );

      // Navigate to results WITHOUT plant data
      router.go(AppRoutes.results);
      await tester.pumpAndSettle();

      // Should show error screen
      expect(find.text('Oops! Something went wrong'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('Should handle invalid route', (WidgetTester tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(appRouterProvider);

      await tester.pumpWidget(
        MaterialApp.router(
          routerConfig: router,
        ),
      );

      // Navigate to invalid route
      router.go('/this-route-does-not-exist');
      await tester.pumpAndSettle();

      // Should show error screen
      expect(find.text('Oops! Something went wrong'), findsOneWidget);
    });

    group('Authentication Guard Tests', () {
      testWidgets('Should redirect unauthenticated user to login when accessing protected route',
          (WidgetTester tester) async {
        // Create container with unauthenticated state
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(
              routerConfig: router,
            ),
          ),
        );

        // Try to navigate to protected route (profile)
        router.go(AppRoutes.profile);
        await tester.pumpAndSettle();

        // Should be redirected to login
        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.login),
        );
      });

      testWidgets('Should allow authenticated user to access protected route',
          (WidgetTester tester) async {
        // Create container with authenticated state
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(_MockAuthenticatedAuthService.new),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(
              routerConfig: router,
            ),
          ),
        );

        // Navigate to protected route (profile)
        router.go(AppRoutes.profile);
        await tester.pumpAndSettle();

        // Should be allowed to access profile
        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.profile),
        );
      });

      testWidgets('Should redirect authenticated user away from login screen',
          (WidgetTester tester) async {
        // Create container with authenticated state
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(_MockAuthenticatedAuthService.new),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(
              routerConfig: router,
            ),
          ),
        );

        // Try to navigate to login while authenticated
        router.go(AppRoutes.login);
        await tester.pumpAndSettle();

        // Should be redirected to home
        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.home),
        );
      });
    });

    group('Navigation Extension Tests', () {
      testWidgets('goToHome() should navigate to home',
          (WidgetTester tester) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          MaterialApp.router(
            routerConfig: router,
          ),
        );

        final context = tester.element(find.byType(MaterialApp));
        context.goToHome();
        await tester.pumpAndSettle();

        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.home),
        );
      });

      testWidgets('goToCamera() should navigate to camera',
          (WidgetTester tester) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
          ],
        );
        addTearDown(container.dispose);

        final router = container.read(appRouterProvider);

        await tester.pumpWidget(
          MaterialApp.router(
            routerConfig: router,
          ),
        );

        final context = tester.element(find.byType(MaterialApp));
        context.goToCamera();
        await tester.pumpAndSettle();

        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.camera),
        );
      });

      testWidgets('goToResults() should navigate to results with plant data',
          (WidgetTester tester) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(_MockUnauthenticatedAuthService.new),
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

        await tester.pumpWidget(
          MaterialApp.router(
            routerConfig: router,
          ),
        );

        final context = tester.element(find.byType(MaterialApp));
        context.goToResults(testPlant);
        await tester.pumpAndSettle();

        expect(
          router.routerDelegate.currentConfiguration.uri.path,
          equals(AppRoutes.results),
        );
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
// NOTE: These mocks currently fail because they require Firebase initialization.
// See test/routing/TEST_STATUS.md for solutions.
//
// To enable these tests, add firebase_auth_mocks package and initialize Firebase.

class _MockUnauthenticatedAuthService extends AuthService {
  @override
  AuthState build() {
    return const AuthState(
      firebaseUser: null,
      jwtToken: null,
      isLoading: false,
    );
  }
}

class _MockAuthenticatedAuthService extends AuthService {
  @override
  AuthState build() {
    return const AuthState(
      firebaseUser: null,  // Would be User object in real scenario
      jwtToken: 'mock-jwt-token',
      isLoading: false,
    );
  }
}
