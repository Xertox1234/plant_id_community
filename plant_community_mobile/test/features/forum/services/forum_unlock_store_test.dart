import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

ForumBoard _forum(int id, {bool locked = false}) => ForumBoard(
  id: id,
  title: 'Forum $id',
  slug: 'f$id',
  description: '',
  topicCount: 0,
  postCount: 0,
  isLocked: locked,
);

ForumUnlocks _unlocks(String uid, Map<int, String> tokens) =>
    ForumUnlocks(uid: uid, tokens: tokens);

/// Answers each categories fetch only when the test completes its entry in
/// [answers], in whatever order the test chooses.
class _SequencedApi extends FakeForumApi {
  final answers = <Completer<List<ForumCategory>>>[];

  @override
  Future<List<ForumCategory>> fetchCategories() {
    fetchCategoriesCalls++;
    final answer = Completer<List<ForumCategory>>();
    answers.add(answer);
    return answer.future;
  }
}

class _Harness {
  _Harness({
    required AuthState auth,
    FakeForumUnlockStore? store,
    FakeForumApi? api,
    ApiService? apiService,
  }) : store = store ?? FakeForumUnlockStore(),
       api = api ?? FakeForumApi(),
       apiService =
           apiService ??
           ApiService(baseUrl: 'http://api.test', authToken: 'a') {
    container = ProviderContainer(
      // Off so a failed fetch settles at once and counts stay exact.
      retry: (_, _) => null,
      overrides: [
        forumApiProvider.overrideWithValue(this.api),
        forumUnlockStoreProvider.overrideWithValue(this.store),
        apiServiceProvider.overrideWithValue(this.apiService),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: false, initial: auth),
        ),
      ],
    );
    container.listen(authServiceProvider, (_, _) {});
  }

  final FakeForumUnlockStore store;
  final FakeForumApi api;
  final ApiService apiService;
  late final ProviderContainer container;

  void setAuth(AuthState next) =>
      (container.read(authServiceProvider.notifier) as FakeAuthService).setAuth(
        next,
      );

  Future<Map<int, String>> unlocks() =>
      container.read(forumUnlocksProvider.future);

  ForumUnlocksController get notifier =>
      container.read(forumUnlocksProvider.notifier);

  /// Keeps the current viewer's autoDispose feed alive and waits for it.
  Future<List<ForumCategory>> categories() {
    container.listen(viewerCategoriesProvider, (_, _) {});
    final viewer = container.read(forumViewerProvider);
    return container.read(categoriesProvider(viewer).future);
  }

  void dispose() => container.dispose();
}

