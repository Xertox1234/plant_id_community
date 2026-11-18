// The forum reads a password forum's unlock token opens: the topic list,
// a topic and its posts. Signed in, each waits for the stored tokens before
// its first request (a push or deep link on a cold start must not go out
// without them), and a `forum_locked` answer is never re-requested.
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

class _Harness {
  _Harness({required AuthState auth, bool retries = false}) {
    container = ProviderContainer(
      retry: retries ? null : (_, _) => null,
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
  }

  final api = FakeForumApi()
    ..topicDetail = topicDetail()
    ..posts = CursorPage(items: [post(id: 1)])
    ..topics = CursorPage(items: [topic(id: 1)]);
  final store = FakeForumUnlockStore(
    const ForumUnlocks(uid: 'u1', tokens: {3: 't3'}),
  )..loadGate = Completer<void>();
  late final ProviderContainer container;

  void dispose() => container.dispose();
}

void main() {
  group('signed in, a cold-start read waits for the stored unlocks', () {
    test('the topic list', () async {
      final h = _Harness(auth: signedInAs('u1'));
      addTearDown(h.dispose);
      h.container.listen(boardTopicsProvider('secret', 'u1'), (_, _) {});
      await pumpEventQueue();
      expect(h.api.fetchTopicsCalls, 0);

      h.store.loadGate!.complete();
      await pumpEventQueue();
      expect(h.api.fetchTopicsCalls, 1);
      expect(h.container.read(apiServiceProvider).forumUnlockTokens, [
        't3',
      ], reason: 'the request carries the stored token');
    });

    test('the topic', () async {
      final h = _Harness(auth: signedInAs('u1'));
      addTearDown(h.dispose);
      h.container.listen(topicDetailProvider(10, 'u1'), (_, _) {});
      await pumpEventQueue();
      expect(h.api.fetchTopicDetailCalls, 0);

      h.store.loadGate!.complete();
      await pumpEventQueue();
      expect(h.api.fetchTopicDetailCalls, 1);
    });

    test('the posts', () async {
      final h = _Harness(auth: signedInAs('u1'));
      addTearDown(h.dispose);
      h.container.listen(topicPostsProvider(10, 'u1'), (_, _) {});
      await pumpEventQueue();
      expect(h.api.fetchPostsCalls, isEmpty);

      h.store.loadGate!.complete();
      await pumpEventQueue();
      expect(h.api.fetchPostsCalls, hasLength(1));
    });
  });

  test('signed out, the reads do not wait', () async {
    final h = _Harness(auth: const AuthState());
    addTearDown(h.dispose);
    h.container
      ..listen(boardTopicsProvider('secret', null), (_, _) {})
      ..listen(topicDetailProvider(10, null), (_, _) {})
      ..listen(topicPostsProvider(10, null), (_, _) {});
    await pumpEventQueue();

    expect(h.api.fetchTopicsCalls, 1);
    expect(h.api.fetchTopicDetailCalls, 1);
    expect(h.api.fetchPostsCalls, hasLength(1));
    expect(h.store.loadCalls, 0);
  });

  test('a forum_locked topic list makes exactly one request', () async {
    // Riverpod's own retry policy, not the harness's "never".
    final h = _Harness(auth: const AuthState(), retries: true);
    addTearDown(h.dispose);
    h.api.topicsError = ApiException(
      'This forum needs a password.',
      statusCode: 403,
      code: 'forum_locked',
    );
    h.container.listen(boardTopicsProvider('secret', null), (_, _) {});

    // The default policy's first retries land at 200 ms and 400 ms.
    await Future<void>.delayed(const Duration(milliseconds: 900));

    expect(h.api.fetchTopicsCalls, 1);
    expect(
      h.container.read(boardTopicsProvider('secret', null)).hasError,
      true,
    );
  });
}
