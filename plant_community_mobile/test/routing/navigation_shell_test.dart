import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/features/auth/register_screen.dart';
import 'package:plant_community_mobile/features/camera/camera_screen.dart';
import 'package:plant_community_mobile/features/collection/collection_screen.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/home/home_page.dart';
import 'package:plant_community_mobile/features/profile/profile_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../features/forum/support/forum_test_support.dart';

/// Longer than the 300ms fade on `_buildPageWithTransition`. At the 100ms
/// used elsewhere in test/routing the shell has not mounted yet and every
/// `find.byType(NavigationBar)` comes back empty -- which reads as "no nav
/// bar" rather than "not yet". Deliberately not `pumpAndSettle`:
/// docs/rules/flutter.md forbids it once a CachedNetworkImage is mounted,
/// and the forum feed mounts them.
const _settle = Duration(milliseconds: 400);

/// Advance past a route transition.
///
/// TWO pumps, not one: `pump(duration)` renders a single frame, and go_router
/// mounts the shell on the frame AFTER the navigation commits. With one pump
/// `find.byType(NavigationBar)` returns empty, which reads as "there is no nav
/// bar" when the truth is "not yet" -- the exact false negative these tests
/// exist to catch.
Future<void> settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(_settle);
}

/// Reachability tests for the navigation shell (todo 384).
///
/// These assert what `find.text` cannot. Todo 383 item 11 recorded the lesson
/// the hard way: a widget test passed for months on a screen no user could
/// open, because `find.text` searches the widget TREE, not the screen, and says
/// nothing about whether anything navigates there. Every assertion here drives
/// a real tap on the real router and then checks where that landed — the thing
/// a user's thumb actually changes. See [GoRouterHarness.path] for why that is
/// `last.matchedLocation` and not the `uri.path` used elsewhere in this
/// directory.
///
/// The companion check is `scripts/check_flutter_route_reachability.py`, which
/// is static; this is the dynamic half.
void main() {
  /// Pump the PRODUCTION router — not a hand-built one. A stub router would
  /// prove only that the test's own wiring works.
  Future<GoRouterHarness> pumpShell(
    WidgetTester tester, {
    required bool loggedIn,
  }) async {
    final container = ProviderContainer(
      overrides: [
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: loggedIn),
        ),
        forumApiProvider.overrideWithValue(FakeForumApi()),
        forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
        // Signed in, ProfileScreen fetches GET /auth/user/. Unfaked it
        // 401s and Riverpod 3.x reschedules the failed fetch forever,
        // failing the test with a pending timer rather than an assertion
        // (docs/rules/flutter.md: every provider a mounted screen reads
        // must succeed).
        userProfileServiceProvider.overrideWith(
          () => FakeUserProfileService(username: 'tester'),
        ),
      ],
    );
    addTearDown(container.dispose);
    // appRouterProvider is autoDispose: hold the subscription BEFORE reading,
    // or the router is torn down and its refreshListenable never fires.
    container.listen(appRouterProvider, (_, _) {});
    final router = container.read(appRouterProvider);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );

    // Skip the splash animation straight to the shell.
    router.go(AppRoutes.home);
    await settle(tester);
    return GoRouterHarness(router);
  }

  /// Tap a shell tab by its icon, scoped to the NavigationBar so an identically
  /// named AppBar title (ProfileScreen's is literally 'Profile') can't be hit
  /// by accident.
  Future<void> tapTab(WidgetTester tester, IconData icon) async {
    final target = find.descendant(
      of: find.byType(NavigationBar),
      matching: find.byIcon(icon),
    );
    expect(
      target,
      findsOneWidget,
      reason:
          'no NavigationBar destination showing $icon — a user cannot '
          'switch to that tab',
    );
    await tester.tap(target);
    await settle(tester);
  }

  group('navigation shell reachability', () {
    testWidgets('the shell renders a destination for every branch', (
      tester,
    ) async {
      await pumpShell(tester, loggedIn: false);

      expect(find.byType(NavigationBar), findsOneWidget);
      // Guards against a branch being added to the router with no way in.
      expect(
        find.byType(NavigationDestination),
        findsNWidgets(MainShell.destinations.length),
      );

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('every top-level destination is reachable signed OUT', (
      tester,
    ) async {
      final h = await pumpShell(tester, loggedIn: false);
      expect(h.path, AppRoutes.home);
      expect(find.byType(HomePage), findsOneWidget);

      await tapTab(tester, Icons.eco_outlined);
      expect(h.path, AppRoutes.collection);
      expect(find.byType(CollectionScreen), findsOneWidget);

      await tapTab(tester, Icons.forum_outlined);
      expect(h.path, AppRoutes.forum);
      expect(find.byType(ForumScreen), findsOneWidget);

      await tapTab(tester, Icons.person_outline);
      expect(h.path, AppRoutes.profile);
      expect(find.byType(ProfileScreen), findsOneWidget);

      await tapTab(tester, Icons.home_outlined);
      expect(h.path, AppRoutes.home);

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('every top-level destination is reachable signed IN', (
      tester,
    ) async {
      final h = await pumpShell(tester, loggedIn: true);

      await tapTab(tester, Icons.eco_outlined);
      expect(h.path, AppRoutes.collection);

      await tapTab(tester, Icons.forum_outlined);
      expect(h.path, AppRoutes.forum);

      // Signed in this must NOT bounce to /login either.
      await tapTab(tester, Icons.person_outline);
      expect(h.path, AppRoutes.profile);

      await tester.pump(const Duration(seconds: 4));
    });
  });

  group('the Identify centre action', () {
    testWidgets('opens the camera and can be left without force-quitting', (
      tester,
    ) async {
      final h = await pumpShell(tester, loggedIn: false);

      // Land on a tab that is NOT Home, so the pop target is unambiguous.
      await tapTab(tester, Icons.forum_outlined);
      expect(h.path, AppRoutes.forum);

      await tester.tap(find.byType(FloatingActionButton));
      await settle(tester);
      expect(h.path, AppRoutes.camera);
      expect(find.byType(CameraScreen), findsOneWidget);

      // Todo 384 finding 5: Home used `context.go`, which REPLACES the stack,
      // so canPop() was false, the bare AppBar drew no back button and
      // force-quitting was the only way out. `push` is what makes this pass.
      expect(
        h.router.canPop(),
        isTrue,
        reason: 'the camera must be poppable or the user is stranded',
      );

      h.router.pop();
      await settle(tester);

      // Back on the shell, on the tab we left from — not reset to Home.
      expect(h.path, AppRoutes.forum);
      expect(find.byType(NavigationBar), findsOneWidget);

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('the camera covers the nav bar while capturing', (
      tester,
    ) async {
      final h = await pumpShell(tester, loggedIn: false);

      await tester.tap(find.byType(FloatingActionButton));
      await settle(tester);

      expect(h.path, AppRoutes.camera);
      // /camera sits on the ROOT navigator, outside every branch, so capture
      // is full-screen rather than framed by a tab bar.
      expect(find.byType(NavigationBar), findsNothing);

      await tester.pump(const Duration(seconds: 4));
    });
  });

  group('sign-in is reachable from a cold launch (todo 384 AC 4)', () {
    testWidgets('Profile tab -> Sign in reaches the real LoginScreen', (
      tester,
    ) async {
      final h = await pumpShell(tester, loggedIn: false);

      await tapTab(tester, Icons.person_outline);
      expect(h.path, AppRoutes.profile);

      // The signed-out profile must offer sign-in rather than the old
      // "Failed to load profile" + permanently-failing Retry.
      expect(find.text('Failed to load profile'), findsNothing);

      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await settle(tester);

      expect(h.path, AppRoutes.login);
      // Not the PlaceholderScreen that used to say "Login screen coming soon".
      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.textContaining('coming soon'), findsNothing);

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('Profile tab -> Create an account reaches RegisterScreen', (
      tester,
    ) async {
      final h = await pumpShell(tester, loggedIn: false);

      await tapTab(tester, Icons.person_outline);
      await tester.tap(
        find.widgetWithText(OutlinedButton, 'Create an account'),
      );
      await settle(tester);

      expect(h.path, AppRoutes.register);
      expect(find.byType(RegisterScreen), findsOneWidget);

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('sign-in and register link to each other', (tester) async {
      final h = await pumpShell(tester, loggedIn: false);

      await tapTab(tester, Icons.person_outline);
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await settle(tester);
      expect(h.path, AppRoutes.login);

      await tester.tap(find.textContaining("Don't have an account"));
      await settle(tester);
      expect(h.path, AppRoutes.register);

      // ensureVisible, not a bare tap: flutter_test's default surface is
      // 800x600, SHORTER than any phone it ships to, and the register form is
      // tall enough that this link sits at y=632 -- off the test viewport but
      // perfectly visible on a 667pt iPhone SE. Both screens are
      // SingleChildScrollViews, so scrolling to it is what a real thumb does.
      // Without this the test fails as "still on /register", which reads as a
      // broken link rather than an unscrolled one.
      final signInLink = find.textContaining('Already have an account');
      await tester.ensureVisible(signInLink);
      await tester.pump();
      await tester.tap(signInLink);
      await settle(tester);
      expect(h.path, AppRoutes.login);

      await tester.pump(const Duration(seconds: 4));
    });

    testWidgets('both auth screens offer the Google path', (tester) async {
      // Google is not a convenience here, it is the only path that reaches a
      // signed-in state: the backend 403s an unverified email/password token
      // and this app sends no verification mail. If either screen loses this
      // button, that screen becomes a dead end.
      final h = await pumpShell(tester, loggedIn: false);

      await tapTab(tester, Icons.person_outline);
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await settle(tester);
      expect(h.path, AppRoutes.login);
      expect(find.text('Continue with Google'), findsOneWidget);

      await tester.tap(find.textContaining("Don't have an account"));
      await settle(tester);
      expect(h.path, AppRoutes.register);
      expect(find.text('Continue with Google'), findsOneWidget);

      await tester.pump(const Duration(seconds: 4));
    });
  });

  group('Settings survived losing the Home FAB', () {
    testWidgets('Settings is reachable from the Profile tab', (tester) async {
      final h = await pumpShell(tester, loggedIn: false);

      await tapTab(tester, Icons.person_outline);
      await tester.tap(find.byIcon(Icons.settings));
      await settle(tester);

      // The Home FAB used to be the ONLY way to open Settings; the shell's
      // Identify FAB replaced it, so Profile has to carry it now.
      expect(h.path, AppRoutes.settings);

      await tester.pump(const Duration(seconds: 4));
    });
  });

  group('the Identify FAB does not sit on the nav bar', () {
    // The FAB is a fixed 56px and each destination cell is width/4, so the
    // NARROWER the phone the more of its neighbours the FAB covers. 320pt is
    // the narrowest width iOS ships. Under the `centerDocked` this shell was
    // written with, these failed by 11.3px at 390pt and 20px at 320pt, on two
    // of the four tabs -- with an even number of destinations the centre of
    // the screen is a boundary between two of them, not a gap.
    //
    // Geometry only, no text: the M3 selection pill is a fixed 64x32, so this
    // assertion is font-independent. That matters, because flutter_test's
    // default font is MONOSPACE at 12.25px per character and inflates every
    // label -- measuring anything text-shaped here without first loading the
    // real Geist face via FontLoader produces confident, wrong numbers.
    for (final width in <double>[320.0, 390.0, 428.0]) {
      testWidgets(
        'the Identify FAB never covers a tab selection indicator '
        '@${width.toInt()}pt',
        (tester) async {
          tester.view.physicalSize = Size(width, 844) * 3;
          tester.view.devicePixelRatio = 3.0;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);

          await pumpShell(tester, loggedIn: false);

          final fab = tester.getRect(find.byType(FloatingActionButton));
          final indicators = find.byType(NavigationIndicator);
          // A missing indicator would make the loop below vacuously pass.
          expect(indicators, findsNWidgets(MainShell.destinations.length));

          for (var i = 0; i < MainShell.destinations.length; i++) {
            expect(
              tester.getRect(indicators.at(i)).overlaps(fab),
              isFalse,
              reason:
                  'at ${width.toInt()}pt the Identify FAB covers part of the '
                  '"${MainShell.destinations[i].label}" tab selection '
                  'indicator, so that tab looks clipped when selected',
            );
          }

          await tester.pump(const Duration(seconds: 4));
        },
      );
    }
  });
}

/// Thin holder so assertions read as `h.path` rather than a four-property chain.
class GoRouterHarness {
  GoRouterHarness(this.router);

  final GoRouter router;

  /// Where the user actually is -- including a route reached by `push`.
  ///
  /// NOT `currentConfiguration.uri.path`, which the rest of test/routing uses.
  /// That reports only the underlying LOCATION: after
  /// `go('/forum')` then `push('/login')` it still reads `/forum`, while the
  /// login screen is on screen and `canPop()` is true. Verified directly
  /// against go_router 17.2.3 rather than assumed. Asserting on `uri.path`
  /// here would have silently passed every push test for the wrong reason --
  /// or, as it did first time round, failed one that was actually working.
  String get path =>
      router.routerDelegate.currentConfiguration.last.matchedLocation;
}
