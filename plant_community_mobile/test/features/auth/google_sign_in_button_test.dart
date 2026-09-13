import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

/// Tests for the only sign-in path that can currently complete.
///
/// Email/password cannot: the backend 403s any Firebase token whose
/// `email_verified` claim is false unless the provider is in
/// `_TRUSTED_FIREBASE_PROVIDERS` (`{google.com, apple.com}`), and this app
/// never calls `sendEmailVerification()`. The server half of that is asserted
/// in `backend/apps/users/tests/test_firebase_auth.py`
/// (`FirebaseTrustedProviderTestCase`); this is the client half.
void main() {
  Future<FakeAuthService> pumpButton(
    WidgetTester tester, {
    bool enabled = true,
  }) async {
    final fake = FakeAuthService(loggedIn: false);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authServiceProvider.overrideWith(() => fake)],
        child: MaterialApp(
          home: Scaffold(
            body: Center(child: GoogleSignInButton(enabled: enabled)),
          ),
        ),
      ),
    );
    return fake;
  }

  testWidgets('tapping it actually calls signInWithGoogle', (tester) async {
    final fake = await pumpButton(tester);
    expect(fake.googleSignInCalls, 0);

    await tester.tap(find.text('Continue with Google'));
    await tester.pump();

    // The assertion that matters: a button that renders but is wired to
    // nothing is exactly the shape todo 384 was filed about.
    expect(fake.googleSignInCalls, 1);
  });

  testWidgets('a failure is shown on the form, not swallowed', (tester) async {
    final fake = await pumpButton(tester);
    fake.googleSignInError = AuthException(
      'That sign-in method is not enabled for this app.',
    );

    await tester.tap(find.text('Continue with Google'));
    await tester.pump();

    // The exact message a disabled Google provider produces. It has to reach
    // the user, or a console toggle is indistinguishable from a dead button.
    expect(
      find.text('That sign-in method is not enabled for this app.'),
      findsOneWidget,
    );
  });

  testWidgets('it is inert while the email form is submitting', (tester) async {
    final fake = await pumpButton(tester, enabled: false);

    await tester.tap(find.text('Continue with Google'), warnIfMissed: false);
    await tester.pump();

    expect(fake.googleSignInCalls, 0);
  });
}
