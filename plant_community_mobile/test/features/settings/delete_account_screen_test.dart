import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/settings/delete_account_screen.dart';
import 'package:plant_community_mobile/services/account_deletion_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

import '../forum/support/forum_test_support.dart';

const _intro =
    'This permanently deletes your account, saved plants, garden, scans and '
    'forum posts. Other people keep their copy of messages you sent them. It '
    "can't be undone.";
const _subscriptions =
    "Deleting your account doesn't cancel a Premium subscription. Manage "
    'subscriptions in the App Store or Google Play.';
const _finalMessage =
    "Your account is being deleted. You'll get an email when it's done.";

/// Signed in, with re-auth and sign-out recorded into [events] instead of
/// reaching Firebase.
class _FakeAuth extends FakeAuthService {
  _FakeAuth(this.events, {this.method = ReauthMethod.google})
    : super(loggedIn: true);

  final List<String> events;
  final ReauthMethod? method;
  AuthException? reauthError;

  @override
  ReauthMethod? get reauthMethod => method;

  @override
  Future<String> freshIdTokenAfterReauth({String? password}) async {
    events.add(password == null ? 'reauth' : 'reauth:$password');
    final error = reauthError;
    if (error != null) throw error;
    return 'fresh-token';
  }

  @override
  Future<void> signOut() async {
    events.add('signOut');
    state = const AuthState();
  }
}

class _FakeDeletion extends AccountDeletionService {
  _FakeDeletion(this.events) : super(ApiService(baseUrl: 'http://fake.local'));

  final List<String> events;
  AccountDeletionResult result = const AccountDeletionScheduled();

  /// When set, the request stays in flight until it completes.
  Completer<void>? gate;

  @override
  Future<AccountDeletionResult> deleteAccount(String firebaseToken) async {
    events.add('delete:$firebaseToken');
    final g = gate;
    if (g != null) await g.future;
    return result;
  }
}

class _Harness {
  _Harness({ReauthMethod? method = ReauthMethod.google})
    : this._withEvents(<String>[], method);

  _Harness._withEvents(this.events, ReauthMethod? method)
    : auth = _FakeAuth(events, method: method),
      deletion = _FakeDeletion(events);

  /// One log shared by every fake, so the order across them is assertable.
  final List<String> events;
  final _FakeAuth auth;
  final _FakeDeletion deletion;
  final List<Uri> launched = [];
  late final GoRouter router;

  /// When set, the offline-cache clear throws it (it must stay non-fatal).
  Object? clearCacheError;

  Widget build() {
    // The screen sits on top of a home page, so a back can pop it.
    router = GoRouter(
      initialLocation: DeleteAccountScreen.routePath,
      routes: [
        GoRoute(
          path: '/',
          builder: (_, _) => const Scaffold(body: Text('HOME')),
          routes: [
            GoRoute(
              path: DeleteAccountScreen.routePath.substring(1),
              builder: (_, _) => const DeleteAccountScreen(),
            ),
          ],
        ),
        GoRoute(
          path: '/login',
          builder: (_, _) => const Scaffold(body: Text('LOGIN SCREEN')),
        ),
      ],
    );
    return ProviderScope(
      overrides: [
        authServiceProvider.overrideWith(() => auth),
        accountDeletionServiceProvider.overrideWithValue(deletion),
        externalLinkLauncherProvider.overrideWithValue((uri) async {
          launched.add(uri);
          return true;
        }),
        firestoreOfflineCacheClearerProvider.overrideWithValue(() async {
          events.add('clearCache');
          final error = clearCacheError;
          if (error != null) throw error;
        }),
      ],
      child: MaterialApp.router(
        theme: AppTheme.build(Brightness.light, AppDensity.cozy),
        routerConfig: router,
      ),
    );
  }
}

Future<_Harness> _pump(
  WidgetTester tester, {
  ReauthMethod? method = ReauthMethod.google,
}) async {
  final harness = _Harness(method: method);
  await tester.pumpWidget(harness.build());
  await tester.pumpAndSettle();
  return harness;
}

