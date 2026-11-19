import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

/// "Forgot password?" on the sign-in screen (todo 704, audit H7).
///
/// The notifier's real [AuthService.sendPasswordResetEmail] runs: only its
/// Firebase seam is faked, so the test reaches the Firebase call itself.
void main() {
  Future<_ResetRecordingFirebaseAuth> pumpLogin(
    WidgetTester tester, {
    FirebaseAuthException? resetError,
  }) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final firebase = _ResetRecordingFirebaseAuth(resetError);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authServiceProvider.overrideWith(() => _ResetRecordingAuth(firebase)),
        ],
        child: const MaterialApp(home: LoginScreen()),
      ),
    );
    return firebase;
  }

  Finder field(String label) => find.widgetWithText(TextFormField, label);

  testWidgets('"Forgot password?" sends the Firebase reset mail to the '
      'address typed on the form', (tester) async {
    final firebase = await pumpLogin(tester);
    await tester.enterText(field('Email'), ' ada@example.com ');

    await tester.tap(find.text('Forgot password?'));
    await tester.pumpAndSettle();

    // The dialog starts from the form's address.
    final dialog = find.byType(ForgotPasswordDialog);
    expect(dialog, findsOneWidget);
    expect(
      find.descendant(of: dialog, matching: find.text('ada@example.com')),
      findsOneWidget,
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Send link'));
    await tester.pumpAndSettle();

    expect(firebase.resetEmails, ['ada@example.com']);
    expect(
      find.text(
        'If an account exists for ada@example.com, we have sent it a link '
        'to reset the password.',
      ),
      findsOneWidget,
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Done'));
    await tester.pumpAndSettle();
    expect(dialog, findsNothing);
  });

  testWidgets('an address with no account gets the same answer', (
    tester,
  ) async {
    final firebase = await pumpLogin(
      tester,
      resetError: FirebaseAuthException(code: 'user-not-found'),
    );

    await tester.tap(find.text('Forgot password?'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.descendant(
        of: find.byType(ForgotPasswordDialog),
        matching: find.byType(TextFormField),
      ),
      'nobody@example.com',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Send link'));
    await tester.pumpAndSettle();

    expect(firebase.resetEmails, ['nobody@example.com']);
    expect(
      find.text(
        'If an account exists for nobody@example.com, we have sent it a link '
        'to reset the password.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('a failure the address does not decide shows a fixed message '
      'and keeps the dialog open', (tester) async {
    await pumpLogin(
      tester,
      resetError: FirebaseAuthException(
        code: 'internal-error',
        message: 'RAW_DETAIL',
      ),
    );

    await tester.tap(find.text('Forgot password?'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.descendant(
        of: find.byType(ForgotPasswordDialog),
        matching: find.byType(TextFormField),
      ),
      'ada@example.com',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Send link'));
    await tester.pumpAndSettle();

    expect(find.text(passwordResetFailedMessage), findsOneWidget);
    expect(find.textContaining('RAW_DETAIL'), findsNothing);
    expect(find.byType(ForgotPasswordDialog), findsOneWidget);
  });

  testWidgets('an empty address is refused before anything is sent', (
    tester,
  ) async {
    final firebase = await pumpLogin(tester);

    await tester.tap(find.text('Forgot password?'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Send link'));
    await tester.pumpAndSettle();

    expect(find.text('Enter your email'), findsOneWidget);
    expect(firebase.resetEmails, isEmpty);
  });

  group('validatePassword (todo 715, audit M17)', () {
    test('a new password needs the Firebase policy minimum of 14', () {
      expect(minPasswordLength, 14);
      expect(validatePassword(''), 'Enter a password');
      expect(validatePassword('a' * 13), 'Use at least 14 characters');
      expect(validatePassword('a' * 14), isNull);
    });
  });
}

/// [FakeAuthService] with the real reset method, over a fake Firebase.
class _ResetRecordingAuth extends FakeAuthService {
  _ResetRecordingAuth(this.firebase) : super(loggedIn: false);

  final _ResetRecordingFirebaseAuth firebase;

  @override
  FirebaseAuth get firebaseAuth => firebase;
}

class _ResetRecordingFirebaseAuth implements FirebaseAuth {
  _ResetRecordingFirebaseAuth(this.error);

  final FirebaseAuthException? error;
  final List<String> resetEmails = [];

  @override
  Future<void> sendPasswordResetEmail({
    required String email,
    ActionCodeSettings? actionCodeSettings,
  }) async {
    resetEmails.add(email);
    final e = error;
    if (e != null) throw e;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
