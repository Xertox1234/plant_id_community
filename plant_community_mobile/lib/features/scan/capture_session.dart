import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'capture_steps.dart';

part 'capture_session.g.dart';

/// Immutable snapshot of an in-progress guided capture.
class CaptureSessionState {
  const CaptureSessionState({
    this.mode = ScanMode.diagnose,
    this.stepIndex = 0,
    this.shots = const {},
  });

  final ScanMode mode;
  final int stepIndex;

  /// role -> local file path
  final Map<CaptureRole, String> shots;

  CaptureRole get currentRole => stepsFor(mode)[stepIndex];
  bool get canFinish => shots.containsKey(requiredRole(mode));
  bool get isCurrentSkippable => currentRole != requiredRole(mode);
  bool get hasShotForCurrent => shots.containsKey(currentRole);
  bool get isLastStep => stepIndex == stepsFor(mode).length - 1;

  CaptureSessionState copyWith({
    ScanMode? mode,
    int? stepIndex,
    Map<CaptureRole, String>? shots,
  }) => CaptureSessionState(
    mode: mode ?? this.mode,
    stepIndex: stepIndex ?? this.stepIndex,
    shots: shots ?? this.shots,
  );
}

/// What a finished capture hands to the identification/diagnosis call.
class CaptureResult {
  const CaptureResult({required this.mode, required this.shots});

  final ScanMode mode;
  final Map<CaptureRole, String> shots;
}

@riverpod
class CaptureSession extends _$CaptureSession {
  @override
  CaptureSessionState build() => const CaptureSessionState();

  /// Stores [path] for the current role, then moves to the next later step
  /// with no shot. Stays put when there is none; never wraps.
  void addShot(String path) {
    final steps = stepsFor(state.mode);
    final shots = {...state.shots, state.currentRole: path};
    var next = state.stepIndex;
    for (var i = state.stepIndex + 1; i < steps.length; i++) {
      if (!shots.containsKey(steps[i])) {
        next = i;
        break;
      }
    }
    state = state.copyWith(shots: shots, stepIndex: next);
  }

  /// Advances without a shot. No-op on the required step or the last step.
  void skip() {
    if (!state.isCurrentSkippable || state.isLastStep) return;
    state = state.copyWith(stepIndex: state.stepIndex + 1);
  }

  void jumpTo(CaptureRole role) {
    final index = stepsFor(state.mode).indexOf(role);
    if (index < 0) return;
    state = state.copyWith(stepIndex: index);
  }

  void retake(CaptureRole role) {
    if (!stepsFor(state.mode).contains(role)) return;
    state = state.copyWith(shots: {...state.shots}..remove(role));
    jumpTo(role);
  }

  /// Switches mode, back to step 0, keeping shots whose role exists in it.
  void setMode(ScanMode mode) {
    final roles = stepsFor(mode);
    state = CaptureSessionState(
      mode: mode,
      stepIndex: 0,
      shots: {
        for (final e in state.shots.entries)
          if (roles.contains(e.key)) e.key: e.value,
      },
    );
  }

  CaptureResult finish() {
    if (!state.canFinish) {
      throw StateError('Cannot finish before the required shot exists');
    }
    return CaptureResult(
      mode: state.mode,
      shots: Map.unmodifiable(state.shots),
    );
  }
}
