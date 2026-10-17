// Care-reminder taps reach the task they name (todo 621): the single task
// is highlighted in the garden, a multi-task reminder opens the due list,
// and a malformed, stale or foreign target falls back safely. Driven at the
// FCM transport layer, like push_message_router_service_test.dart.

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_messaging_platform_interface/firebase_messaging_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/routing/app_router.dart';
import 'package:plant_community_mobile/features/auth/login_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_sync_store.dart';
import 'package:plant_community_mobile/features/garden/garden_screen.dart';
import 'package:plant_community_mobile/features/garden/models/models.dart';
import 'package:plant_community_mobile/features/garden/providers/garden_focus_provider.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';
import 'package:plant_community_mobile/features/onboarding/onboarding_checklist_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_message_router_service.dart';

import '../features/forum/support/forum_test_support.dart';
import '../features/garden/support/garden_test_support.dart';

const _taskId = '6f1c2d3e-0000-4000-8000-000000000001';
const _plantId = '6f1c2d3e-0000-4000-8000-000000000002';

RemoteMessage _care({String? task = _taskId, String count = '1'}) =>
    RemoteMessage(
      data: {
        'event': 'care_task_due',
        'care_task_uuid': ?task,
        'plant_uuid': _plantId,
        'count': count,
      },
    );

CareTask _dueTask({String id = _taskId, String title = 'Water the fern'}) =>
    CareTask(
      id: id,
      plant: _plantId,
      plantName: 'Fern',
      title: title,
      taskType: 'watering',
      scheduledDate: DateTime.now(),
      isOverdue: true,
    );

/// Signed in, or signed out and able to sign in.
class _SwitchableAuth extends AuthService {
  _SwitchableAuth(this._initial);

  final AuthState _initial;

  @override
  FirebaseAuth get firebaseAuth => _FakeFirebaseAuth();

  @override
  AuthState build() => _initial;

  void signInAs() => state = const AuthState(jwtToken: 'jwt');
}

class _FakeFirebaseAuth extends Fake implements FirebaseAuth {
  @override
  Stream<User?> authStateChanges() => const Stream.empty();
}

class _NoChecklist extends OnboardingChecklistService {
  @override
  Future<OnboardingChecklist?> build() async => null;
}

ProviderContainer _container({
  AuthState auth = const AuthState(jwtToken: 'jwt'),
  List<CareTask>? tasks,
}) => ProviderContainer(
  overrides: [
    authServiceProvider.overrideWith(() => _SwitchableAuth(auth)),
    gardenApiProvider.overrideWithValue(
      FakeGardenApi(tasks: tasks ?? [_dueTask()]),
    ),
    forumApiProvider.overrideWithValue(FakeForumApi()),
    forumSyncStoreProvider.overrideWithValue(InMemoryForumSyncStore()),
    onboardingChecklistServiceProvider.overrideWith(_NoChecklist.new),
  ],
);

class _Messaging implements FirebaseMessaging {
  _Messaging({this.initialMessage});

  final RemoteMessage? initialMessage;

  @override
  Future<RemoteMessage?> getInitialMessage() async => initialMessage;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _Router extends PushMessageRouterService {
  _Router(super.routerAccessor, this._messaging, {super.onCareFocus});

  final FirebaseMessaging _messaging;

  @override
  FirebaseMessaging get messaging => _messaging;
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 400));
  await tester.pump(const Duration(milliseconds: 400));
}

/// SplashScreen's ~1.8 s timers, drained so no timer outlives the test.
Future<void> _drainSplash(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 500));
  }
}

Future<(ProviderContainer, _Router)> _start(
  WidgetTester tester, {
  AuthState auth = const AuthState(jwtToken: 'jwt'),
  List<CareTask>? tasks,
  RemoteMessage? initial,
}) async {
  final container = _container(auth: auth, tasks: tasks);
  addTearDown(container.dispose);
  final router = container.read(appRouterProvider);
  container.listen(appRouterProvider, (_, _) {});
  container.listen(gardenFocusProvider, (_, _) {});
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pump();
  final service = _Router(
    () => router,
    _Messaging(initialMessage: initial),
    onCareFocus: (focus) =>
        container.read(gardenFocusProvider.notifier).set(focus),
  );
  addTearDown(service.detach);
  return (container, service);
}

bool _highlighted(WidgetTester tester, String title) => tester
    .widget<ListTile>(
      find.ancestor(of: find.text(title), matching: find.byType(ListTile)),
    )
    .selected;

