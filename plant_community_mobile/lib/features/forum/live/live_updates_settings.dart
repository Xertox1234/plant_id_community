import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'live_updates_settings.g.dart';

/// Storage keys for live forum replies (spec "The setting"). Per device:
/// there is no backend field.
const liveUpdatesKey = 'forum_live_updates';
const liveIntroKey = 'forum_live_intro_shown';
const missingOutKey = 'forum_live_missing_out_at';

/// The signed-out "missing out" toast shows at most once per this long, and
/// once per app launch.
const missingOutQuiet = Duration(hours: 24);

/// The per-device "Live updates" switch: on by default, and on whenever the
/// stored value can't be read. Follows `ThemeModeNotifier`.
@Riverpod(keepAlive: true)
class LiveUpdatesSetting extends _$LiveUpdatesSetting {
  static const _storage = FlutterSecureStorage();

  /// Set once the user flips the switch, so a slow first read can't undo it.
  bool _changed = false;

  @override
  bool build() {
    unawaited(_load());
    return true;
  }

  void setEnabled(bool on) {
    _changed = true;
    state = on;
    unawaited(_save(on));
  }

  Future<void> _load() async {
    try {
      final stored = await _storage.read(key: liveUpdatesKey);
      if (ref.mounted && !_changed && stored == 'off') state = false;
    } catch (error) {
      debugPrint(
        '[FORUM_LIVE] Failed to load the live updates setting: $error',
      );
    }
  }

  Future<void> _save(bool on) async {
    try {
      await _storage.write(key: liveUpdatesKey, value: on ? 'on' : 'off');
    } catch (error) {
      debugPrint(
        '[FORUM_LIVE] Failed to save the live updates setting: $error',
      );
    }
  }
}

/// Once-per-device and once-per-launch flags for the two live-replies
/// toasts. A failed read counts as "never shown"; a failed write is ignored.
class LiveToastFlags {
  LiveToastFlags(this._storage);

  final FlutterSecureStorage _storage;

  /// Set synchronously, before any await, so two events in a row can't both
  /// take the intro.
  bool _introTaken = false;
  bool _missingOutShownThisLaunch = false;

  /// True exactly once per device: the first-time "Replies now appear live."
  /// toast is due. Recorded before the toast shows, so a crash can't repeat it.
  Future<bool> takeIntro() async {
    if (_introTaken) return false;
    _introTaken = true;
    try {
      if (await _storage.read(key: liveIntroKey) == '1') return false;
    } catch (_) {
      // Unreadable: treat as never shown.
    }
    try {
      await _storage.write(key: liveIntroKey, value: '1');
    } catch (_) {}
    return true;
  }

  /// Whether the signed-out toast may show: not yet this launch, and not
  /// within [missingOutQuiet] of the last time.
  Future<bool> mayShowMissingOut(DateTime now) async {
    if (_missingOutShownThisLaunch) return false;
    try {
      final stored = int.tryParse(
        await _storage.read(key: missingOutKey) ?? '',
      );
      if (stored == null) return true;
      final last = DateTime.fromMillisecondsSinceEpoch(stored, isUtc: true);
      return now.difference(last) >= missingOutQuiet;
    } catch (_) {
      return true;
    }
  }

  Future<void> markMissingOutShown(DateTime now) async {
    _missingOutShownThisLaunch = true;
    try {
      await _storage.write(
        key: missingOutKey,
        value: now.millisecondsSinceEpoch.toString(),
      );
    } catch (_) {}
  }
}

/// App-lifetime flags, so "once per launch" holds across topic screens.
final liveToastFlagsProvider = Provider<LiveToastFlags>(
  (ref) => LiveToastFlags(const FlutterSecureStorage()),
);
