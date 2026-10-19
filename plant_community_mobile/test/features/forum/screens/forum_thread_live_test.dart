// Live replies on the thread screen (forum live replies, slice 4): the
// socket through a fake connector, the pill, the highlight, pull-to-refresh,
// lifecycle, and both toasts.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/live/forum_live_client.dart';
import 'package:plant_community_mobile/features/forum/live/live_updates_settings.dart';
import 'package:plant_community_mobile/features/forum/live/topic_missing_out.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_thread_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/live_flash.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

ForumPost _reply(int id, [String? text]) =>
    post(id: id, body: [ParagraphBlock(text ?? 'Reply $id')]);

class _Live {
  _Live() {
    api
      ..topicDetail = topicDetail(replyCount: 1)
      ..posts = CursorPage(items: [_reply(1, 'Opening'), _reply(2)])
      ..replyStatus = ForumModerationStatus.published;
  }

  final api = FakeForumApi();
  final connector = FakeLiveConnector();
  late GoRouter router;

  FakeLiveChannel get channel => connector.last;

  Widget app({bool loggedIn = true, bool reduceMotion = false}) {
    router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (_, _) => const ForumThreadScreen(topicId: 10),
        ),
        GoRoute(
          path: '/forum/compose',
          name: 'forumCompose',
          builder: (_, state) =>
              ForumComposerScreen(args: state.extra as ForumComposeArgs),
        ),
        GoRoute(
          path: '/login',
          name: 'login',
          builder: (_, _) => const Scaffold(body: Text('LOGIN PAGE')),
        ),
        GoRoute(
          path: '/register',
          name: 'register',
          builder: (_, _) => const Scaffold(body: Text('REGISTER PAGE')),
        ),
      ],
    );
    return ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        apiServiceProvider.overrideWithValue(
          ApiService(
            baseUrl: 'http://localhost:8000/api/v1',
            authToken: loggedIn ? 'test-jwt' : null,
          ),
        ),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: loggedIn),
        ),
        ...liveTestOverrides(connector),
      ],
      child: MaterialApp.router(
        routerConfig: router,
        builder: (context, child) => reduceMotion
            ? MediaQuery(
                data: MediaQuery.of(context).copyWith(disableAnimations: true),
                child: child!,
              )
            : child!,
      ),
    );
  }

  Future<void> open(WidgetTester tester, {bool loggedIn = true}) async {
    await tester.pumpWidget(app(loggedIn: loggedIn));
    await tester.pumpAndSettle();
  }
}

const _intro = 'Replies now appear live.';

