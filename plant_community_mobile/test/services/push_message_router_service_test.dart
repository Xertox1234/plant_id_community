// Push-tap routing (todo 311). These tests drive the FCM tap entry points
// at the transport layer — `FirebaseMessagingPlatform.onMessageOpenedApp`
// and a faked `FirebaseMessaging.getInitialMessage()` — NOT a physical-
// device notification-tray tap. A real on-device repro is blocked on todo
// 286 (Apple provisioning still missing for a distributed build); this is
// the closest coverage available until that lands.

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_messaging_platform_interface/firebase_messaging_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/garden/garden_screen.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';
import 'package:plant_community_mobile/features/onboarding/onboarding_checklist_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_message_router_service.dart';

import '../features/forum/support/forum_test_support.dart';
import '../features/garden/support/garden_test_support.dart';

/// The reply_added/mention/answer_accepted shape from the backend's
/// `_build_payload` (`backend/apps/forum_host/notifications.py`) — all
/// values are strings, an FCM requirement.
const _samplePayload = RemoteMessage(
  data: {
    'topic_id': '42',
    'topic_title': 'Ferns',
    'post_id': '7',
    'actor_name': 'Alex',
    'event': 'reply_added',
  },
);

/// Drains SplashScreen's periodic progress timer AND its chained
/// `Future.delayed` settle step (30ms ticks to ~1.5s, then a further 300ms
/// before `context.go(AppRoutes.home)`). A single big `tester.pump(Duration)`
/// jump advances the fake clock and fires due timers, but does not reliably
/// force the router to rebuild in response to a `go()` triggered partway
/// through that jump — confirmed empirically (a deliberately-broken
/// implementation still passed the splash-race assertion under one big
/// pump, and only failed once the drain was split like this). Several
/// smaller pumps give each intermediate navigation its own settle-and-
/// rebuild cycle, matching the two-pump `pump(); pump(Duration(...))`
/// pattern this file and `app_router_test.dart` already use after every
/// single navigation.
Future<void> _drainSplashTimer(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 500));
  }
}

/// The care-reminder shape from `garden_calendar.tasks` (todo 410): no
/// `topic_id`, so the forum parse alone would drop it.
const _careReminderPayload = RemoteMessage(
  data: {
    'event': 'care_task_due',
    'care_task_uuid': '6f1c2d3e-0000-4000-8000-000000000001',
    'plant_uuid': '6f1c2d3e-0000-4000-8000-000000000002',
    'count': '2',
  },
);

/// Signed in (the garden is a protected route) with a faked garden API.
ProviderContainer _careContainer() => ProviderContainer(
  overrides: [
    authServiceProvider.overrideWithValue(const AuthState(jwtToken: 'jwt')),
    gardenApiProvider.overrideWithValue(FakeGardenApi()),
    forumApiProvider.overrideWithValue(FakeForumApi()),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    // Signed in, Home (where splash lands) shows the onboarding card, which
    // would otherwise fetch over real Dio (todo 412).
    onboardingChecklistServiceProvider.overrideWith(_NoChecklist.new),
  ],
);

/// Signed in to Firebase at launch, with the JWT exchange still in flight:
/// `isAuthenticated` is false until [finishRestore] — the cold-start state
/// a tap that launches the app actually meets.
class _RestoringAuthService extends AuthService {
  @override
  FirebaseAuth get firebaseAuth => _FakeFirebaseAuth();

  @override
  AuthState build() => AuthState(firebaseUser: _FakeUser());

  void finishRestore() {
    state = state.copyWith(jwtToken: 'jwt');
  }
}

class _FakeFirebaseAuth extends Fake implements FirebaseAuth {
  @override
  Stream<User?> authStateChanges() => const Stream.empty();
}

class _FakeUser extends Fake implements User {}

