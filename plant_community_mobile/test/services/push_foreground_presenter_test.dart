// Foreground pushes (todo 621): a restrained in-app banner plus a data
// refresh, deduplicated, silent for routine moderation events and while
// signed out, and torn down on disposal and account changes.

import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_foreground_presenter.dart';
import 'package:plant_community_mobile/services/push_message_router_service.dart';

RemoteMessage _reply({String? id = 'm-1', String? title = 'New reply'}) =>
    RemoteMessage(
      messageId: id,
      data: const {'event': 'reply_added', 'topic_id': '42', 'post_id': '7'},
      notification: RemoteNotification(title: title, body: 'Alex replied'),
    );

class _Harness {
  _Harness() {
    presenter = PushForegroundPresenter(
      messages: controller.stream,
      showBanner: banners.add,
      refresh: (event, data) => refreshes.add(event),
      isSignedIn: () => signedIn,
      open: opened.add,
    );
  }

  final controller = StreamController<RemoteMessage>.broadcast();
  final banners = <ForegroundBanner>[];
  final refreshes = <String?>[];
  final opened = <RemoteMessage>[];
  bool signedIn = true;
  late final PushForegroundPresenter presenter;

  Future<void> send(RemoteMessage message) async {
    controller.add(message);
    await pumpEventQueue();
  }

  Future<void> close() async {
    presenter.dispose();
    await controller.close();
  }
}

void main() {
  late _Harness h;

  setUp(() => h = _Harness());
  tearDown(() => h.close());

  test('a forum push shows one banner and refreshes its data', () async {
    await h.send(_reply());

    expect(h.banners, hasLength(1));
    expect(h.banners.single.title, 'New reply');
    expect(h.banners.single.body, 'Alex replied');
    expect(h.refreshes, ['reply_added']);
  });

  test('View opens what the push is about, as a tray tap would', () async {
    final message = _reply();
    await h.send(message);

    h.banners.single.onView();

    expect(h.opened, [message]);
  });

  test(
    'the same message delivered twice is shown and refreshed once',
    () async {
      await h.send(_reply());
      await h.send(_reply());

      expect(h.banners, hasLength(1));
      expect(h.refreshes, hasLength(1));
    },
  );

  test('a duplicate without a message id is caught by its payload', () async {
    await h.send(_reply(id: null));
    await h.send(_reply(id: null));

    expect(h.banners, hasLength(1));
  });

  test('distinct messages each show', () async {
    await h.send(_reply(id: 'm-1'));
    await h.send(_reply(id: 'm-2'));

    expect(h.banners, hasLength(2));
  });

  test('a moderation decision refreshes silently, with no banner', () async {
    await h.send(
      const RemoteMessage(
        messageId: 'm-3',
        data: {'event': 'moderation_decided', 'status': 'published'},
        notification: RemoteNotification(title: 'Published', body: 'Yours'),
      ),
    );

    expect(h.banners, isEmpty);
    expect(h.refreshes, ['moderation_decided']);
  });

  test('a data-only message refreshes silently', () async {
    await h.send(
      const RemoteMessage(messageId: 'm-4', data: {'event': 'topic_created'}),
    );

    expect(h.banners, isEmpty);
    expect(h.refreshes, ['topic_created']);
  });

  test('a care reminder shows its banner and refreshes the garden', () async {
    await h.send(
      const RemoteMessage(
        messageId: 'm-5',
        data: {'event': careTaskDueEvent, 'count': '1'},
        notification: RemoteNotification(
          title: 'Water the fern',
          body: 'Fern is due for care.',
        ),
      ),
    );

    expect(h.banners.single.title, 'Water the fern');
    expect(h.refreshes, [careTaskDueEvent]);
  });

  test('nothing surfaces while signed out', () async {
    h.signedIn = false;

    await h.send(_reply());

    expect(h.banners, isEmpty);
    expect(h.refreshes, isEmpty);
  });

  test(
    'an account change forgets the ids seen for the previous account',
    () async {
      await h.send(_reply());
      h.presenter.accountChanged();
      await h.send(_reply());

      expect(h.banners, hasLength(2));
    },
  );

  test('dispose stops listening', () async {
    h.presenter.dispose();

    await h.send(_reply());

    expect(h.banners, isEmpty);
    expect(h.controller.hasListener, isFalse);
  });

  test('a refresh that throws still shows the banner', () async {
    final failing = PushForegroundPresenter(
      messages: h.controller.stream,
      showBanner: h.banners.add,
      refresh: (_, _) => throw StateError('provider gone'),
      isSignedIn: () => true,
      open: h.opened.add,
    );
    addTearDown(failing.dispose);
    h.presenter.dispose();

    await h.send(_reply());

    expect(h.banners, hasLength(1));
  });

  test('the remembered ids are bounded', () async {
    for (var i = 0; i <= PushForegroundPresenter.rememberedIds; i++) {
      await h.send(_reply(id: 'id-$i'));
    }
    // id-0 was evicted, so it shows again; the newest is still remembered.
    await h.send(_reply(id: 'id-0'));
    await h.send(_reply(id: 'id-${PushForegroundPresenter.rememberedIds}'));

    expect(h.banners, hasLength(PushForegroundPresenter.rememberedIds + 2));
  });

  group('the provider (wired in MyApp)', () {
    testWidgets('listens to the foreground stream until disposed, and the '
        'banner is a SnackBar with a View action', (tester) async {
      final messages = StreamController<RemoteMessage>.broadcast();
      addTearDown(messages.close);
      final container = ProviderContainer(
        overrides: [
          foregroundMessagesProvider.overrideWithValue(messages.stream),
          authServiceProvider.overrideWith(_SignedIn.new),
        ],
      );
      final messengerKey = GlobalKey<ScaffoldMessengerState>();
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            scaffoldMessengerKey: messengerKey,
            home: const Scaffold(body: SizedBox()),
          ),
        ),
      );
      container.read(pushForegroundPresenterProvider);
      expect(messages.hasListener, isTrue);

      // The real banner widget, on a messenger.
      showForegroundBannerSnackBar(
        messengerKey.currentState,
        ForegroundBanner(
          title: 'New reply',
          body: 'Alex replied',
          onView: () {},
        ),
      );
      await tester.pump();
      expect(find.text('New reply'), findsOneWidget);
      expect(find.text('View'), findsOneWidget);

      // Disposal cancels the provider's listener.
      container.dispose();
      await tester.pump();
      expect(messages.hasListener, isFalse);
      await tester.pump(const Duration(seconds: 5));
    });
  });
}

class _SignedIn extends AuthService {
  @override
  AuthState build() => const AuthState(jwtToken: 'jwt');
}
