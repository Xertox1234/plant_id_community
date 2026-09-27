import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/services/forum_link_launcher.dart';
import 'package:plant_community_mobile/main.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

/// The 409 account-conflict error carries a "Forgot password?" link to
/// allauth's reset page (todo 447, owner decision 2026-09-26). Driven through
/// [MyApp], whose root listener shows every [AuthState.error], so the test
/// fails if the listener stops passing the action on.
void main() {
  late List<Uri> launched;

  Future<_StubAuthService> pumpApp(WidgetTester tester) async {
    launched = [];
    final auth = _StubAuthService();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authServiceProvider.overrideWith(() => auth),
          apiServiceProvider.overrideWithValue(
            ApiService(baseUrl: 'https://api.example.test/api/v1'),
          ),
          forumLinkLauncherProvider.overrideWithValue((uri) async {
            launched.add(uri);
            return true;
          }),
        ],
        child: const MyApp(),
      ),
    );
    // Past the splash, so no route transition sits over the SnackBar.
    await tester.pumpAndSettle(const Duration(seconds: 3));
    return auth;
  }

  testWidgets('the conflict error opens the reset page in the in-app browser', (
    tester,
  ) async {
    final auth = await pumpApp(tester);

    auth.emit(
      const AuthState(
        error: accountConflictMessage,
        unverifiedAccountConflict: true,
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text(accountConflictMessage), findsOneWidget);
    // Invoked directly: under the test's shell layout the home tab's text
    // overlaps the SnackBar's hit area. What matters here is the action's
    // label and where it goes.
    final action = tester.widget<SnackBarAction>(find.byType(SnackBarAction));
    expect(action.label, 'Forgot password?');
    action.onPressed();
    await tester.pump();

    expect(launched, [
      Uri.parse('https://api.example.test/accounts/password/reset/'),
    ]);

    await tester.pumpAndSettle(const Duration(seconds: 3));
  });

  testWidgets('the conflict SnackBar goes once the conflict is over', (
    tester,
  ) async {
    // It persists (it has an action), so nothing else would take it down.
    final auth = await pumpApp(tester);
    auth.emit(
      const AuthState(
        error: accountConflictMessage,
        unverifiedAccountConflict: true,
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text(accountConflictMessage), findsOneWidget);

    auth.emit(const AuthState(jwtToken: 'signed-in'));
    await tester.pumpAndSettle();

    expect(find.text(accountConflictMessage), findsNothing);
  });

  testWidgets('signing out also ends the conflict SnackBar', (tester) async {
    // Todo 449 item 7: sign-out is `AuthState()` with no error, the same
    // branch as a successful sign-in, pinned so it holds by test, not reasoning.
    final auth = await pumpApp(tester);
    auth.emit(
      const AuthState(
        error: accountConflictMessage,
        unverifiedAccountConflict: true,
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text(accountConflictMessage), findsOneWidget);

    auth.emit(const AuthState());
    await tester.pumpAndSettle();

    expect(find.text(accountConflictMessage), findsNothing);
  });

  testWidgets('any other auth error has no reset link', (tester) async {
    final auth = await pumpApp(tester);

    auth.emit(const AuthState(error: 'Failed to connect to server.'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Failed to connect to server.'), findsOneWidget);
    expect(find.byType(SnackBarAction), findsNothing);

    await tester.pumpAndSettle(const Duration(seconds: 5));
  });
}

/// Skips Firebase entirely; the test sets the state the exchange would.
class _StubAuthService extends AuthService {
  @override
  AuthState build() => const AuthState();

  void emit(AuthState next) => state = next;
}