/// Like [_careContainer], but the session is still being restored.
ProviderContainer _restoringCareContainer() => ProviderContainer(
  overrides: [
    authServiceProvider.overrideWith(_RestoringAuthService.new),
    gardenApiProvider.overrideWithValue(FakeGardenApi()),
    forumApiProvider.overrideWithValue(FakeForumApi()),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    onboardingChecklistServiceProvider.overrideWith(_NoChecklist.new),
  ],
);

/// No onboarding checklist, without touching the network.
class _NoChecklist extends OnboardingChecklistService {
  @override
  Future<OnboardingChecklist?> build() async => null;
}

void main() {
  group('care_task_due pushes (todo 386)', () {
    testWidgets('a warm-resume tap opens the garden', (tester) async {
      final container = _careContainer();
      addTearDown(container.dispose);
      final router = container.read(appRouterProvider);
      container.listen(appRouterProvider, (_, _) {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pump();

      final service = _TestablePushMessageRouterService(
        () => router,
        _FakeMessaging(),
      );
      addTearDown(service.detach);

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_careReminderPayload);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.byType(GardenScreen), findsOneWidget);

      await _drainSplashTimer(tester);
    });

    testWidgets(
      'a cold-start tap opens the garden and survives the splash redirect',
      (tester) async {
        final container = _careContainer();
        addTearDown(container.dispose);
        final router = container.read(appRouterProvider);
        container.listen(appRouterProvider, (_, _) {});

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );
        await tester.pump();

        final service = _TestablePushMessageRouterService(
          () => router,
          _FakeMessaging(initialMessage: _careReminderPayload),
        );
        addTearDown(service.detach);

        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));
        expect(find.byType(GardenScreen), findsOneWidget);

        // Past splash's own ~1.8 s go(home): the garden must still be up.
        await _drainSplashTimer(tester);
        expect(find.byType(GardenScreen), findsOneWidget);
      },
    );

    testWidgets(
      'a cold-start tap waits for the launch session restore, then opens '
      'the garden instead of bouncing to login',
      (tester) async {
        final container = _restoringCareContainer();
        addTearDown(container.dispose);
        final router = container.read(appRouterProvider);
        container.listen(appRouterProvider, (_, _) {});

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );
        await tester.pump();

        final service = _TestablePushMessageRouterService(
          () => router,
          _FakeMessaging(initialMessage: _careReminderPayload),
          awaitAuthRestore: container.read(authRestoreWaiterProvider),
        );
        addTearDown(service.detach);

        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));
        // Restore still in flight: nothing pushed yet, so no login detour.
        expect(find.byType(LoginScreen), findsNothing);
        expect(find.byType(GardenScreen), findsNothing);

        // The launch JWT exchange lands after splash's own go(home).
        await _drainSplashTimer(tester);
        (container.read(authServiceProvider.notifier) as _RestoringAuthService)
            .finishRestore();
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        expect(find.byType(GardenScreen), findsOneWidget);
        expect(find.byType(LoginScreen), findsNothing);
      },
    );

    test('waitForAuthRestore returns at once when there is nothing to '
        'restore, and gives up after its timeout', () async {
      final signedOut = ProviderContainer(
        overrides: [authServiceProvider.overrideWithValue(const AuthState())],
      );
      addTearDown(signedOut.dispose);
      await signedOut.read(authRestoreWaiterProvider)();

      final restoring = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWith(_RestoringAuthService.new),
        ],
      );
      addTearDown(restoring.dispose);
      final waiter = restoring.read(
        Provider(
          (ref) =>
              () => waitForAuthRestore(
                ref,
                timeout: const Duration(milliseconds: 50),
              ),
        ),
      );
      final stopwatch = Stopwatch()..start();
      await waiter();
      expect(
        stopwatch.elapsed,
        greaterThanOrEqualTo(const Duration(milliseconds: 50)),
      );
    });

    test('authRestoreSettled: only a Firebase user with no JWT and no error '
        'is still restoring', () {
      expect(authRestoreSettled(const AuthState()), isTrue);
      expect(authRestoreSettled(const AuthState(jwtToken: 'jwt')), isTrue);
      expect(authRestoreSettled(AuthState(firebaseUser: _FakeUser())), isFalse);
      expect(
        authRestoreSettled(
          AuthState(firebaseUser: _FakeUser(), error: 'exchange failed'),
        ),
        isTrue,
      );
    });
  });

  group('PushMessageRouterService', () {
    testWidgets(
      'a warm-resume tap (onMessageOpenedApp) routes to the topic and post',
      (tester) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWithValue(const AuthState()),
            forumApiProvider.overrideWithValue(
              FakeForumApi()..topicDetail = topicDetail(id: 42, title: 'Ferns'),
            ),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          ],
        );
        addTearDown(container.dispose);
        final router = container.read(appRouterProvider);
        // appRouterProvider is autoDispose; a bare container.read has no
        // persistent subscription, so it can be disposed between pump
        // cycles and a later navigation's redirect throws. Matches
        // app_router_test.dart's precedent for any test that navigates.
        container.listen(appRouterProvider, (_, _) {});

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );
        await tester.pump();

        final service = _TestablePushMessageRouterService(
          () => router,
          _FakeMessaging(),
        );
        addTearDown(service.detach);

        FirebaseMessagingPlatform.onMessageOpenedApp.add(_samplePayload);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        expect(find.byType(ForumThreadScreen), findsOneWidget);
        final thread = tester.widget<ForumThreadScreen>(
          find.byType(ForumThreadScreen),
        );
        expect(thread.topicId, 42);
        expect(thread.highlightPostId, 7);

        // Drain SplashScreen's still-pending timer so it doesn't outlive
        // the widget tree (matches app_router_test.dart's convention).
        await _drainSplashTimer(tester);
      },
    );

    testWidgets(
      'a cold-start tap (getInitialMessage) routes to the topic and post, '
      "and survives splash screen's own timer-driven redirect to home",
      (tester) async {
        final container = ProviderContainer(
          overrides: [
            authServiceProvider.overrideWithValue(const AuthState()),
            forumApiProvider.overrideWithValue(
              FakeForumApi()..topicDetail = topicDetail(id: 42, title: 'Ferns'),
            ),
            forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
          ],
        );
        addTearDown(container.dispose);
        final router = container.read(appRouterProvider);
        container.listen(appRouterProvider, (_, _) {});

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(routerConfig: router),
          ),
        );
        // One frame: SplashScreen mounts and its ~1.8s progress timer starts
        // ticking toward its own `go(home)` — the race this test exists to
        // catch.
        await tester.pump();

        final service = _TestablePushMessageRouterService(
          () => router,
          _FakeMessaging(initialMessage: _samplePayload),
        );
        addTearDown(service.detach);

        // Let the faked getInitialMessage() future resolve and the
        // resulting navigation run.
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // First assertion: navigation happened immediately. A naive test
        // that only checked this would pass even on a broken
        // implementation that skips the pre-emptive `go(home)` — splash's
        // timer hasn't reached ~1.8s yet at this point either way.
        expect(find.byType(ForumThreadScreen), findsOneWidget);
        final thread = tester.widget<ForumThreadScreen>(
          find.byType(ForumThreadScreen),
        );
        expect(thread.topicId, 42);
        expect(thread.highlightPostId, 7);

        // Second assertion — this is what actually catches the splash-race
        // bug: drain well past splash's ~1.8s timer. A broken
        // implementation lets splash's still-alive timer fire here and
        // wipe the pushed route back to `/home`; the fix pre-empts it with
        // its own `go(home)`, which disposes SplashScreen (cancelling its
        // timer) before the topic route is pushed on top. Verified
        // empirically by temporarily removing the fix's `go(home)` call —
        // this assertion then fails, as intended.
        await _drainSplashTimer(tester);
        expect(find.byType(ForumThreadScreen), findsOneWidget);
      },
    );

    group('payload edge cases', () {
      testWidgets(
        'a moderation_decided-shaped payload (no post_id key) routes to '
        'the topic without a postId query param',
        (tester) async {
          final container = ProviderContainer(
            overrides: [
              authServiceProvider.overrideWithValue(const AuthState()),
              forumApiProvider.overrideWithValue(
                FakeForumApi()
                  ..topicDetail = topicDetail(id: 42, title: 'Ferns'),
              ),
              forumSyncStoreProvider.overrideWithValue(
                InMemoryForumSyncStore(),
              ),
            ],
          );
          addTearDown(container.dispose);
          final router = container.read(appRouterProvider);
          container.listen(appRouterProvider, (_, _) {});

          await tester.pumpWidget(
            UncontrolledProviderScope(
              container: container,
              child: MaterialApp.router(routerConfig: router),
            ),
          );
          await tester.pump();

          final service = _TestablePushMessageRouterService(
            () => router,
            _FakeMessaging(),
          );
          addTearDown(service.detach);

          FirebaseMessagingPlatform.onMessageOpenedApp.add(
            const RemoteMessage(
              data: {
                'topic_id': '42',
                'status': 'approved',
                'obj_id': '99',
                'event': 'moderation_decided',
              },
            ),
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 400));

          expect(find.byType(ForumThreadScreen), findsOneWidget);
          final thread = tester.widget<ForumThreadScreen>(
            find.byType(ForumThreadScreen),
          );
          expect(thread.topicId, 42);
          expect(thread.highlightPostId, isNull);

          await _drainSplashTimer(tester);
        },
      );

      testWidgets(
        'an unparseable topic_id does not navigate at all (silent no-op, '
        'not a crash)',
        (tester) async {
          final container = ProviderContainer(
            overrides: [
              authServiceProvider.overrideWithValue(const AuthState()),
              forumApiProvider.overrideWithValue(FakeForumApi()),
              forumSyncStoreProvider.overrideWithValue(
                InMemoryForumSyncStore(),
              ),
            ],
          );
          addTearDown(container.dispose);
          final router = container.read(appRouterProvider);
          container.listen(appRouterProvider, (_, _) {});

          await tester.pumpWidget(
            UncontrolledProviderScope(
              container: container,
              child: MaterialApp.router(routerConfig: router),
            ),
          );
          await tester.pump();

          final service = _TestablePushMessageRouterService(
            () => router,
            _FakeMessaging(),
          );
          addTearDown(service.detach);

          FirebaseMessagingPlatform.onMessageOpenedApp.add(
            const RemoteMessage(
              data: {
                'status': 'approved',
                'obj_id': '99',
                'event': 'moderation_decided',
              },
            ),
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 400));

          expect(find.byType(ForumThreadScreen), findsNothing);

          await _drainSplashTimer(tester);
        },
      );
    });
  });

  group('pushBackgroundMessageHandler', () {
    test('completes without throwing', () async {
      await expectLater(
        pushBackgroundMessageHandler(
          const RemoteMessage(data: {'topic_id': '42'}),
        ),
        completes,
      );
    });
  });
}

/// Overrides [PushMessageRouterService.messaging] test seam, mirroring
/// `push_registration_service_test.dart`'s `_TestablePushRegistrationService`.
class _TestablePushMessageRouterService extends PushMessageRouterService {
  _TestablePushMessageRouterService(
    super.routerAccessor,
    this._messaging, {
    super.awaitAuthRestore,
  });

  final FirebaseMessaging _messaging;

  @override
  FirebaseMessaging get messaging => _messaging;
}

/// Hand-rolled fake (no mocking library in this suite): only
/// [getInitialMessage] is implemented; anything else is a loud
/// [NoSuchMethodError] via [noSuchMethod].
class _FakeMessaging implements FirebaseMessaging {
  _FakeMessaging({this.initialMessage});

  final RemoteMessage? initialMessage;

  @override
  Future<RemoteMessage?> getInitialMessage() async => initialMessage;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
