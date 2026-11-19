import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/features/auth/register_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

/// "Continue with Apple" on the sign-in and register screens (todo 717):
/// App Store Guideline 4.8 asks for it on iOS, where Google sign-in is
/// offered. iOS only: hidden on Android (owner decision 2026-11-19).
void main() {
  Future<FakeAuthService> pumpScreen(
    WidgetTester tester,
    Widget screen, {
    required TargetPlatform platform,
    Brightness brightness = Brightness.light,
  }) async {
    debugDefaultTargetPlatformOverride = platform;
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final fake = FakeAuthService(loggedIn: false);
    // A router: on success the button calls dismissAfterAuth, which reads
    // GoRouter.of(context), as the Google button does.
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, _) => screen),
        GoRoute(
          path: '/profile',
          builder: (_, _) => const Scaffold(body: Text('PROFILE')),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authServiceProvider.overrideWith(() => fake)],
        child: MaterialApp.router(
          theme: ThemeData(brightness: brightness),
          routerConfig: router,
        ),
      ),
    );
    return fake;
  }

  Finder appleButton() =>
      find.widgetWithText(FilledButton, AppleSignInButton.label);
  Finder googleText() => find.text('Continue with Google');

  /// Apple's button style: the Apple logo, the HIG's label, black on a
  /// light screen, above Google and at least as large.
  void expectAppleStyle(WidgetTester tester, {required Color background}) {
    expect(appleButton(), findsOneWidget);
    expect(
      find.descendant(of: appleButton(), matching: find.byIcon(Icons.apple)),
      findsOneWidget,
    );
    final style = tester.widget<FilledButton>(appleButton()).style!;
    expect(style.backgroundColor!.resolve({}), background);
    final appleRect = tester.getRect(appleButton());
    final googleRect = tester.getRect(
      find.ancestor(of: googleText(), matching: find.byType(OutlinedButton)),
    );
    expect(appleRect.top, lessThan(googleRect.top), reason: 'above Google');
    expect(appleRect.height, greaterThanOrEqualTo(googleRect.height));
    expect(appleRect.width, greaterThanOrEqualTo(googleRect.width));
  }

  group('login screen', () {
    testWidgets('iOS shows Continue with Apple in Apple\'s style, and a tap '
        'signs in with Apple without the consent flag', (tester) async {
      final fake = await pumpScreen(
        tester,
        const LoginScreen(),
        platform: TargetPlatform.iOS,
      );

      expectAppleStyle(tester, background: Colors.black);
      expect(tester.widget<FilledButton>(appleButton()).onPressed, isNotNull);

      await tester.tap(appleButton());
      await tester.pumpAndSettle();

      expect(fake.appleSignInCalls, 1);
      expect(fake.appleSignInAcceptedTerms, [false]);
      expect(fake.googleSignInCalls, 0);
      debugDefaultTargetPlatformOverride = null;
    });

    testWidgets('a dark screen gets the white Apple button', (tester) async {
      await pumpScreen(
        tester,
        const LoginScreen(),
        platform: TargetPlatform.iOS,
        brightness: Brightness.dark,
      );

      expectAppleStyle(tester, background: Colors.white);
      debugDefaultTargetPlatformOverride = null;
    });

    testWidgets('an Apple failure is shown on the form', (tester) async {
      final fake = await pumpScreen(
        tester,
        const LoginScreen(),
        platform: TargetPlatform.iOS,
      );
      fake.appleSignInError = AuthException(appleSignInFailedMessage);

      await tester.tap(appleButton());
      await tester.pump();

      expect(find.text(appleSignInFailedMessage), findsOneWidget);
      debugDefaultTargetPlatformOverride = null;
    });

    testWidgets('Android hides the Apple button', (tester) async {
      await pumpScreen(
        tester,
        const LoginScreen(),
        platform: TargetPlatform.android,
      );

      expect(find.text(AppleSignInButton.label), findsNothing);
      expect(find.byIcon(Icons.apple), findsNothing);
      expect(googleText(), findsOneWidget);
      debugDefaultTargetPlatformOverride = null;
    });
  });

  group('register screen', () {
    testWidgets('iOS shows Continue with Apple in Apple\'s style, disabled '
        'until the consent box is ticked, then signs up with consent', (
      tester,
    ) async {
      final fake = await pumpScreen(
        tester,
        const RegisterScreen(),
        platform: TargetPlatform.iOS,
      );

      expectAppleStyle(tester, background: Colors.black);
      expect(tester.widget<FilledButton>(appleButton()).onPressed, isNull);

      await tester.tap(find.byType(Checkbox));
      await tester.pump();
      expect(tester.widget<FilledButton>(appleButton()).onPressed, isNotNull);

      await tester.tap(appleButton());
      await tester.pumpAndSettle();

      expect(fake.appleSignInCalls, 1);
      expect(fake.appleSignInAcceptedTerms, [true]);
      debugDefaultTargetPlatformOverride = null;
    });

    testWidgets('Android hides the Apple button', (tester) async {
      await pumpScreen(
        tester,
        const RegisterScreen(),
        platform: TargetPlatform.android,
      );

      expect(find.text(AppleSignInButton.label), findsNothing);
      expect(googleText(), findsOneWidget);
      debugDefaultTargetPlatformOverride = null;
    });
  });

  test('Apple sign-in is offered on iOS only', () {
    expect(appleSignInSupported(TargetPlatform.iOS), isTrue);
    for (final platform in [
      TargetPlatform.android,
      TargetPlatform.macOS,
      TargetPlatform.fuchsia,
      TargetPlatform.linux,
      TargetPlatform.windows,
    ]) {
      expect(appleSignInSupported(platform), isFalse, reason: '$platform');
    }
  });
}