void main() {
  group('SecureForumUnlockStore', () {
    setUp(() => FlutterSecureStorage.setMockInitialValues({}));

    test('store round-trips, removes and clears', () async {
      const store = SecureForumUnlockStore();
      expect(await store.load(), isNull);

      await store.save(_unlocks('u1', {3: 'a', 7: 'b'}));
      var loaded = await store.load();
      expect(loaded?.uid, 'u1');
      expect(loaded?.tokens, {3: 'a', 7: 'b'});
      expect(loaded?.tokens.keys, [3, 7], reason: 'order is kept');

      await store.save(_unlocks('u1', {7: 'b'}));
      loaded = await store.load();
      expect(loaded?.tokens, {7: 'b'});

      await store.clear();
      expect(await store.load(), isNull);
      expect(
        await const FlutterSecureStorage().read(
          key: SecureForumUnlockStore.storageKey,
        ),
        isNull,
      );
    });

    for (final (name, raw) in [
      ('not JSON', '{nope'),
      ('a list', '[1, 2]'),
      ('no uid', '{"tokens": {"1": "a"}}'),
      ('tokens not a map', '{"uid": "u1", "tokens": "a"}'),
    ]) {
      test('corrupt stored value ($name) loads as no unlocks', () async {
        FlutterSecureStorage.setMockInitialValues({
          SecureForumUnlockStore.storageKey: raw,
        });
        expect(await const SecureForumUnlockStore().load(), isNull);
      });
    }

    test('bad entries are skipped, good ones kept', () async {
      FlutterSecureStorage.setMockInitialValues({
        SecureForumUnlockStore.storageKey:
            '{"uid": "u1", "tokens": {"x": "a", "2": 5, "3": "", "4": "ok"}}',
      });
      final loaded = await const SecureForumUnlockStore().load();
      expect(loaded?.tokens, {4: 'ok'});
    });
  });

  group('forumUnlocksProvider', () {
    test('signed out at launch leaves the store untouched', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final h = _Harness(auth: const AuthState(), store: store);
      addTearDown(h.dispose);

      expect(await h.unlocks(), isEmpty);
      expect(store.loadCalls, 0);
      expect(store.clearCalls, 0);
      expect(store.stored?.tokens, {1: 't1'});
      expect(h.apiService.forumUnlockTokens, isEmpty);
    });

    test('a Firebase user still waiting on its JWT is not signed in', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final h = _Harness(
        auth: AuthState(firebaseUser: FakeFirebaseUser('u2')),
        store: store,
      );
      addTearDown(h.dispose);

      expect(await h.unlocks(), isEmpty);
      expect(store.clearCalls, 0, reason: 'nobody signed in to clear for');
    });

    test('tokens survive an app restart for the same member', () async {
      final store = FakeForumUnlockStore();
      final first = _Harness(auth: signedInAs('u1'), store: store);
      await first.unlocks();
      await first.notifier.add(5, 't5');
      first.dispose();

      // A new launch: the session restores after the first frame.
      final second = _Harness(auth: const AuthState(), store: store);
      addTearDown(second.dispose);
      expect(await second.unlocks(), isEmpty);
      second.setAuth(signedInAs('u1'));
      expect(await second.unlocks(), {5: 't5'});
      expect(second.apiService.forumUnlockTokens, ['t5']);
    });

    test('tokens stored for another uid are cleared, not sent', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final h = _Harness(auth: signedInAs('u2'), store: store);
      addTearDown(h.dispose);

      expect(await h.unlocks(), isEmpty);
      expect(store.stored, isNull);
      expect(h.apiService.forumUnlockTokens, isEmpty);
    });

    test('a member switch while the load is in flight sends nothing of the '
        'first member', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}))
        ..loadGate = Completer<void>();
      final h = _Harness(auth: signedInAs('u1'), store: store);
      addTearDown(h.dispose);
      final firstLoad = h.unlocks();
      await pumpEventQueue();
      h.setAuth(const AuthState());
      store.loadGate!.complete();

      expect(await h.unlocks(), isEmpty);
      expect(await firstLoad, isEmpty);
      await pumpEventQueue();
      expect(h.apiService.forumUnlockTokens, isEmpty);
    });

    test('a member change clears the header at once, before anything reads '
        'the unlocks again', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final h = _Harness(auth: signedInAs('u1'), store: store);
      addTearDown(h.dispose);
      await h.unlocks();
      expect(h.apiService.forumUnlockTokens, ['t1']);

      h.setAuth(signedInAs('u2'));
      await pumpEventQueue();
      expect(h.apiService.forumUnlockTokens, isEmpty);
    });

    test('add, drop and clear keep the store and the header in step', () async {
      final store = FakeForumUnlockStore();
      final h = _Harness(auth: signedInAs('u1'), store: store);
      addTearDown(h.dispose);
      await h.unlocks();

      await h.notifier.add(1, 't1');
      await h.notifier.add(2, 't2');
      expect(h.apiService.forumUnlockTokens, ['t2', 't1'], reason: 'newest');
      expect(store.stored?.uid, 'u1');
      expect(store.stored?.tokens, {1: 't1', 2: 't2'});

      await h.notifier.drop(1, ifToken: 'other');
      expect(store.stored?.tokens, {1: 't1', 2: 't2'}, reason: 'not that one');
      await h.notifier.drop(1);
      expect(await h.unlocks(), {2: 't2'});
      expect(h.apiService.forumUnlockTokens, ['t2']);

      await h.notifier.clear();
      expect(await h.unlocks(), isEmpty);
      expect(store.stored, isNull);
      expect(h.apiService.forumUnlockTokens, isEmpty);
    });

    test('only the newest 20 are sent', () {
      final tokens = {for (var i = 0; i < 25; i++) i: 't$i'};
      final sent = forumUnlockEntriesToSend(tokens);
      expect(sent.map((e) => e.key), [for (var i = 24; i >= 5; i--) i]);
    });
  });

  group('categoriesProvider and the unlock tokens', () {
    test(
      'categories fetch waits for the unlock load on a cold start',
      () async {
        final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}))
          ..loadGate = Completer<void>();
        final api = FakeForumApi()
          ..categories = [
            categoryOf([_forum(1)]),
          ];
        final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
        addTearDown(h.dispose);

        final feed = h.categories();
        await pumpEventQueue();
        expect(api.fetchCategoriesCalls, 0);
        expect(h.apiService.forumUnlockTokens, isEmpty);

        store.loadGate!.complete();
        await feed;
        expect(api.fetchCategoriesCalls, 1);
        expect(h.apiService.forumUnlockTokens, ['t1']);
      },
    );

    test('a forum still locked after load drops its stored token', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1', 2: 't2'}));
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1, locked: true), _forum(2)]),
        ];
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);

      await h.categories();
      await pumpEventQueue();
      expect(await h.unlocks(), {2: 't2'});
      expect(store.stored?.tokens, {2: 't2'});
      expect(h.apiService.forumUnlockTokens, ['t2']);
    });

    test('a token added while a fetch is in flight is not dropped by that '
        'response', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 'old'}));
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1, locked: true), _forum(2, locked: true)]),
        ]
        ..fetchCategoriesGate = Completer<void>();
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);

      final feed = h.categories();
      await pumpEventQueue();
      expect(api.fetchCategoriesCalls, 1);
      // Unlocked again (forum 1) and for the first time (forum 2) while
      // the request that answers "locked" is still out.
      await h.notifier.add(1, 'new');
      await h.notifier.add(2, 't2');
      api.fetchCategoriesGate!.complete();
      await feed;
      await pumpEventQueue();

      expect(await h.unlocks(), {1: 'new', 2: 't2'});
    });

    test('an older answer arriving after a newer one drops nothing', () async {
      // The newer request found the forum open; the older one's "locked"
      // answer is out of date by the time it lands.
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final api = _SequencedApi();
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);
      unawaited(h.categories());
      await pumpEventQueue();
      final viewer = h.container.read(forumViewerProvider);
      unawaited(
        h.container.read(categoriesProvider(viewer).notifier).refresh(),
      );
      await pumpEventQueue();
      expect(api.answers, hasLength(2));

      api.answers[1].complete([
        categoryOf([_forum(1)]),
      ]);
      await pumpEventQueue();
      api.answers[0].complete([
        categoryOf([_forum(1, locked: true)]),
      ]);
      await pumpEventQueue();
      expect(await h.unlocks(), {1: 't1'});
    });

    test('a failed fetch drops no token', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final api = FakeForumApi()
        ..categoriesError = ApiException('gone', statusCode: 404);
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);

      await expectLater(h.categories(), throwsA(isA<ApiException>()));
      await pumpEventQueue();
      expect(await h.unlocks(), {1: 't1'});
    });

    test(
      'an answer to a request sent with no Authorization drops nothing',
      () async {
        final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
        final api = FakeForumApi()
          ..categories = [
            categoryOf([_forum(1, locked: true)]),
          ];
        final h = _Harness(
          auth: signedInAs('u1'),
          store: store,
          api: api,
          apiService: ApiService(baseUrl: 'http://api.test'),
        );
        addTearDown(h.dispose);

        await h.categories();
        await pumpEventQueue();
        expect(await h.unlocks(), {1: 't1'});
      },
    );

    test('a token that was not sent (past the 20) is not dropped', () async {
      // Forum 0 is the OLDEST of 21 unlocks, so it is the one not sent.
      final tokens = {for (var i = 0; i <= 20; i++) i: 't$i'};
      final store = FakeForumUnlockStore(_unlocks('u1', tokens));
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(0, locked: true), _forum(20, locked: true)]),
        ];
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);

      await h.categories();
      await pumpEventQueue();
      final left = await h.unlocks();
      expect(left.containsKey(0), isTrue, reason: 'never sent');
      expect(left.containsKey(20), isFalse, reason: 'sent, still locked');
    });

    test('a failed refresh over a previous value drops no token', () async {
      // The first answer shows forum 1 locked (nothing to unlock it yet);
      // the member then unlocks it, and the refresh fails. The previous
      // value still says "locked", but it is not an answer to the token.
      final store = FakeForumUnlockStore(_unlocks('u1', const {}));
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1, locked: true)]),
        ];
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);
      await h.categories();
      await h.notifier.add(1, 't1');

      api.categoriesError = ApiException('down', statusCode: 503);
      h.container.invalidate(categoriesProvider);
      await pumpEventQueue();
      final feed = h.container.read(viewerCategoriesProvider);
      expect(feed.hasError, isTrue);
      expect(feed.value, isNotNull, reason: 'the previous value is still held');
      expect(await h.unlocks(), {1: 't1'});
      expect(store.stored?.tokens, {1: 't1'});
    });

    test('a token that is not in the header when the request goes out is '
        'not dropped', () async {
      // The header is what the server saw: a token the app holds but did
      // not send cannot have been refused.
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}));
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1, locked: true)]),
        ];
      final h = _Harness(auth: signedInAs('u1'), store: store, api: api);
      addTearDown(h.dispose);
      await h.unlocks();
      h.apiService.setForumUnlockTokens(const []);

      await h.categories();
      await pumpEventQueue();
      expect(await h.unlocks(), {1: 't1'});
      expect(store.saveCalls, 0);
    });

    test('a guest fetch does not wait for or touch the unlocks', () async {
      final store = FakeForumUnlockStore(_unlocks('u1', {1: 't1'}))
        ..loadGate = Completer<void>();
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1)]),
        ];
      final h = _Harness(auth: const AuthState(), store: store, api: api);
      addTearDown(h.dispose);

      await h.categories();
      expect(api.fetchCategoriesCalls, 1);
      expect(store.loadCalls, 0);
    });
  });

  group('boardsProvider', () {
    test('a viewer change whose refetch fails drops the previous member\'s '
        'forums', () async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1), _forum(2)]),
        ];
      final h = _Harness(auth: signedInAs('u1'), api: api);
      addTearDown(h.dispose);
      h.container.listen(boardsProvider, (_, _) {});
      await pumpEventQueue();
      expect(h.container.read(boardsProvider).value?.map((b) => b.id), [1, 2]);

      api.categoriesError = ApiException('down', statusCode: 503);
      h.setAuth(signedInAs('u2'));
      await pumpEventQueue();
      final after = h.container.read(boardsProvider);
      expect(after.hasValue, isFalse);
      expect(after.hasError, isTrue);
    });

    test('leaves out forums still locked for the viewer', () async {
      final api = FakeForumApi()
        ..categories = [
          categoryOf([_forum(1), _forum(2, locked: true)]),
          categoryOf([_forum(3, locked: true), _forum(4)], id: 2),
        ];
      final h = _Harness(auth: signedInAs('u1'), api: api);
      addTearDown(h.dispose);

      h.container.listen(boardsProvider, (_, _) {});
      await pumpEventQueue();
      final boards = h.container.read(boardsProvider).requireValue;
      expect(boards.map((b) => b.id), [1, 4]);
    });
  });
}
