// Collapsed forum categories (spec §7.5): the device copy paints at once,
// a member's server list replaces it, and a save PUTs the whole list, so it
// is only ever built from that server list.
import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/providers/collapsed_categories.dart';
import 'package:plant_community_mobile/features/forum/providers/forum_providers.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_unlock_store.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

class _Harness {
  _Harness({AuthState auth = const AuthState()}) {
    container = ProviderContainer(
      retry: (_, _) => null,
      overrides: [
        forumApiProvider.overrideWithValue(api),
        collapsedCategoriesStoreProvider.overrideWithValue(store),
        forumUnlockStoreProvider.overrideWithValue(FakeForumUnlockStore()),
        apiServiceProvider.overrideWithValue(
          ApiService(baseUrl: 'http://api.test', authToken: 'a'),
        ),
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: false, initial: auth),
        ),
      ],
    );
  }

  final api = FakeForumApi();
  final store = FakeCollapsedCategoriesStore();
  late final ProviderContainer container;

  /// Builds the provider, reading the fixtures set so far.
  void start() => container.listen(collapsedCategoriesProvider, (_, _) {});

  Set<int> get state => container.read(collapsedCategoriesProvider);
  CollapsedCategories get notifier =>
      container.read(collapsedCategoriesProvider.notifier);

  void setAuth(AuthState next) =>
      (container.read(authServiceProvider.notifier) as FakeAuthService).setAuth(
        next,
      );

  void dispose() => container.dispose();
}

_Harness _harness({AuthState auth = const AuthState()}) {
  final h = _Harness(auth: auth);
  addTearDown(h.dispose);
  return h;
}

void _expectMember(_Harness h, String uid, Set<int> ids) {
  expect(h.store.member?.uid, uid);
  expect(h.store.member?.ids, ids);
}

