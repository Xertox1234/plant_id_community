import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../services/auth_service.dart';
import '../models/models.dart';
import '../services/forum_api.dart';
import 'live_updates_settings.dart';

part 'topic_missing_out.g.dart';

/// How often a signed-out reader's open topic checks for new replies.
const missingOutPollInterval = Duration(seconds: 30);

/// The signed-out "missing out" check (spec "Signed-out readers", D17).
/// Signed-out readers never get a socket; instead a peek read every
/// [missingOutPollInterval] while the app is shown. The first read sets the
/// baseline reply count. When a later read is higher, and the toast hasn't
/// shown this launch or in the last 24 h, the state (a sequence number) goes
/// up by one and the check stops for this screen.
///
/// When the toast can't show anyway, the check never starts, so it costs
/// no request.
@riverpod
class TopicMissingOut extends _$TopicMissingOut {
  Timer? _timer;
  int? _baseline;
  bool _suspended = false;
  bool _done = false;
  int _seq = 0;

  /// Bumped on every start and stop, so a start still waiting on storage
  /// can't arm a timer after it was stopped.
  int _generation = 0;

  @override
  int build(int topicId) {
    final signedIn = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    ref.onDispose(_stop);
    if (!signedIn) unawaited(_start());
    return _seq;
  }

  /// The app was hidden: no reads until [resume].
  void suspend() {
    _suspended = true;
    _stop();
  }

  void resume() {
    if (!_suspended) return;
    _suspended = false;
    if (!ref.read(authServiceProvider).isAuthenticated) unawaited(_start());
  }

  Future<void> _start() async {
    if (_done || _suspended || _timer != null) return;
    final generation = ++_generation;
    final allowed = await ref
        .read(liveToastFlagsProvider)
        .mayShowMissingOut(DateTime.now());
    if (!allowed || !ref.mounted || generation != _generation) return;
    _timer = Timer.periodic(missingOutPollInterval, (_) => unawaited(_tick()));
  }

  void _stop() {
    _generation++;
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _tick() async {
    final generation = _generation;
    final ForumTopicDetail fresh;
    try {
      fresh = await ref
          .read(forumApiProvider)
          .fetchTopicDetail(topicId, peek: true);
    } catch (_) {
      return; // Silent: the next tick tries again.
    }
    if (!ref.mounted || generation != _generation) return;
    final baseline = _baseline;
    _baseline = fresh.replyCount;
    if (baseline == null || fresh.replyCount <= baseline) return;
    final flags = ref.read(liveToastFlagsProvider);
    final now = DateTime.now();
    if (!await flags.mayShowMissingOut(now)) return;
    if (!ref.mounted || generation != _generation || _done) return;
    _done = true;
    _stop();
    unawaited(flags.markMissingOutShown(now));
    state = ++_seq;
  }
}