void main() {
  late Map<String, String> store;

  setUp(() {
    store = {};
    FlutterSecureStorage.setMockInitialValues(store);
  });

  testWidgets('flag off: one connect, no retry, no pill, no toast', (
    tester,
  ) async {
    final l = _Live();
    // The catch-up would count one new reply. In prod the 4503 close
    // arrives before the catch-up's HTTP round trip does.
    l.api
      ..peekGate = Completer<void>()
      ..peekDetails = [topicDetail(replyCount: 2)];
    await l.open(tester);

    l.channel.serverClose(liveCloseDisabled);
    await tester.pump();
    l.api.peekGate!.complete();
    await tester.pump(const Duration(minutes: 2));
    await tester.pumpAndSettle();

    expect(l.connector.connects, hasLength(1));
    expect(find.textContaining('new repl'), findsNothing);
    expect(find.byType(SnackBar), findsNothing);
  });

  testWidgets('a reply at the bottom slides in with the intro toast; Turn off '
      'closes the socket and Undo reconnects', (tester) async {
    final l = _Live();
    l.api.postsById[3] = _reply(3, 'Live reply');
    await l.open(tester);

    l.channel.serverEvent('post.created', postId: 3);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Live reply'), findsOneWidget);
    expect(find.byType(LiveFlash), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(LiveFlash),
        matching: find.byType(SizeTransition),
      ),
      findsOneWidget,
    );
    await tester.pumpAndSettle();
    // The highlight has run its 2.5 s and gone.
    expect(find.byType(LiveFlash), findsNothing);
    expect(find.text(_intro), findsOneWidget);
    expect(store[liveIntroKey], '1');

    await tester.tap(find.text('Turn off'));
    await tester.pumpAndSettle();
    expect(l.channel.closedByClient, isTrue);
    expect(store[liveUpdatesKey], 'off');
    expect(find.text('Live updates off'), findsOneWidget);

    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(l.connector.connects, hasLength(2));
    expect(store[liveUpdatesKey], 'on');
  });

  testWidgets('the intro toast shows once per device', (tester) async {
    final l = _Live();
    l.api.postsById
      ..[3] = _reply(3)
      ..[4] = _reply(4);
    await l.open(tester);
    l.channel.serverEvent('post.created', postId: 3);
    await tester.pumpAndSettle();
    expect(find.text(_intro), findsOneWidget);

    // A new launch of the screen on the same device.
    await tester.pumpWidget(const SizedBox());
    final again = _Live()..api.postsById[4] = _reply(4);
    await again.open(tester);
    again.channel.serverEvent('post.created', postId: 4);
    await tester.pumpAndSettle();

    expect(find.text('Reply 4'), findsOneWidget);
    expect(find.text(_intro), findsNothing);
  });

  testWidgets('scrolled up: the pill counts, and tapping it loads, highlights '
      'and reveals the first new reply', (tester) async {
    final l = _Live();
    final first = [for (var i = 1; i <= 20; i++) _reply(i)];
    final second = [for (var i = 21; i <= 40; i++) _reply(i)];
    l.api
      ..topicDetail = topicDetail(replyCount: 39)
      ..postPages = [
        CursorPage(items: first, next: 'p2'),
        CursorPage(items: second),
      ]
      ..postsById[41] = _reply(41, 'Brand new reply');
    await l.open(tester);

    l.channel.serverEvent('post.created', postId: 41);
    await tester.pumpAndSettle();
    expect(find.text('1 new reply'), findsOneWidget);
    expect(find.text('Brand new reply'), findsNothing);
    // The first pill also brings the intro toast; close it.
    await tester.tap(find.byIcon(Icons.close));
    await tester.pumpAndSettle();

    l.api.postPages = [
      CursorPage(items: first, next: 'p2'),
      CursorPage(items: [...second, _reply(41, 'Brand new reply')]),
    ];
    await tester.tap(find.text('1 new reply'));
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    expect(find.text('1 new reply'), findsNothing);
    expect(find.byType(LiveFlash), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('Brand new reply').hitTestable(), findsOneWidget);
  });

  testWidgets('a reader at the bottom of a long thread sees a live reply, '
      'and the next one slides in too', (tester) async {
    final l = _Live();
    l.api
      ..topicDetail = topicDetail(replyCount: 29)
      ..posts = CursorPage(items: [for (var i = 1; i <= 30; i++) _reply(i)])
      ..postsById[31] = _reply(31, 'Live thirty-one')
      ..postsById[32] = _reply(32, 'Live thirty-two');
    await l.open(tester);
    await tester.fling(find.byType(ListView), const Offset(0, -20000), 5000);
    await tester.pumpAndSettle();

    l.channel.serverEvent('post.created', postId: 31);
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.close)); // the intro toast
    await tester.pumpAndSettle();
    expect(find.text('Live thirty-one').hitTestable(), findsOneWidget);

    l.channel.serverEvent('post.created', postId: 32);
    await tester.pumpAndSettle();
    expect(find.textContaining('new repl'), findsNothing);
    expect(find.text('Live thirty-two').hitTestable(), findsOneWidget);
  });

  testWidgets('another screen pushed over the thread closes the socket, and '
      'coming back reconnects', (tester) async {
    final l = _Live();
    await l.open(tester);

    unawaited(l.router.push('/register'));
    await tester.pumpAndSettle();
    expect(l.channel.closedByClient, isTrue);

    l.router.pop();
    await tester.pumpAndSettle();
    expect(l.connector.connects, hasLength(2));
  });

  testWidgets('own reply never counts', (tester) async {
    final l = _Live();
    await l.open(tester);

    await tester.tap(find.text('Reply'));
    await tester.pumpAndSettle();
    // The server broadcasts the reply while the composer is still open.
    l.api
      ..postsById[3] = _reply(3, 'My own reply')
      ..posts = CursorPage(
        items: [_reply(1, 'Opening'), _reply(2), _reply(3, 'My own reply')],
      );
    l.channel.serverEvent('post.created', postId: 3);
    await tester.pump();
    await tester.enterText(find.byType(TextField).last, 'My own reply');
    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(find.text('My own reply'), findsOneWidget);
    expect(find.textContaining('new repl'), findsNothing);
    expect(find.text(_intro), findsNothing);
    expect(store[liveIntroKey], isNull);
  });

  testWidgets('edit splices in place and keeps the scroll offset', (
    tester,
  ) async {
    final l = _Live();
    l.api
      ..topicDetail = topicDetail(replyCount: 29)
      ..posts = CursorPage(items: [for (var i = 1; i <= 30; i++) _reply(i)])
      ..postsById[4] = _reply(4, 'Edited four');
    await l.open(tester);
    await tester.drag(find.byType(ListView), const Offset(0, -150));
    await tester.pumpAndSettle();
    final scrollable = tester.state<ScrollableState>(
      find.byType(Scrollable).first,
    );
    final offset = scrollable.position.pixels;

    l.channel.serverEvent('post.updated', postId: 4);
    await tester.pumpAndSettle();

    expect(find.text('Edited four'), findsOneWidget);
    expect(find.text('Reply 4'), findsNothing);
    expect(scrollable.position.pixels, offset);
  });

  testWidgets('delete removes the card', (tester) async {
    final l = _Live();
    await l.open(tester);
    expect(find.text('Reply 2'), findsOneWidget);

    l.channel.serverEvent('post.removed', postId: 2);
    await tester.pumpAndSettle();

    expect(find.text('Reply 2'), findsNothing);
  });

  testWidgets('topic.updated relocks the topic: the Reply button goes away '
      'after the debounce', (tester) async {
    final l = _Live();
    l.api.peekDetails = [
      topicDetail(replyCount: 1),
      topicDetail(replyCount: 1, locked: true),
    ];
    await l.open(tester);
    expect(find.text('Reply'), findsOneWidget);

    l.channel.serverEvent('topic.updated');
    await tester.pump(const Duration(milliseconds: 499));
    expect(find.text('Reply'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 1));
    await tester.pumpAndSettle();

    expect(find.text('Reply'), findsNothing);
  });

  testWidgets(
    'topic.removed shows "This topic is no longer available." and no Reply '
    'button',
    (tester) async {
      final l = _Live();
      await l.open(tester);

      l.channel.serverEvent('topic.removed');
      await tester.pumpAndSettle();

      expect(find.text('This topic is no longer available.'), findsOneWidget);
      expect(find.text('Reply'), findsNothing);
      expect(find.text('Reply 2'), findsNothing);
      expect(l.channel.closedByClient, isTrue);
    },
  );

  testWidgets('hide closes, show reconnects once and offers missed replies', (
    tester,
  ) async {
    final l = _Live();
    await l.open(tester);
    expect(l.connector.connects, hasLength(1));

    tester.binding
      ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
      ..handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    await tester.pump();
    expect(l.channel.closedByClient, isTrue);

    l.api.peekDetails = [
      topicDetail(replyCount: 1),
      topicDetail(replyCount: 3),
    ];
    await tester.pump(const Duration(minutes: 5));
    tester.binding
      ..handleAppLifecycleStateChanged(AppLifecycleState.inactive)
      ..handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();

    expect(l.connector.connects, hasLength(2));
    expect(find.text('2 new replies'), findsOneWidget);
  });

  testWidgets('pull-to-refresh loads a new reply with the setting off', (
    tester,
  ) async {
    store[liveUpdatesKey] = 'off';
    final l = _Live();
    await l.open(tester);
    expect(l.connector.connects, isEmpty);

    l.api.posts = CursorPage(
      items: [_reply(1, 'Opening'), _reply(2), _reply(3, 'Pulled in')],
    );
    await tester.fling(find.text('Opening'), const Offset(0, 400), 1000);
    await tester.pumpAndSettle();

    expect(find.text('Pulled in'), findsOneWidget);
    expect(l.connector.connects, isEmpty);
  });

  testWidgets('signed out: no socket, and the missing-out toast after the '
      'count grows, with Sign in and Sign up', (tester) async {
    final l = _Live();
    l.api.peekDetails = [
      topicDetail(replyCount: 1),
      topicDetail(replyCount: 2),
    ];
    await l.open(tester, loggedIn: false);

    await tester.pump(missingOutPollInterval);
    await tester.pump(missingOutPollInterval);
    await tester.pumpAndSettle();

    expect(l.connector.connects, isEmpty);
    expect(
      find.text(
        'New replies are coming in. Sign in or sign up to follow along live.',
      ),
      findsOneWidget,
    );
    expect(find.text('Sign up'), findsOneWidget);

    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('LOGIN PAGE'), findsOneWidget);
  });

  testWidgets('reduce motion: an inserted reply is highlighted but not '
      'animated', (tester) async {
    final l = _Live();
    l.api.postsById[3] = _reply(3, 'Calm reply');
    await tester.pumpWidget(l.app(reduceMotion: true));
    await tester.pumpAndSettle();

    l.channel.serverEvent('post.created', postId: 3);
    await tester.pump();
    await tester.pump();

    expect(find.byType(LiveFlash), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(LiveFlash),
        matching: find.byType(SizeTransition),
      ),
      findsNothing,
    );
    await tester.pumpAndSettle();
  });
}
