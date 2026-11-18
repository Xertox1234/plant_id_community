import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart' show setEquals;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../services/forum_api.dart';
import 'forum_providers.dart' show forumViewerProvider;

part 'collapsed_categories.g.dart';

/// The device copy of the collapsed forum categories, one per viewer: a
/// guest's under its own key, a member's under another, tagged with their
/// uid. Every method is total: a storage failure or a corrupt value reads
/// as "no copy" and never throws.
abstract class CollapsedCategoriesStore {
  /// The copy for [viewer] (null = the guest), or null when there is none,
  /// it can't be read, or it belongs to another member.
  Future<Set<int>?> load(String? viewer);

  Future<void> save(String? viewer, Set<int> ids);
}

/// [CollapsedCategoriesStore] in flutter_secure_storage, as
/// `LiveUpdatesSetting`: [guestKey] holds a plain JSON list, [memberKey]
/// holds `{"uid": ..., "ids": [...]}`. A member's save replaces the previous
/// member's copy and never touches the guest's.
class SecureCollapsedCategoriesStore implements CollapsedCategoriesStore {
  const SecureCollapsedCategoriesStore([
    this._storage = const FlutterSecureStorage(),
  ]);

  static const String guestKey = 'forum_collapsed_categories';
  static const String memberKey = 'forum_collapsed_categories_member';

  final FlutterSecureStorage _storage;

