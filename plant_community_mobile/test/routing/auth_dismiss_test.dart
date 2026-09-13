import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/features/auth/register_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/profile/profile_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

import '../features/forum/support/forum_test_support.dart';

const _settle = Duration(milliseconds: 400);

Future<void> settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(_settle);
}

/// Signing in must actually LEAVE the sign-in screen.
///
/// Reported against TestFlight build 7: "it logged me in, but I had to tap the
/// back arrow to find out I was logged in. The UI did not move after logging in
/// with google so I was unsure."
///
/// Two plausible-looking mechanisms do NOT work here, which is why these drive
/// the real router instead of asserting on a widget tree:
///
///  * the redirect never sees `/login`. It matches on `state.uri.path`, and a
///    PUSHED auth screen leaves the location at `/profile` — verified by
///    instrumenting the production redirect: on the auth-change refresh,
///    `uri.path`, `matchedLocation` and `fullPath` were all `/profile`.
///  * `context.pop()` reports `canPop() == true` and then changes nothing,
///    because the auth flip's refresh re-parses first.
void main() {
  Future<(GoRouter, FakeAuthService)> pumpTo(
    WidgetTester tester,
    String route, {
    bool viaPushFromProfile = true,
  }) async {
    final fake = FakeAuthService(loggedIn: false);
    final container = ProviderContainer(
      overrides: [
        authServiceProvider.overrideWith(() => fake),
        forumApiProvider.overrideWithValue(FakeForumApi()),
        forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
        userProfileServiceProvider
            .overrideWith(() => FakeUserProfileService(username: 'tester')),
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

    if (viaPushFromProfile) {
      // The real path a user takes, not a synthetic deep link.
      router.go(AppRoutes.home);
      await settle(tester);
      await tester.tap(
        find.descendant(
          of: find.byType(NavigationBar),
          matching: find.byIcon(Icons.person_outline),
        ),
      );
      await settle(tester);
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await settle(tester);
      if (route == AppRoutes.register) {
        await tester.tap(find.textContaining("Don't have an account"));
        await settle(tester);
      }
    } else {
      router.go(route);
      await settle(tester);
    }
    return (router, fake);
  }

  testWidgets('Google sign-in leaves the sign-in screen', (tester) async {
    final (router, _) = await pumpTo(tester, AppRoutes.login);
    expect(find.byType(LoginScreen), findsOneWidget);
    // The push is what breaks the redirect; assert the shape the bug needs.
    expect(router.routerDelegate.currentConfiguration.uri.path, '/profile');

    await tester.tap(find.text('Continue with Google'));
    await settle(tester);

    expect(
      find.byType(LoginScreen),
      findsNothing,
      reason: 'signed in, but still looking at the sign-in form',
    );
    // Back where they started, now signed in — not dumped somewhere else.
    expect(find.byType(ProfileScreen), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);

    await tester.pump(const Duration(seconds: 4));
  });

  testWidgets('Google sign-in leaves the register screen too', (tester) async {
    await pumpTo(tester, AppRoutes.register);
    expect(find.byType(RegisterScreen), findsOneWidget);

    await tester.tap(find.text('Continue with Google'));
    await settle(tester);

    expect(find.byType(RegisterScreen), findsNothing);
    expect(find.byType(ProfileScreen), findsOneWidget);

    await tester.pump(const Duration(seconds: 4));
  });

  testWidgets('arriving by redirect (not push) lands on the Profile tab', (
    tester,
  ) async {
    // Here the location really IS /login, so there is nothing to return to.
    final (router, _) = await pumpTo(
      tester,
      AppRoutes.login,
      viaPushFromProfile: false,
    );
    expect(router.routerDelegate.currentConfiguration.uri.path, '/login');

    await tester.tap(find.text('Continue with Google'));
    // TWO transitions chain here, unlike the pushed cases: the redirect moves
    // /login -> /home, and the dismissal runs too. One `settle` lands mid-flight
    // and reports "LoginScreen still present", which reads as a broken fix when
    // the truth is "not yet" -- the same false negative `_settle` guards against
    // in navigation_shell_test.dart.
    await settle(tester);
    await tester.pump(const Duration(seconds: 1));

    expect(find.byType(LoginScreen), findsNothing);
    // Profile, not home: someone who just signed in is there to BE signed in.
    // Build 8 landed on Home here and the owner asked for Profile.
    expect(
      router.routerDelegate.currentConfiguration.uri.path,
      AppRoutes.profile,
    );
    expect(find.byType(ProfileScreen), findsOneWidget);

    await tester.pump(const Duration(seconds: 4));
  });
}