void main() {
  group('careFocusOf', () {
    test('several tasks open the due list', () {
      expect(careFocusOf(_care(count: '3').data), const GardenFocus.dueList());
    });

    test('one well-formed task uuid targets that task', () {
      expect(careFocusOf(_care().data), const GardenFocus.task(_taskId));
      expect(
        careFocusOf(_care(task: _taskId.toUpperCase()).data),
        const GardenFocus.task(_taskId),
      );
    });

    test('a malformed or missing target is the plain garden', () {
      for (final data in [
        _care(task: 'not-a-uuid').data,
        _care(task: '$_taskId/../x').data,
        _care(task: null).data,
        <String, dynamic>{'event': 'care_task_due', 'count': 'many'},
      ]) {
        expect(careFocusOf(data), isNull, reason: '$data');
      }
    });
  });

  group('care tap targets (todo 621)', () {
    testWidgets('a warm tap highlights the task it named', (tester) async {
      await _start(
        tester,
        tasks: [
          _dueTask(),
          _dueTask(
            id: '6f1c2d3e-0000-4000-8000-000000000009',
            title: 'Mist the orchid',
          ),
        ],
      );

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_care());
      await _settle(tester);

      expect(find.byType(GardenScreen), findsOneWidget);
      expect(_highlighted(tester, 'Water the fern'), isTrue);
      expect(_highlighted(tester, 'Mist the orchid'), isFalse);
      expect(find.text(gardenTaskGoneNotice), findsNothing);
      await _drainSplash(tester);
    });

    testWidgets('a task that is done, deleted or not the user\'s says so '
        'and shows the garden', (tester) async {
      await _start(
        tester,
        tasks: [_dueTask(id: '6f1c2d3e-0000-4000-8000-000000000009')],
      );

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_care());
      await _settle(tester);

      expect(find.byType(GardenScreen), findsOneWidget);
      expect(find.text(gardenTaskGoneNotice), findsOneWidget);
      expect(_highlighted(tester, 'Water the fern'), isFalse);
      await _drainSplash(tester);
    });

    testWidgets('a multi-task reminder opens the due list', (tester) async {
      final (container, _) = await _start(tester);

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_care(count: '2'));
      await _settle(tester);

      expect(find.byType(GardenScreen), findsOneWidget);
      expect(find.text('DUE CARE'), findsOneWidget);
      expect(find.text(gardenTaskGoneNotice), findsNothing);
      expect(container.read(gardenFocusProvider), isNull, reason: 'consumed');
      await _drainSplash(tester);
    });

    testWidgets('a malformed target opens the plain garden', (tester) async {
      final (container, _) = await _start(tester);

      FirebaseMessagingPlatform.onMessageOpenedApp.add(
        _care(task: 'not-a-uuid'),
      );
      await _settle(tester);

      expect(find.byType(GardenScreen), findsOneWidget);
      expect(_highlighted(tester, 'Water the fern'), isFalse);
      expect(find.text(gardenTaskGoneNotice), findsNothing);
      expect(container.read(gardenFocusProvider), isNull);
      await _drainSplash(tester);
    });

    testWidgets('a tap while the garden is open highlights the task in the '
        'open garden, without stacking a second one', (tester) async {
      await _start(tester);

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_care(task: null));
      await _settle(tester);
      expect(find.byType(GardenScreen), findsOneWidget);
      expect(_highlighted(tester, 'Water the fern'), isFalse);

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_care());
      await _settle(tester);

      expect(find.byType(GardenScreen, skipOffstage: false), findsOneWidget);
      expect(_highlighted(tester, 'Water the fern'), isTrue);
      await _drainSplash(tester);
    });

    testWidgets('a cold-start tap highlights the task past the splash '
        'redirect', (tester) async {
      await _start(tester, initial: _care());

      await _settle(tester);
      await _drainSplash(tester);

      expect(find.byType(GardenScreen), findsOneWidget);
      expect(_highlighted(tester, 'Water the fern'), isTrue);
    });

    testWidgets('a signed-out tap lands on login, and the target does not '
        'survive the next sign-in', (tester) async {
      final (container, _) = await _start(tester, auth: const AuthState());

      FirebaseMessagingPlatform.onMessageOpenedApp.add(_care());
      await _settle(tester);
      expect(find.byType(LoginScreen), findsOneWidget);
      expect(container.read(gardenFocusProvider), isNotNull);

      (container.read(authServiceProvider.notifier) as _SwitchableAuth)
          .signInAs();
      await tester.pump();

      expect(container.read(gardenFocusProvider), isNull);
      await _drainSplash(tester);
    });
  });
}
