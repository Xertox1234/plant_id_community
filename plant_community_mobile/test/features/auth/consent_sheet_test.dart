import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/auth/consent_checkbox.dart';
import 'package:plant_community_mobile/features/auth/consent_sheet.dart';
import 'package:plant_community_mobile/main.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

/// The consent sheet the root opens when the token exchange answers 428
/// `consent_required` (legal policies, Task 9).
void main() {
  Future<FakeAuthService> pumpOpener(WidgetTester tester) async {
    final fake = FakeAuthService(loggedIn: false);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authServiceProvider.overrideWith(() => fake)],
        child: MaterialApp(
          // Watched, as MyApp watches it: the provider is autoDispose.
          home: Consumer(
            builder: (context, ref, _) {
              ref.watch(authServiceProvider);
              return Scaffold(
                body: Center(
                  child: TextButton(
                    onPressed: () => showConsentSheet(context),
                    child: const Text('open'),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    return fake;
  }

  FilledButton continueButton(WidgetTester tester) =>
      tester.widget(find.widgetWithText(FilledButton, 'Continue'));

  testWidgets('shows the title and the shared consent checkbox', (
    tester,
  ) async {
    await pumpOpener(tester);

    expect(find.text('One more step'), findsOneWidget);
    expect(find.byType(ConsentCheckbox), findsOneWidget);
  });

  testWidgets('Continue is disabled until ticked, then retries with consent', (
    tester,
  ) async {
    final fake = await pumpOpener(tester);

    expect(continueButton(tester).onPressed, isNull);

    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    expect(continueButton(tester).onPressed, isNotNull);

    await tester.tap(find.widgetWithText(FilledButton, 'Continue'));
    await tester.pumpAndSettle();

    expect(fake.acceptTermsCalls, 1);
    expect(fake.declineTermsCalls, 0);
    expect(find.text('One more step'), findsNothing);
  });

  testWidgets('Cancel calls declineTerms', (tester) async {
    final fake = await pumpOpener(tester);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(fake.declineTermsCalls, 1);
    expect(fake.acceptTermsCalls, 0);
    expect(find.text('One more step'), findsNothing);
  });

  testWidgets('tapping outside counts as Cancel', (tester) async {
    final fake = await pumpOpener(tester);

    await tester.tapAt(const Offset(10, 10));
    await tester.pumpAndSettle();

    expect(find.text('One more step'), findsNothing);
    expect(fake.declineTermsCalls, 1);
    expect(fake.acceptTermsCalls, 0);
  });

  group('hosted at the app root', () {
    Future<FakeAuthService> pumpApp(WidgetTester tester) async {
      final fake = FakeAuthService(loggedIn: false);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authServiceProvider.overrideWith(() => fake),
            apiServiceProvider.overrideWithValue(
              ApiService(baseUrl: 'https://api.example.test/api/v1'),
            ),
          ],
          child: const MyApp(),
        ),
      );
      await tester.pumpAndSettle(const Duration(seconds: 3));
      return fake;
    }

    testWidgets('opens once when consentRequired turns true', (tester) async {
      final fake = await pumpApp(tester);
      expect(find.text('One more step'), findsNothing);

      fake.setAuth(const AuthState(consentRequired: true));
      await tester.pumpAndSettle();
      expect(find.text('One more step'), findsOneWidget);

      // Another true state (false in between) must not stack a second sheet.
      fake.setAuth(const AuthState());
      await tester.pump();
      fake.setAuth(const AuthState(consentRequired: true));
      await tester.pumpAndSettle();
      expect(find.text('One more step'), findsOneWidget);

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(find.text('One more step'), findsNothing);
      expect(fake.declineTermsCalls, 1);
    });
  });
}
