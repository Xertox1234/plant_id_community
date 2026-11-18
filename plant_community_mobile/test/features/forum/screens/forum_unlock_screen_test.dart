// The unlock screen for a password forum (spec §7.4): one password field,
// an Unlock button, inline errors; a success keeps the member's token and
// opens the forum.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_unlock_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';

import '../support/forum_test_support.dart';

const _secret = ForumBoard(
  id: 7,
  title: 'Rare aroids',
  slug: 'rare-aroids',
  description: 'Members only.',
  topicCount: 3,
  postCount: 9,
  isLocked: true,
);

/// The server's view: once the member has unlocked it, the feed lists the
/// forum open (so the feed's dead-token rule keeps the new token).
class _UnlockingApi extends FakeForumApi {
  @override
  Future<String?> unlockBoard(String slug, String password) async {
    final token = await super.unlockBoard(slug, password);
    categories = [
      categoryOf(const [
        ForumBoard(
          id: 7,
          title: 'Rare aroids',
          slug: 'rare-aroids',
          description: 'Members only.',
          topicCount: 3,
          postCount: 9,
        ),
      ]),
    ];
    return token;
  }
}

class _Screen {
  _Screen({AuthState? auth, ForumUnlocks? stored})
    : auth = auth ?? signedInAs('ada'),
      store = FakeForumUnlockStore(stored);

  final AuthState auth;
  final FakeForumUnlockStore store;
  final api = _UnlockingApi()
    ..categories = [
      categoryOf(const [_secret]),
    ];
  late final ProviderContainer container;

  void setAuth(AuthState next) =>
      (container.read(authServiceProvider.notifier) as FakeAuthService).setAuth(
        next,
      );

