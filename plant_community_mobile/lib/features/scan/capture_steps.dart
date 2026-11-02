/// What the guided camera is for.
enum ScanMode { diagnose, identify }

/// The subject a single shot covers.
enum CaptureRole {
  problem,
  leaf,
  whole,
  flower;

  String get chipLabel => switch (this) {
    CaptureRole.problem => 'Problem',
    CaptureRole.leaf => 'Leaf',
    CaptureRole.whole => 'Whole',
    CaptureRole.flower => 'Flower',
  };
}

/// Ordered capture steps for [mode].
List<CaptureRole> stepsFor(ScanMode mode) => switch (mode) {
  ScanMode.diagnose => const [
    CaptureRole.problem,
    CaptureRole.leaf,
    CaptureRole.whole,
    CaptureRole.flower,
  ],
  ScanMode.identify => const [
    CaptureRole.leaf,
    CaptureRole.whole,
    CaptureRole.flower,
  ],
};

/// The one shot that must exist before the user can finish.
CaptureRole requiredRole(ScanMode mode) => switch (mode) {
  ScanMode.diagnose => CaptureRole.problem,
  ScanMode.identify => CaptureRole.leaf,
};

/// Headline copy for a step.
String titleFor(CaptureRole role, ScanMode mode) => switch (role) {
  CaptureRole.problem => "Show me what's wrong",
  CaptureRole.leaf =>
    mode == ScanMode.identify ? 'Point at a leaf' : 'Now the whole leaf',
  CaptureRole.whole => 'Whole plant',
  CaptureRole.flower => 'A flower, if it has one',
};

/// Short instruction under the title; falls back to the title where the spec
/// gives no separate prompt.
String promptFor(CaptureRole role, ScanMode mode) => switch (role) {
  CaptureRole.problem => 'Point at the problem',
  _ => titleFor(role, mode),
};
