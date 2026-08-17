import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_topics_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../features/forum/support/forum_test_support.dart';

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

    testWidgets('forumBoard route builds ForumTopicsScreen', (tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
          forumApiProvider.overrideWithValue(FakeForumApi()),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
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

      router.go('/forum/boards/general', extra: 'General');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.byType(ForumTopicsScreen), findsOneWidget);
      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('forumTopic route builds ForumThreadScreen', (tester) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
          forumApiProvider.overrideWithValue(
            FakeForumApi()..topicDetail = topicDetail(),
          ),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
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

      router.go('/forum/topics/10', extra: 'A topic');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.byType(ForumThreadScreen), findsOneWidget);
      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('forumCompose route builds ForumComposerScreen with args', (
      tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(
            _MockUnauthenticatedAuthNotifier.new,
          ),
          forumApiProvider.overrideWithValue(FakeForumApi()),
          forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
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

      router.go(
        '/forum/compose',
        extra: const ForumComposeArgs.reply(topicId: 10),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.byType(ForumComposerScreen), findsOneWidget);
      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets(
      'posting a reply on a multi-page thread makes it visible without a '
      'manual refresh',
      (tester) async {
        // Todo 291: a new reply is oldest-first-ordered onto the LAST cursor
        // page. Page 1's opening post is the only one build() ever fetches;
        // page 2's post ("Page two reply") must appear after the FAB → compose
        // → post round trip, with no manual refresh action from the test.
        final page1 = CursorPage(
          items: [
            post(id: 1, body: const [ParagraphBlock('Opening post')]),
          ],
          next: 'https://api/forum/topics/10/posts/?cursor=p2',
        );
        final page2 = CursorPage(
          items: [
            post(id: 2, body: const [ParagraphBlock('Page two reply')]),
          ],
        );
        final api = FakeForumApi()
          ..topicDetail = topicDetail()
          ..postPages = [page1, page2];

        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockAuthenticatedAuthNotifier.new,
            ),
            forumApiProvider.overrideWithValue(api),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          ],
        );
        addTearDown(container.dispose);
        final router = container.read(appRouterProvider);
        // appRouterProvider is autoDispose (production keeps it alive via
        // ref.watch in main.dart). A bare container.read has no persistent
        // subscription, so Riverpod can dispose it between pump cycles —
        // then a SECOND navigation's redirect callback (which reads
        // authServiceProvider through the disposed Ref) throws
        // "Cannot use the Ref of appRouterProvider after it has been
        // disposed", silently landing on the router's error screen. This
        // test is the first in the file to navigate twice, which is what
        // exposes it. container.listen keeps it alive, matching main.dart's
        // ref.watch.
        container.listen(appRouterProvider, (_, _) {});
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );

        router.go('/forum/topics/10', extra: 'A topic');
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // Page 2's reply is not visible yet — build() only fetched page 1.
        expect(find.textContaining('Page two reply'), findsNothing);

        await tester.tap(find.widgetWithText(FloatingActionButton, 'Reply'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        await tester.enterText(find.byType(TextField), 'my reply');
        await tester.pump();
        await tester.tap(find.widgetWithText(FilledButton, 'Post'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // Back on the thread screen: the reply — which lives on page 2 — is
        // now visible with no manual refresh action from this test.
        expect(find.textContaining('Page two reply'), findsOneWidget);

        await tester.pump(const Duration(seconds: 4));
      },
    );

    testWidgets(
      'editing a post updates it in place without a manual refresh (todo 292)',
      (tester) async {
        final api = FakeForumApi()
          ..topicDetail = topicDetail()
          ..posts = CursorPage(
            items: [
              post(
                id: 1,
                body: const [ParagraphBlock('Original body')],
                canEdit: true,
              ),
            ],
          );

        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockAuthenticatedAuthNotifier.new,
            ),
            forumApiProvider.overrideWithValue(api),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          ],
        );
        addTearDown(container.dispose);
        // See the reply round-trip test above for why this listen is needed:
        // appRouterProvider is autoDispose and this test navigates twice.
        container.listen(appRouterProvider, (_, _) {});
        final router = container.read(appRouterProvider);
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );

        router.go('/forum/topics/10', extra: 'A topic');
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));
        expect(find.textContaining('Original body'), findsOneWidget);

        await tester.tap(find.byIcon(Icons.more_vert));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Edit'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // Composer opened pre-filled from the existing body.
        expect(find.text('Original body'), findsOneWidget);
        await tester.enterText(find.byType(TextField), 'Edited body');
        await tester.pump();
        await tester.tap(find.widgetWithText(FilledButton, 'Save'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // Back on the thread screen: the edit is visible with no manual
        // refresh action from this test (TopicPosts.applyEditedPost).
        expect(find.textContaining('Edited body'), findsOneWidget);
        expect(find.textContaining('Original body'), findsNothing);
        expect(api.editPostKeys, hasLength(1));

        await tester.pump(const Duration(seconds: 4));
      },
    );

    testWidgets(
      'tapping Done on a pending edit does not throw (code review — '
      'the edit route is pushed as <ForumPost>, not <bool> like reply/topic)',
      (tester) async {
        final api = FakeForumApi()
          ..topicDetail = topicDetail()
          ..posts = CursorPage(
            items: [
              post(
                id: 1,
                body: const [ParagraphBlock('Original body')],
                canEdit: true,
              ),
            ],
          )
          ..editStatus = ForumModerationStatus.pending;

        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWith(
              _MockAuthenticatedAuthNotifier.new,
            ),
            forumApiProvider.overrideWithValue(api),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          ],
        );
        addTearDown(container.dispose);
        container.listen(appRouterProvider, (_, _) {});
        final router = container.read(appRouterProvider);
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );

        router.go('/forum/topics/10', extra: 'A topic');
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        await tester.tap(find.byIcon(Icons.more_vert));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Edit'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        await tester.enterText(find.byType(TextField), 'Edited body');
        await tester.pump();
        await tester.tap(find.widgetWithText(FilledButton, 'Save'));
        await tester.pumpAndSettle();

        expect(find.textContaining('awaiting moderation'), findsOneWidget);

        // The regression: popping this route used to always pop `false` (a
        // bool), which throws when the route was pushed as <ForumPost>
        // (edit) rather than <bool> (reply/topic). Must complete cleanly —
        // no uncaught exception — and land back on the thread screen with
        // the pre-edit body still showing (a pending edit never applies
        // locally; only the moderation-approved version does).
        await tester.tap(find.widgetWithText(FilledButton, 'Done'));
        await tester.pumpAndSettle();

        expect(tester.takeException(), isNull);
        expect(find.byType(ForumThreadScreen), findsOneWidget);
        expect(find.textContaining('Original body'), findsOneWidget);

        await tester.pump(const Duration(seconds: 4));
      },
    );

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
