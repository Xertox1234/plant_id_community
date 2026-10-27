import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/features/auth/register_screen.dart';
import 'package:plant_community_mobile/features/auth/verify_email_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

/// The "Check your email" state of the sign-in and register screens (todo
/// 660): an unverified email/password account used to land, silently, on a
/// signed-out Profile.
void main() {
  late _StubAuthService auth;

  Future<GoRouter> pump(WidgetTester tester, String initial) async {
    auth = _StubAuthService();
    final router = GoRouter(
      initialLocation: initial,
      routes: [
        GoRoute(
          path: AppRoutes.login,
          builder: (context, state) => const LoginScreen(),
        ),
        GoRoute(
          path: AppRoutes.register,
          builder: (context, state) => const RegisterScreen(),
        ),
        GoRoute(
          path: AppRoutes.profile,
          builder: (context, state) => const Scaffold(body: Text('PROFILE')),
        ),
      ],
    );
    addTearDown(router.dispose);
    final container = ProviderContainer(
      overrides: [authServiceProvider.overrideWith(() => auth)],
    );
    addTearDown(container.dispose);
    // authServiceProvider is autoDispose and the screens only `read` it: hold
    // a listener, as main.dart does in the app, so there is one notifier.
    container.listen(authServiceProvider, (_, _) {});
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
    return router;
  }

  Future<void> signInUnverified(WidgetTester tester) async {
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Email'),
      'ada@example.com',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Password'),
      'secret1',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();
  }

  testWidgets('an unverified sign-in shows "Check your email", not a '
      'signed-out Profile', (tester) async {
    await pump(tester, AppRoutes.login);

    await signInUnverified(tester);

    expect(find.byType(VerifyEmailPanel), findsOneWidget);
    expect(find.text('Check your email'), findsOneWidget);
    expect(find.textContaining('ada@example.com'), findsOneWidget);
    expect(find.text('PROFILE'), findsNothing);
  });

  testWidgets('registering shows "Check your email"', (tester) async {
    await pump(tester, AppRoutes.register);

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Display name'),
      'Ada',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Email'),
      'ada@example.com',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Password'),
      'secret1',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Confirm password'),
      'secret1',
    );
    await tester.ensureVisible(
      find.widgetWithText(FilledButton, 'Create account'),
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    expect(auth.registered, 1);
    expect(find.byType(VerifyEmailPanel), findsOneWidget);
    expect(find.text('PROFILE'), findsNothing);
  });

  testWidgets('Resend sends the mail again and says so', (tester) async {
    await pump(tester, AppRoutes.login);
    await signInUnverified(tester);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Resend email'));
    await tester.pumpAndSettle();

    expect(auth.resends, 1);
    expect(find.text(verificationEmailSentMessage), findsOneWidget);
  });

  testWidgets('"I\'ve verified" before the link is opened keeps the panel '
      'and says why', (tester) async {
    await pump(tester, AppRoutes.login);
    await signInUnverified(tester);

    await tester.tap(find.widgetWithText(FilledButton, "I've verified"));
    await tester.pumpAndSettle();

    expect(auth.confirms, 1);
    expect(find.text(emailStillUnverifiedMessage), findsOneWidget);
    expect(find.byType(VerifyEmailPanel), findsOneWidget);
  });

  testWidgets('"I\'ve verified" once the link is opened signs in and leaves '
      'for Profile', (tester) async {
    await pump(tester, AppRoutes.login);
    await signInUnverified(tester);
    auth.verified = true;

    await tester.tap(find.widgetWithText(FilledButton, "I've verified"));
    await tester.pumpAndSettle();

    expect(find.byType(VerifyEmailPanel), findsNothing);
    expect(find.text('PROFILE'), findsOneWidget);
  });

  testWidgets('"Use a different account" signs out and shows the form again', (
    tester,
  ) async {
    await pump(tester, AppRoutes.login);
    await signInUnverified(tester);

    await tester.tap(find.text('Use a different account'));
    await tester.pumpAndSettle();

    expect(auth.signOuts, 1);
    expect(find.byType(VerifyEmailPanel), findsNothing);
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
  });
}

class _StubAuthService extends AuthService {
  /// What the reload in "I've verified" finds.
  bool verified = false;
  int registered = 0;
  int resends = 0;
  int confirms = 0;
  int signOuts = 0;

  final User _user = _FakeUser();

  @override
  AuthState build() => const AuthState();

  @override
  Future<bool> signInWithEmailPassword(String email, String password) async {
    state = AuthState(firebaseUser: _user, emailVerificationRequired: true);
    return true;
  }

  @override
  Future<bool> registerWithEmailPassword({
    required String email,
    required String password,
    required String displayName,
  }) async {
    registered++;
    state = AuthState(firebaseUser: _user, emailVerificationRequired: true);
    return true;
  }

  @override
  Future<void> resendVerificationEmail() async => resends++;

  @override
  Future<bool> confirmEmailVerified() async {
    confirms++;
    if (!verified) {
      state = AuthState(
        firebaseUser: _user,
        error: emailStillUnverifiedMessage,
        emailVerificationRequired: true,
      );
      return false;
    }
    state = AuthState(firebaseUser: _user, jwtToken: 'django-jwt');
    return true;
  }

  @override
  Future<void> signOut() async {
    signOuts++;
    state = const AuthState();
  }
}

class _FakeUser implements User {
  @override
  String get uid => 'ada';

  @override
  String? get email => 'ada@example.com';

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
