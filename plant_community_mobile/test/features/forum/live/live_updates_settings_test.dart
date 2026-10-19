// The per-device "Live updates" setting and the toast flags (live forum
// replies, slice 4), both in FlutterSecureStorage.
import 'dart:collection';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/live_updates_settings.dart';

/// A storage backing map whose every read throws, as a broken keychain does.
class _ThrowingMap extends MapBase<String, String> {
  @override
  String? operator [](Object? key) => throw StateError('keychain locked');
  @override
  void operator []=(String key, String value) =>
      throw StateError('keychain locked');
  @override
  void clear() {}
  @override
  Iterable<String> get keys => const [];
  @override
  String? remove(Object? key) => null;
}

void main() {
  late Map<String, String> store;

  setUp(() {
    store = {};
    FlutterSecureStorage.setMockInitialValues(store);
  });

  group('LiveUpdatesSetting', () {
    test('defaults to on', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      expect(container.read(liveUpdatesSettingProvider), isTrue);
      await pumpEventQueue();
      expect(container.read(liveUpdatesSettingProvider), isTrue);
    });

    test('stored off is read back after load', () async {
      store[liveUpdatesKey] = 'off';
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(liveUpdatesSettingProvider);
      await pumpEventQueue();

      expect(container.read(liveUpdatesSettingProvider), isFalse);
    });

    test("setEnabled(false) writes 'off'", () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(liveUpdatesSettingProvider);
      await pumpEventQueue();

      container.read(liveUpdatesSettingProvider.notifier).setEnabled(false);
      await pumpEventQueue();

      expect(container.read(liveUpdatesSettingProvider), isFalse);
      expect(
        await const FlutterSecureStorage().read(key: liveUpdatesKey),
        'off',
      );
    });

    test('a storage read that throws leaves it on', () async {
      FlutterSecureStorage.setMockInitialValues(_ThrowingMap());
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(liveUpdatesSettingProvider);
      await pumpEventQueue();

      expect(container.read(liveUpdatesSettingProvider), isTrue);
    });
  });

  group('LiveToastFlags', () {
    const storage = FlutterSecureStorage();
    final now = DateTime.utc(2026, 10, 19, 12);

    test('takeIntro is true once, then false, across a new LiveToastFlags on '
        'the same storage', () async {
      expect(await LiveToastFlags(storage).takeIntro(), isTrue);
      expect(await LiveToastFlags(storage).takeIntro(), isFalse);
      expect(store[liveIntroKey], '1');
    });

    test('two takeIntro calls in a row cannot both be true', () async {
      final flags = LiveToastFlags(storage);
      final results = await Future.wait([flags.takeIntro(), flags.takeIntro()]);
      expect(results, [true, false]);
    });

    test(
      'mayShowMissingOut is false after markMissingOutShown in the same launch',
      () async {
        final flags = LiveToastFlags(storage);
        expect(await flags.mayShowMissingOut(now), isTrue);
        await flags.markMissingOutShown(now);
        // Even a day later: once per app launch.
        expect(
          await flags.mayShowMissingOut(now.add(const Duration(days: 2))),
          isFalse,
        );
      },
    );

    test('false within 24 h of the stored time in a new launch', () async {
      store[missingOutKey] = now
          .subtract(missingOutQuiet)
          .add(const Duration(seconds: 1))
          .millisecondsSinceEpoch
          .toString();

      expect(await LiveToastFlags(storage).mayShowMissingOut(now), isFalse);
    });

    test('true again after 24 h', () async {
      store[missingOutKey] = now
          .subtract(missingOutQuiet)
          .millisecondsSinceEpoch
          .toString();

      expect(await LiveToastFlags(storage).mayShowMissingOut(now), isTrue);
    });

    test('a broken store counts as never shown and ignores writes', () async {
      FlutterSecureStorage.setMockInitialValues(_ThrowingMap());
      final flags = LiveToastFlags(storage);

      expect(await flags.mayShowMissingOut(now), isTrue);
      await flags.markMissingOutShown(now);
      expect(await flags.mayShowMissingOut(now), isFalse);
      expect(await flags.takeIntro(), isTrue);
    });
  });
}