  @override
  Future<Set<int>?> load(String? viewer) async {
    try {
      final raw = await _storage.read(
        key: viewer == null ? guestKey : memberKey,
      );
      if (raw == null) return null;
      final data = jsonDecode(raw);
      if (viewer == null) return _ids(data);
      if (data is! Map || data['uid'] != viewer) return null;
      return _ids(data['ids']);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> save(String? viewer, Set<int> ids) async {
    final list = ids.toList()..sort();
    try {
      if (viewer == null) {
        await _storage.write(key: guestKey, value: jsonEncode(list));
      } else {
        await _storage.write(
          key: memberKey,
          value: jsonEncode({'uid': viewer, 'ids': list}),
        );
      }
    } catch (_) {
      // Storage unavailable: the toggle still works for this launch.
    }
  }

  static Set<int>? _ids(Object? data) {
    if (data is! List) return null;
    return {for (final id in data) ?(id is int ? id : null)};
  }
}

/// Injectable so tests can use an in-memory store.
final collapsedCategoriesStoreProvider = Provider<CollapsedCategoriesStore>(
  (ref) => const SecureCollapsedCategoriesStore(),
);

/// Which forum-index categories the viewer has collapsed (spec §7.5),
/// matching the web's `useCollapsedCategories`.
///
/// [build] starts empty and applies the viewer's device copy once it is
/// read; signed in, it also fetches the member's list from their forum
/// profile, which then replaces the state and the device copy. A failed
/// fetch keeps the device copy silently. Nothing here delays the categories
/// feed. Rebuilt for every viewer change: work begun for one viewer never
/// touches the state, the device copy or the network once it is another's.
///
/// A save PUTs the whole list, so it is only ever built from the member's
/// server list with their pending taps re-applied, never from the device
/// copy, and only one is in flight at a time. [refresh] re-reads that list
/// when the forum tab refreshes its categories, so a list changed on the web
/// meanwhile is not overwritten by the next save.
@Riverpod(keepAlive: true)
class CollapsedCategories extends _$CollapsedCategories {
  /// Bumped by every [build].
  int _builds = 0;
  String? _viewer;

  /// The member's list as the server last confirmed it; null until loaded.
  Set<int>? _confirmed;

  /// What each tap made while the member's list was not in hand (before the
  /// first load, or during a refresh) asked for: id to collapsed, the last
  /// tap wins. Forced onto whichever list lands. Not a flip: the lists may
  /// disagree about an id, and a flip re-applied to the other list would
  /// invert the tap.
  Map<int, bool> _pending = {};

  /// True while a fetch of the member's list is in flight (the first load,
  /// its retry or a [refresh]). Toggles made meanwhile wait for it.
  bool _fetching = false;

  Future<void> _deviceRead = Future<void>.value();
  Future<void> _deviceWrites = Future<void>.value();
  Future<bool>? _loading;
  Future<bool>? _saving;

  @override
  Set<int> build() {
    final viewer = ref.watch(forumViewerProvider);
    final build = ++_builds;
    _viewer = viewer;
    _confirmed = null;
    _pending = {};
    _fetching = false;
    _loading = null;
    _saving = null;
    _deviceRead = _readDevice(build);
    _deviceWrites = _deviceRead;
    if (viewer != null) _loading = _load(build);
    return const {};
  }

  bool _superseded(int build) => !ref.mounted || build != _builds;

  /// Collapse or expand [categoryId]. The change shows at once. Returns
  /// false when a member's change could not be saved and was undone. Work
  /// overtaken by a viewer change is dropped and reports true: nothing is
  /// left to tell the new viewer about.
  Future<bool> toggle(int categoryId) async {
    final build = _builds;
    final collapse = !state.contains(categoryId);
    state = _with(state, {categoryId: collapse});
    final waiting = _confirmed == null || _fetching;
    if (waiting) _pending[categoryId] = collapse;
    _writeDevice(build);
    if (_viewer == null) return true;

    if (waiting) {
      final loaded = await _ensureLoaded(build);
      if (_superseded(build)) return true;
      if (!loaded) {
        // Undone, unless a later tap on the same id has replaced this one.
        if (_pending[categoryId] == collapse) {
          _pending.remove(categoryId);
          state = _with(state, {categoryId: !collapse});
          _writeDevice(build);
        }
        return false;
      }
    }
    // Checked here, not only in the loop: a loop with nothing to send would
    // finish before its first await, clear [_saving] in its `finally`, and
    // only then be stored by the `??=` below as a completed future that
    // every later toggle would join without saving.
    if (_saving == null && setEquals(state, _confirmed)) return true;
    return _saving ??= _saveLoop(build);
  }

  /// [base] with each id in [taps] collapsed (true) or expanded (false).
  static Set<int> _with(Set<int> base, Map<int, bool> taps) => {
    for (final id in base)
      if (taps[id] != false) id,
    for (final e in taps.entries)
      if (e.value) e.key,
  };

  Future<void> _readDevice(int build) async {
    final stored = await ref
        .read(collapsedCategoriesStoreProvider)
        .load(_viewer);
    if (_superseded(build) || _confirmed != null) return;
    state = _with(stored ?? const {}, _pending);
  }

  /// Queues a write of the current state, after the device read (so a flip
  /// can't lose to it) and after every earlier write.
  void _writeDevice(int build) {
    _deviceWrites = _deviceWrites.then((_) async {
      if (_superseded(build)) return;
      await ref
          .read(collapsedCategoriesStoreProvider)
          .save(_viewer, Set.of(state));
    });
  }

  /// Re-reads the member's list (the forum tab's pull-to-refresh and
  /// Retry), replacing the state and the device copy. Never awaited by the
  /// categories feed. Skipped for a guest, while a fetch is already in
  /// flight, and while a save is in flight: that save PUTs the whole list,
  /// so a list read during it could be overwritten by it or overwrite the
  /// taps it carries. A failed refresh changes nothing.
  Future<void> refresh() async {
    if (_viewer == null || _fetching || _saving != null) return;
    final build = _builds;
    _loading = _load(build);
    await _loading;
  }

  /// Fetches the member's list. A superseded fetch returns without touching
  /// [_fetching]: [build] has already reset it for the new viewer, whose own
  /// fetch may be in flight, and clearing it would let their toggles skip
  /// waiting for their list.
  Future<bool> _load(int build) async {
    _fetching = true;
    final List<int> server;
    try {
      server = await ref.read(forumApiProvider).fetchCollapsedCategories();
    } catch (_) {
      if (_superseded(build)) return false;
      _fetching = false;
      // A failed refresh: the taps made during it are already in the state
      // and are saved against the list held before it.
      if (_confirmed != null) _pending = {};
      return false;
    }
    if (_superseded(build)) return false;
    _fetching = false;
    final confirmed = server.toSet();
    _confirmed = confirmed;
    state = _with(confirmed, _pending);
    _pending = {};
    _writeDevice(build);
    return true;
  }

  /// Waits for the member's list; a first load that failed is tried once
  /// more. After a failed refresh the list held before it stands.
  Future<bool> _ensureLoaded(int build) async {
    final current = _loading;
    if (current != null && await current) return true;
    if (_superseded(build)) return false;
    if (_confirmed != null) return true;
    // Another toggle may already have started the retry.
    if (identical(_loading, current)) _loading = _load(build);
    return _loading!;
  }

  /// Saves until the server holds the current set, one PUT at a time, so an
  /// older set never lands last. Only started when there is something to
  /// send, so its first pass always awaits a PUT. A failure goes back to the
  /// last confirmed set and fails every toggle waiting on it.
  Future<bool> _saveLoop(int build) async {
    try {
      while (true) {
        final next = Set.of(state);
        if (setEquals(next, _confirmed)) return true;
        try {
          await ref
              .read(forumApiProvider)
              .saveCollapsedCategories(next.toList()..sort());
        } catch (_) {
          if (_superseded(build)) return true;
          state = Set.of(_confirmed!);
          _writeDevice(build);
          return false;
        }
        if (_superseded(build)) return true;
        _confirmed = next;
      }
    } finally {
      if (!_superseded(build)) _saving = null;
    }
  }
}