void main() {
  test('signed in: server list replaces the device copy', () async {
    final h = _Harness(auth: signedInAs('u1'));
    addTearDown(h.dispose);
    h.store.member = (uid: 'u1', ids: {1, 2});
    h.api.collapsedCategories = [3];
    h.api.collapsedFetchGate = Completer<void>();
    h.start();
    await pumpEventQueue();
    expect(h.state, {1, 2}, reason: 'the device copy paints first');

    h.api.collapsedFetchGate!.complete();
    await pumpEventQueue();
    expect(h.state, {3});
    _expectMember(h, 'u1', {3});
  });

  test('toggle saves the whole set and keeps it on success', () async {
    final h = _harness(auth: signedInAs('u1'));
    h.api.collapsedCategories = [4];
    h.start();
    await pumpEventQueue();

    expect(await h.notifier.toggle(7), isTrue);
    expect(h.api.collapsedSaves, [
      [4, 7],
    ]);
    expect(h.state, {4, 7});
    _expectMember(h, 'u1', {4, 7});
  });

  test('toggle rolls back and returns false when the save fails', () async {
    final h = _harness(auth: signedInAs('u1'));
    h.api.collapsedCategories = [4];
    h.start();
    await pumpEventQueue();
    h.api.collapsedSaveError = ApiException('x', statusCode: 500);

    final result = h.notifier.toggle(7);
    expect(h.state, {4, 7}, reason: 'the flip shows at once');
    expect(await result, isFalse);
    await pumpEventQueue();
    expect(h.state, {4});
    _expectMember(h, 'u1', {4});
  });

  test('guest toggle never calls the API and survives a rebuild', () async {
    final h = _harness()..start();
    await pumpEventQueue();
    expect(await h.notifier.toggle(2), isTrue);
    await pumpEventQueue();
    expect(h.store.guest, {2});

    h.container.invalidate(collapsedCategoriesProvider);
    await pumpEventQueue();
    expect(h.state, {2});
    expect(h.api.fetchCollapsedCalls, 0);
    expect(h.api.collapsedSaves, isEmpty);
  });

  test('profile fetch failure keeps the device copy', () async {
    final h = _harness(auth: signedInAs('u1'));
    h.store.member = (uid: 'u1', ids: {5});
    h.api.collapsedFetchError = ApiException('x', connectivity: true);
    h.start();
    await pumpEventQueue();
    expect(h.state, {5});
    _expectMember(h, 'u1', {5});
  });

  test('categories load does not wait for the collapsed fetch', () async {
    final h = _harness(auth: signedInAs('u1'));
    h.api.collapsedFetchGate = Completer<void>();
    h.start();
    h.api.categories = [categoryOf(const [])];
    final categories = await h.container.read(categoriesProvider('u1').future);
    expect(categories, hasLength(1));
    expect(h.api.collapsedFetchGate!.isCompleted, isFalse);
  });

  group('ruling 1: no PUT from an unconfirmed set', () {
    test('a toggle before the server list lands saves that list plus the '
        'flip', () async {
      final h = _harness(auth: signedInAs('u1'));
      h.store.member = (uid: 'u1', ids: {9});
      h.api.collapsedCategories = [1, 2];
      h.api.collapsedFetchGate = Completer<void>();
      h.start();
      await pumpEventQueue();

      final result = h.notifier.toggle(3);
      expect(h.state, {9, 3}, reason: 'the flip shows at once');
      await pumpEventQueue();
      expect(h.api.collapsedSaves, isEmpty, reason: 'no PUT before the load');

      h.api.collapsedFetchGate!.complete();
      expect(await result, isTrue);
      expect(h.api.collapsedSaves, [
        [1, 2, 3],
      ]);
      expect(h.state, {1, 2, 3});
      await pumpEventQueue();
      _expectMember(h, 'u1', {1, 2, 3});
    });

    test('a toggle that races the device read loses neither', () async {
      final h = _harness();
      h.store.guest = {1};
      h.store.loadGate = Completer<void>();
      h.start();

      final result = h.notifier.toggle(2);
      expect(h.state, {2});
      h.store.loadGate!.complete();
      expect(await result, isTrue);
      await pumpEventQueue();
      expect(h.state, {1, 2});
      expect(h.store.guest, {1, 2});
    });

    test('a tap on a stale device copy keeps what it asked for', () async {
      // The device shows 9 collapsed; the server no longer has it. The tap
      // expands 9, so 9 stays expanded on the server's list.
      final h = _harness(auth: signedInAs('u1'));
      h.store.member = (uid: 'u1', ids: {9});
      h.api.collapsedCategories = [1, 2];
      h.api.collapsedFetchGate = Completer<void>();
      h.start();
      await pumpEventQueue();

      final result = h.notifier.toggle(9);
      expect(h.state, isEmpty);
      h.api.collapsedFetchGate!.complete();
      expect(await result, isTrue);
      expect(h.state, {1, 2});
      expect(h.api.collapsedSaves, isEmpty, reason: 'already the server list');

      // A save that had nothing to send must not leave later taps unsaved.
      expect(await h.notifier.toggle(5), isTrue);
      expect(h.api.collapsedSaves, [
        [1, 2, 5],
      ]);
    });

    test(
      'a collapse before the first load never wipes the server list',
      () async {
        final h = _harness(auth: signedInAs('u1'));
        h.api.collapsedCategories = [9];
        h.api.collapsedFetchGate = Completer<void>();
        h.start();
        await pumpEventQueue();

        final result = h.notifier.toggle(9);
        expect(h.state, {9});
        h.api.collapsedFetchGate!.complete();
        expect(await result, isTrue);
        expect(h.state, {9});
        expect(h.api.collapsedSaves, isEmpty);

        expect(await h.notifier.toggle(5), isTrue);
        expect(h.api.collapsedSaves, [
          [5, 9],
        ]);
      },
    );

    test(
      'collapse then expand before the load, then a later tap saves',
      () async {
        final h = _harness(auth: signedInAs('u1'));
        h.api.collapsedCategories = [1];
        h.api.collapsedFetchGate = Completer<void>();
        h.start();
        await pumpEventQueue();

        final a = h.notifier.toggle(3);
        final b = h.notifier.toggle(3);
        expect(h.state, isEmpty);
        h.api.collapsedFetchGate!.complete();
        expect(await Future.wait([a, b]), [true, true]);
        expect(h.state, {1});
        expect(h.api.collapsedSaves, isEmpty);

        expect(await h.notifier.toggle(4), isTrue);
        expect(h.api.collapsedSaves, [
          [1, 4],
        ]);
      },
    );

    test(
      'a guest tap during the device read keeps what it asked for',
      () async {
        final h = _harness();
        h.store.guest = {2};
        h.store.loadGate = Completer<void>();
        h.start();

        final result = h.notifier.toggle(2);
        expect(h.state, {
          2,
        }, reason: 'it showed expanded, so the tap collapses');
        h.store.loadGate!.complete();
        expect(await result, isTrue);
        await pumpEventQueue();
        expect(h.state, {2});
        expect(h.store.guest, {2});
      },
    );

    test('a failed load is retried by the toggle', () async {
      final h = _harness(auth: signedInAs('u1'));
      h.api.collapsedCategories = [1];
      h.api.collapsedFetchError = ApiException('x', connectivity: true);
      h.start();
      await pumpEventQueue();
      expect(h.api.fetchCollapsedCalls, 1);

      h.api.collapsedFetchError = null;
      expect(await h.notifier.toggle(2), isTrue);
      expect(h.api.fetchCollapsedCalls, 2);
      expect(h.api.collapsedSaves, [
        [1, 2],
      ]);
    });

    test(
      'a load that fails again reverts the flip and returns false',
      () async {
        final h = _harness(auth: signedInAs('u1'));
        h.store.member = (uid: 'u1', ids: {5});
        h.api.collapsedFetchError = ApiException('x', connectivity: true);
        h.start();
        await pumpEventQueue();

        expect(await h.notifier.toggle(2), isFalse);
        expect(h.api.fetchCollapsedCalls, 2);
        expect(h.api.collapsedSaves, isEmpty);
        await pumpEventQueue();
        expect(h.state, {5});
        _expectMember(h, 'u1', {5});
      },
    );
  });

  group('ruling 2: one save in flight', () {
    test(
      'toggles during a save send the latest set last, one at a time',
      () async {
        final h = _harness(auth: signedInAs('u1'));
        h.start();
        await pumpEventQueue();
        final first = Completer<void>();
        h.api.collapsedSaveGates.add(first);

        final a = h.notifier.toggle(1);
        await pumpEventQueue();
        final b = h.notifier.toggle(2);
        final c = h.notifier.toggle(3);
        await pumpEventQueue();
        expect(h.api.collapsedSaves, [
          [1],
        ]);

        first.complete();
        expect(await Future.wait([a, b, c]), [true, true, true]);
        expect(h.api.collapsedSaves, [
          [1],
          [1, 2, 3],
        ]);
        expect(h.api.maxCollapsedSavesInFlight, 1);
        expect(h.api.collapsedCategories, [1, 2, 3]);
      },
    );

    test('a failure reverts to the last confirmed set, not the previous '
        'one', () async {
      final h = _harness(auth: signedInAs('u1'));
      h.api.collapsedCategories = [1];
      h.start();
      await pumpEventQueue();
      expect(await h.notifier.toggle(2), isTrue);

      final gate = Completer<void>();
      h.api.collapsedSaveGates.add(gate);
      final a = h.notifier.toggle(3);
      await pumpEventQueue();
      h.api.collapsedSaveError = ApiException('x', statusCode: 500);
      final b = h.notifier.toggle(4);
      gate.complete();
      expect(await Future.wait([a, b]), [false, false]);
      await pumpEventQueue();
      expect(h.state, {1, 2});
      _expectMember(h, 'u1', {1, 2});
    });
  });

  group('ruling 3: a viewer change mid-flight', () {
    test('a fetch begun as A never lands for B', () async {
      final h = _harness(auth: signedInAs('a'));
      h.api.collapsedCategories = [1];
      h.api.collapsedFetchGate = Completer<void>();
      h.start();
      await pumpEventQueue();

      h.setAuth(signedInAs('b'));
      h.container.read(collapsedCategoriesProvider);
      await pumpEventQueue();
      h.api.collapsedCategories = [2];
      h.api.collapsedFetchGate!.complete();
      await pumpEventQueue();
      expect(h.state, {2});
      _expectMember(h, 'b', {2});
    });

    test(
      'a save begun as A: no state, store or PUT after a sign-out',
      () async {
        final h = _harness(auth: signedInAs('a'));
        h.start();
        await pumpEventQueue();
        final gate = Completer<void>();
        h.api.collapsedSaveGates.add(gate);
        h.api.collapsedSaveError = ApiException('x', statusCode: 500);

        final a = h.notifier.toggle(1);
        await pumpEventQueue();
        h.notifier.toggle(2).ignore();
        h.setAuth(const AuthState());
        h.container.read(collapsedCategoriesProvider);
        await pumpEventQueue();
        final guestWrites = h.store.saveCalls;

        gate.complete();
        expect(
          await a,
          isTrue,
          reason: 'no "Couldn\'t save" for a gone viewer',
        );
        await pumpEventQueue();
        expect(h.api.collapsedSaves, [
          [1],
        ], reason: 'the queued second save never goes out');
        expect(h.state, isEmpty);
        expect(h.store.saveCalls, guestWrites);
        expect(h.store.guest, isNull);
      },
    );

    test('a toggle waiting on A\'s load never saves for B', () async {
      final h = _harness(auth: signedInAs('a'));
      h.api.collapsedFetchGate = Completer<void>();
      h.start();
      await pumpEventQueue();
      final a = h.notifier.toggle(1);

      h.setAuth(signedInAs('b'));
      h.container.read(collapsedCategoriesProvider);
      h.api.collapsedFetchGate!.complete();
      expect(await a, isTrue);
      await pumpEventQueue();
      expect(h.api.collapsedSaves, isEmpty);
      expect(h.state, isEmpty);
    });
  });

  group('ruling 4: a device copy per viewer', () {
    test('signing in keeps the guest copy; member B never sees A\'s', () async {
      final h = _harness()..start();
      await pumpEventQueue();
      await h.notifier.toggle(1);
      await pumpEventQueue();

      h.api.collapsedCategories = [2];
      h.setAuth(signedInAs('a'));
      h.container.read(collapsedCategoriesProvider);
      await pumpEventQueue();
      expect(h.state, {2});
      expect(h.store.guest, {1});
      _expectMember(h, 'a', {2});

      h.api.collapsedFetchGate = Completer<void>();
      h.setAuth(signedInAs('b'));
      h.container.read(collapsedCategoriesProvider);
      await pumpEventQueue();
      expect(h.state, isEmpty, reason: 'A\'s copy is not B\'s');

      h.setAuth(const AuthState());
      h.container.read(collapsedCategoriesProvider);
      await pumpEventQueue();
      expect(h.state, {1});
    });

    test('the secure store keeps the guest list plain and tags the member '
        'copy', () async {
      FlutterSecureStorage.setMockInitialValues({});
      const store = SecureCollapsedCategoriesStore();
      await store.save(null, {3, 1});
      await store.save('u1', {2});
      const storage = FlutterSecureStorage();
      expect(
        await storage.read(key: SecureCollapsedCategoriesStore.guestKey),
        jsonEncode([1, 3]),
      );
      expect(
        SecureCollapsedCategoriesStore.guestKey,
        'forum_collapsed_categories',
      );
      expect(
        jsonDecode(
          (await storage.read(key: SecureCollapsedCategoriesStore.memberKey))!,
        ),
        {
          'uid': 'u1',
          'ids': [2],
        },
      );
      expect(await store.load(null), {1, 3});
      expect(await store.load('u1'), {2});
      expect(await store.load('u2'), isNull);
    });

    test('a corrupt copy reads as none', () async {
      FlutterSecureStorage.setMockInitialValues({
        SecureCollapsedCategoriesStore.guestKey: '{not json',
        SecureCollapsedCategoriesStore.memberKey: '[1]',
      });
      const store = SecureCollapsedCategoriesStore();
      expect(await store.load(null), isNull);
      expect(await store.load('u1'), isNull);
    });
  });
}