  Future<void> open(
    WidgetTester tester, {
    Brightness brightness = Brightness.light,
    double textScale = 1.0,
  }) async {
    container = ProviderContainer(
      retry: (_, _) => null,
      overrides: [
        forumApiProvider.overrideWithValue(api),
        forumUnlockStoreProvider.overrideWithValue(store),
        apiServiceProvider.overrideWithValue(
          ApiService(baseUrl: 'http://api.test', authToken: 'a'),
        ),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: false, initial: auth),
        ),
      ],
    );
    addTearDown(container.dispose);
    final router = GoRouter(
      initialLocation: '/forum/boards/rare-aroids/unlock',
      routes: [
        GoRoute(
          path: '/forum/boards/:slug/unlock',
          name: 'forumUnlock',
          builder: (_, state) => ForumUnlockScreen(
            boardSlug: state.pathParameters['slug']!,
            boardTitle: 'Rare aroids',
          ),
        ),
        GoRoute(
          path: '/forum/boards/:slug',
          name: 'forumBoard',
          builder: (_, state) => Scaffold(
            body: Text('BOARD ${state.pathParameters['slug']} ${state.extra}'),
          ),
        ),
        GoRoute(
          path: '/login',
          name: 'login',
          builder: (_, _) => const Scaffold(body: Text('LOGIN PAGE')),
        ),
      ],
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          theme: AppTheme.build(brightness, AppDensity.cozy),
          routerConfig: router,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(textScale)),
            child: child!,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> type(WidgetTester tester, String text) async {
    await tester.enterText(find.byType(TextField), text);
    await tester.pump();
  }

  Future<void> tapUnlock(WidgetTester tester) async {
    await tester.tap(find.widgetWithText(ClayButton, 'Unlock'));
    await tester.pump();
  }

  ClayButton get button =>
      find.byType(ClayButton).evaluate().single.widget as ClayButton;
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('correct password stores the token and opens the forum', (
    tester,
  ) async {
    final s = _Screen();
    await s.open(tester);
    expect(find.text('Rare aroids'), findsOneWidget);
    final feedFetches = s.api.fetchCategoriesCalls;

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(s.api.unlockBoardCalls, ['rare-aroids']);
    expect(s.store.stored?.uid, 'ada');
    expect(s.store.stored?.tokens, {7: 'unlock-token'});
    expect(s.container.read(apiServiceProvider).forumUnlockTokens, [
      'unlock-token',
    ]);
    expect(s.api.fetchCategoriesCalls, greaterThan(feedFetches));
    expect(find.text('BOARD rare-aroids Rare aroids'), findsOneWidget);
  });

  testWidgets('the password is cleared from the field after a successful '
      'unlock', (tester) async {
    final s = _Screen();
    await s.open(tester);
    final controller = tester
        .widget<TextField>(find.byType(TextField))
        .controller!;
    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(controller.text, isEmpty);
  });

  testWidgets('nothing to unlock (a null token) changes no stored token and '
      'opens the forum', (tester) async {
    // A token for another forum: neither replaced nor dropped.
    final s = _Screen(
      stored: const ForumUnlocks(uid: 'ada', tokens: {9: 'other'}),
    );
    s.api.unlockToken = null;
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(s.store.saveCalls, 0);
    expect(s.store.stored?.tokens, {9: 'other'});
    expect(find.text('BOARD rare-aroids Rare aroids'), findsOneWidget);
  });

  testWidgets('wrong password shows "Wrong password." and keeps the field', (
    tester,
  ) async {
    final s = _Screen();
    s.api.unlockError = ApiException('Incorrect password.', statusCode: 400);
    await s.open(tester);

    await s.type(tester, 'nope');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(find.text('Wrong password.'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('nope'), findsOneWidget);
    expect(s.store.saveCalls, 0);
    expect(s.button.onPressed, isNotNull, reason: 'they can try again');
  });

  testWidgets('429 with retry-after 840 shows "Try again in 14 minutes."', (
    tester,
  ) async {
    final s = _Screen();
    s.api.unlockError = ApiException(
      'Too many requests.',
      statusCode: 429,
      retryAfterSeconds: 840,
    );
    await s.open(tester);

    await s.type(tester, 'guess');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(
      find.text('Too many tries. Try again in 14 minutes.'),
      findsOneWidget,
    );
  });

  testWidgets('429 rounds up and never says less than one minute', (
    tester,
  ) async {
    final s = _Screen();
    s.api.unlockError = ApiException(
      'Too many requests.',
      statusCode: 429,
      retryAfterSeconds: 5,
    );
    await s.open(tester);

    await s.type(tester, 'guess');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(find.text('Too many tries. Try again in 1 minute.'), findsOneWidget);
  });

  testWidgets('another failure shows the retry message', (tester) async {
    final s = _Screen();
    s.api.unlockError = ApiException('down', statusCode: 503);
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(
      find.text('Could not unlock this forum. Try again.'),
      findsOneWidget,
    );
    expect(s.button.onPressed, isNotNull);
  });

  testWidgets('Unlock is disabled while the field is empty', (tester) async {
    final s = _Screen();
    await s.open(tester);
    expect(s.button.onPressed, isNull);

    await s.type(tester, 'x');
    expect(s.button.onPressed, isNotNull);

    await s.type(tester, '');
    expect(s.button.onPressed, isNull);
  });

  testWidgets('the unlock goes out once per tap: busy disables the button', (
    tester,
  ) async {
    final s = _Screen();
    s.api.unlockGate = Completer<void>();
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    expect(s.button.onPressed, isNull);
    expect(s.button.loading, isTrue);
    await tester.tap(find.byType(ClayButton), warnIfMissed: false);
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();

    s.api.unlockGate!.complete();
    await tester.pumpAndSettle();
    expect(s.api.unlockBoardCalls, hasLength(1));
  });

  testWidgets('the password field is obscured, with autofill, autocorrect '
      'and suggestions off', (tester) async {
    final s = _Screen();
    await s.open(tester);

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.obscureText, isTrue);
    expect(field.autofillHints, isNull);
    expect(field.autocorrect, isFalse);
    expect(field.enableSuggestions, isFalse);
    expect(field.enableIMEPersonalizedLearning, isFalse);
  });

  testWidgets('an answer that lands after an account switch stores nothing '
      'and does not open the forum', (tester) async {
    final s = _Screen();
    s.api.unlockGate = Completer<void>();
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    s.setAuth(signedInAs('bob'));
    await tester.pump();
    s.api.unlockGate!.complete();
    await tester.pumpAndSettle();

    expect(s.store.saveCalls, 0);
    expect(s.container.read(apiServiceProvider).forumUnlockTokens, isEmpty);
    expect(find.textContaining('BOARD'), findsNothing);
    expect(find.text('hunter2'), findsNothing, reason: 'not kept for bob');
  });

  testWidgets('an answer that lands after sign-out stores nothing and does '
      'not open the forum', (tester) async {
    final s = _Screen();
    s.api.unlockGate = Completer<void>();
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    s.setAuth(const AuthState());
    await tester.pump();
    s.api.unlockGate!.complete();
    await tester.pumpAndSettle();

    expect(s.store.saveCalls, 0);
    expect(find.textContaining('BOARD'), findsNothing);
  });

  testWidgets('a guest who opens the route sees the sign-in prompt, not a '
      'password field', (tester) async {
    final s = _Screen(auth: const AuthState());
    await s.open(tester);

    expect(find.byType(TextField), findsNothing);
    expect(find.text('Sign in to open this forum.'), findsOneWidget);
    await tester.tap(find.widgetWithText(ClayButton, 'Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('LOGIN PAGE'), findsOneWidget);
  });

  testWidgets('a forum the feed does not list sends no password', (
    tester,
  ) async {
    final s = _Screen();
    s.api.categories = [categoryOf(const [])];
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();

    expect(s.api.unlockBoardCalls, isEmpty);
    expect(
      find.text('Could not unlock this forum. Try again.'),
      findsOneWidget,
    );
  });

  testWidgets('a feed that failed is fetched again on the next tap', (
    tester,
  ) async {
    final s = _Screen();
    s.api.categoriesError = ApiException('down', statusCode: 503);
    await s.open(tester);

    await s.type(tester, 'hunter2');
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();
    expect(s.api.unlockBoardCalls, isEmpty);
    expect(
      find.text('Could not unlock this forum. Try again.'),
      findsOneWidget,
    );

    s.api.categoriesError = null;
    await s.tapUnlock(tester);
    await tester.pumpAndSettle();
    expect(s.api.unlockBoardCalls, hasLength(1));
    expect(s.store.stored?.tokens, {7: 'unlock-token'});
    expect(find.text('BOARD rare-aroids Rare aroids'), findsOneWidget);
  });

  for (final brightness in Brightness.values) {
    for (final (w, h, scale) in [(320.0, 640.0, 2.0), (375.0, 812.0, 1.0)]) {
      testWidgets('fits and passes the a11y guidelines at ${w}x$h @$scale '
          '(${brightness.name})', (tester) async {
        tester.view.physicalSize = Size(w, h);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);
        final handle = tester.ensureSemantics();
        final s = _Screen();
        s.api.unlockError = ApiException(
          'Incorrect password.',
          statusCode: 400,
        );
        await s.open(tester, brightness: brightness, textScale: scale);
        await s.type(tester, 'nope');
        await s.tapUnlock(tester);
        await tester.pumpAndSettle();

        expect(tester.takeException(), isNull);
        expect(find.text('Wrong password.'), findsOneWidget);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        handle.dispose();
      });
    }
  }

  testWidgets('the keyboard does not cover the field or the button', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(375, 667);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final s = _Screen();
    await s.open(tester, textScale: 2.0);
    await s.type(tester, 'x');

    // A 300pt keyboard.
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(tester.view.resetViewInsets);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byType(ClayButton));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final visibleBottom = 667 - 300;
    expect(
      tester.getBottomLeft(find.byType(ClayButton)).dy,
      lessThanOrEqualTo(visibleBottom),
    );
  });
}