Future<void> _tapDelete(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Delete my account'));
  await tester.tap(find.text('Delete my account'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows the deletion copy and the danger button', (tester) async {
    await _pump(tester);

    expect(find.text('Delete account'), findsOneWidget);
    expect(find.text(_intro), findsOneWidget);
    expect(find.text(_subscriptions), findsOneWidget);
    expect(find.text('Delete my account'), findsOneWidget);
  });

  testWidgets('the button re-authenticates, deletes, then signs out, and the '
      'final dialog leads to the login screen', (tester) async {
    final harness = await _pump(tester);

    await _tapDelete(tester);

    expect(harness.events, [
      'reauth',
      'delete:fresh-token',
      'signOut',
      'clearCache',
    ]);
    expect(find.text(_finalMessage), findsOneWidget);

    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();

    expect(find.text('LOGIN SCREEN'), findsOneWidget);
  });

  testWidgets('a password user is asked for the password first', (
    tester,
  ) async {
    final harness = await _pump(tester, method: ReauthMethod.password);

    await _tapDelete(tester);
    expect(harness.events, isEmpty, reason: 'nothing runs before the password');

    await tester.enterText(find.byType(TextField), 'hunter2');
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();

    expect(harness.events, [
      'reauth:hunter2',
      'delete:fresh-token',
      'signOut',
      'clearCache',
    ]);
  });

  testWidgets('cancelling the password dialog sends nothing', (tester) async {
    final harness = await _pump(tester, method: ReauthMethod.password);

    await _tapDelete(tester);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(harness.events, isEmpty);
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('Delete my account'), findsOneWidget);
  });

  testWidgets('a cancelled re-auth leaves the user signed in and shows no '
      'error dialog', (tester) async {
    final harness = await _pump(tester);
    harness.auth.reauthError = ReauthCancelledException();

    await _tapDelete(tester);

    expect(harness.events, ['reauth']);
    expect(harness.auth.state.isAuthenticated, isTrue);
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('Delete my account'), findsOneWidget);
  });

  testWidgets('a failed re-auth shows its message and deletes nothing', (
    tester,
  ) async {
    final harness = await _pump(tester);
    harness.auth.reauthError = AuthException('Incorrect password.');

    await _tapDelete(tester);

    expect(harness.events, ['reauth']);
    expect(find.text('Incorrect password.'), findsOneWidget);
  });

  testWidgets('a 409 shows the server message and does not sign out', (
    tester,
  ) async {
    final harness = await _pump(tester);
    harness.deletion.result = const AccountDeletionFailed(
      'Your account has an open case. Contact support.',
    );

    await _tapDelete(tester);

    expect(harness.events, ['reauth', 'delete:fresh-token']);
    expect(
      find.text('Your account has an open case. Contact support.'),
      findsOneWidget,
    );
    expect(harness.auth.state.isAuthenticated, isTrue);
  });

  testWidgets('a 401 (already scheduled elsewhere) signs out and goes to the '
      'login screen without an error dialog', (tester) async {
    final harness = await _pump(tester);
    harness.deletion.result = const AccountDeletionSignedOut();

    await _tapDelete(tester);

    expect(harness.events, [
      'reauth',
      'delete:fresh-token',
      'signOut',
      'clearCache',
    ]);
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('LOGIN SCREEN'), findsOneWidget);
  });

  testWidgets('a failing offline-cache clear is not fatal: the final dialog '
      'still shows', (tester) async {
    final harness = _Harness();
    harness.clearCacheError = StateError('firestore not initialised');
    await tester.pumpWidget(harness.build());
    await tester.pumpAndSettle();

    await _tapDelete(tester);

    expect(harness.events, [
      'reauth',
      'delete:fresh-token',
      'signOut',
      'clearCache',
    ]);
    expect(find.text(_finalMessage), findsOneWidget);
    expect(harness.auth.state.isAuthenticated, isFalse);
  });

  testWidgets('a user with no supported sign-in method is told so', (
    tester,
  ) async {
    final harness = await _pump(tester, method: null);

    await _tapDelete(tester);

    expect(harness.events, isEmpty);
    expect(find.text(reauthUnsupportedMessage), findsOneWidget);
  });

  testWidgets('the final dialog does not claim the deletion is done', (
    tester,
  ) async {
    await _pump(tester);

    await _tapDelete(tester);

    expect(find.text('Account deletion started'), findsOneWidget);
    expect(find.text('Account deleted'), findsNothing);
  });

  testWidgets('back is blocked while the request runs, and works again '
      'after', (tester) async {
    final harness = await _pump(tester);
    harness.deletion.gate = Completer<void>();
    harness.deletion.result = const AccountDeletionFailed('Nope.');
    expect(find.byType(BackButton), findsOneWidget);

    await tester.tap(find.text('Delete my account'));
    await tester.pump();
    expect(find.byType(BackButton), findsNothing);

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(find.byType(DeleteAccountScreen), findsOneWidget);
    expect(find.text('HOME'), findsNothing);

    harness.deletion.gate!.complete();
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    expect(find.byType(BackButton), findsOneWidget);
  });

  testWidgets('a 202 that lands after the screen is gone still signs out', (
    tester,
  ) async {
    final harness = await _pump(tester);
    harness.deletion.gate = Completer<void>();

    await tester.tap(find.text('Delete my account'));
    await tester.pump();
    expect(harness.events, ['reauth', 'delete:fresh-token']);

    // Something else navigates away (a push tap): the screen unmounts.
    harness.router.go('/');
    await tester.pumpAndSettle();
    expect(find.byType(DeleteAccountScreen), findsNothing);

    harness.deletion.gate!.complete();
    await tester.pumpAndSettle();

    expect(harness.events, [
      'reauth',
      'delete:fresh-token',
      'signOut',
      'clearCache',
    ]);
    expect(tester.takeException(), isNull);
  });

  for (final (platform, url) in [
    (TargetPlatform.iOS, 'https://apps.apple.com/account/subscriptions'),
    (
      TargetPlatform.android,
      'https://play.google.com/store/account/subscriptions',
    ),
  ]) {
    testWidgets('the subscriptions note opens the ${platform.name} page', (
      tester,
    ) async {
      debugDefaultTargetPlatformOverride = platform;
      try {
        final harness = await _pump(tester);

        await tester.tap(find.text(_subscriptions));
        await tester.pump();

        expect(harness.launched, [Uri.parse(url)]);
      } finally {
        debugDefaultTargetPlatformOverride = null;
      }
    });
  }

  testWidgets('fits a 320pt phone at 2x text without overflow', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

    await _pump(tester);
    expect(tester.takeException(), isNull);

    await tester.scrollUntilVisible(find.text('Delete my account'), 200);
    expect(tester.takeException(), isNull);
    expect(find.text('Delete my account'), findsOneWidget);
  });
}
