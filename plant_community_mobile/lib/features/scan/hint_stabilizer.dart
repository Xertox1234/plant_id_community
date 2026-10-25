import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'frame_quality.dart';

part 'hint_stabilizer.g.dart';

/// Clock used by the scan screen's [HintStabilizer]. Overridable in widget
/// tests, where fake time does not move `DateTime.now()`.
@riverpod
DateTime Function() hintClock(Ref ref) => DateTime.now;

/// Debounces raw per-frame hints so the UI does not flicker.
class HintStabilizer {
  HintStabilizer({
    this.hold = const Duration(milliseconds: 400),
    this.lockHold = const Duration(milliseconds: 300),
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final Duration hold;
  final Duration lockHold;
  final DateTime Function() _clock;

  FrameHint? _displayed;
  FrameHint? _pending;
  DateTime? _pendingSince;
  bool _justLocked = false;

  /// True only on the push where the displayed hint became [FrameHint.good].
  bool get justLocked => _justLocked;

  /// Returns the hint to display: null until one has been shown, then the
  /// current displayed hint (possibly unchanged).
  FrameHint? push(FrameHint raw) {
    _justLocked = false;
    if (raw == _displayed) {
      _pending = null;
      _pendingSince = null;
      return _displayed;
    }
    final now = _clock();
    if (raw != _pending) {
      _pending = raw;
      _pendingSince = now;
      return _displayed;
    }
    final needed = raw == FrameHint.good ? lockHold : hold;
    if (now.difference(_pendingSince!) >= needed) {
      _displayed = raw;
      _pending = null;
      _pendingSince = null;
      _justLocked = raw == FrameHint.good;
    }
    return _displayed;
  }
}
