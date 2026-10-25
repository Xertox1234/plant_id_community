# Scan 2.0 Part 1: Storage Fix + Guided Camera — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scanning work today (phase 0) and replace the `image_picker` hand-off with a full-screen, in-app guided camera that is diagnosis-first (phase 1).

**Architecture:** Phase 0 is one small PR: upload to the rules-permitted, user-scoped Storage path and sign-in-gate `/camera`. Phase 1 adds `lib/features/scan/`. It has pure capture logic (steps, session state, frame-quality heuristics, hint stabilizer) under unit tests. A thin `ScanCamera` interface wraps the `camera` plugin, so widget tests use a fake. The screen is assembled from small Canopy widgets. Until Part 2 ships the async multi-image job, **Done** bridges to the existing synchronous `identifyPlant` with one chosen shot and the existing results route.

**Tech Stack:** Flutter (Dart `^3.10`), Riverpod 3 (`@riverpod` codegen, `riverpod_annotation ^4`), go_router, `camera` plugin (new), `image_picker` (gallery only), `permission_handler`, Canopy theme (`GreenThumbExtension`, `context.canopy`).

**Spec:** `docs/superpowers/specs/2026-10-24-scan-2-0-design.md` (phases 0 and 1 of "Left to the builder → Phasing"; flow section 1 "Capture: the field guide"; "Settled after the builder check → Sign-in is required to scan").

**Later plans (not this one):** Part 2 (multi-image endpoint, Celery job, push, pill), Part 3 (results screen), Part 4 (premium guides, cache, My Guides), Part 5 (reminders, follow-up scan). Part 1 must not build any of them.

## Global Constraints

- Two PRs: **PR A = Task 1 only** (ships first, alone). **PR B = Tasks 2–8.** Feature branches only, never commit to `main`.
- Riverpod 3.x `Notifier` + `@riverpod`. Never `StateNotifier`. Run `dart run build_runner build --delete-conflicting-outputs` after any annotation change, and commit the `.g.dart` files.
- Material 3 APIs: `.withValues(alpha:)`, never `.withOpacity()`.
- Colours and spacing come from Canopy tokens (`context.canopy.*`, `GreenThumbExtension`, `AppSpacing`). No raw hex in widgets.
- Respect `MediaQuery.disableAnimationsOf(context)`. With reduce motion on, snaps and transitions jump to their end state.
- Every `StreamSubscription` and image stream must be cancelled or stopped in `dispose` / `ref.onDispose`.
- Copy is fixed by the spec. Step prompts: **"Show me what's wrong"** (with the hint **"Point at the problem"**), **"Now the whole leaf"**, **"Whole plant"**, **"A flower, if it has one"**. Identify-mode first prompt: **"Point at a leaf"**. Mode chip: **"Just identify it"**. Hints: **"Move closer"**, **"Too dark, tap ⚡"**, **"Hold steady"**. Buttons: **Skip**, **Done**.
- Rules: in diagnose mode, `problem` is required and `leaf`, `whole`, `flower` are skippable. In identify mode, `leaf` is required and `whole`, `flower` are skippable. Done is enabled once the required shot exists. Skip is visible on every non-required step, next to the shutter.
- The user always taps the shutter. No auto-capture. Hints never block the shutter.
- Captured photos: `ResolutionPreset.veryHigh`, JPEG. They must stay under `FirebaseStorageService.maxImageBytes` (5 MB). Gallery picks keep `maxWidth: 1080, maxHeight: 1080, imageQuality: 85`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Camera permission denied, or restricted (parental controls).** The user expects a clear explanation and an "Open Settings" button, not a black screen or a crash. Pinned in Task 6.
2. **The app is backgrounded mid-capture, or a call comes in.** On return the preview resumes, and the shots already taken are still in the tray. Pinned in Task 6 (a lifecycle test with the fake camera) and Task 5 (session state lives in a provider, not the widget).
3. **Signed-out user taps Scan.** They land on sign-in, never on an upload that fails with "not authorized". Pinned in Task 1.
4. **The user skips every optional step, or taps Done after one shot.** Submission works with exactly the required shot. Pinned in Tasks 3 and 7.
5. **The device has no flash or no zoom range (iPad, some Androids).** The flash button is hidden and pinch does nothing, with no exceptions. Pinned in Task 6.

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `lib/services/firebase_storage_service.dart` (modify) | user-scoped upload path, sign-in check |
| `lib/core/routing/app_router.dart` (modify) | `/camera` protected; route builds `ScanScreen` |
| `lib/features/scan/capture_steps.dart` | `ScanMode`, `CaptureRole`, step order, required rule, copy |
| `lib/features/scan/capture_session.dart` | `@riverpod` session state: mode, current step, shots |
| `lib/features/scan/frame_quality.dart` | `FrameSample`, `assessFrame()` heuristics, thresholds |
| `lib/features/scan/hint_stabilizer.dart` | debounce hints, emit the "locked" edge once |
| `lib/features/scan/scan_camera.dart` | `ScanCamera` interface + `PluginScanCamera` + factory provider |
| `lib/features/scan/scan_submitter.dart` | interim bridge: choose shot → `identifyPlant` |
| `lib/features/scan/scan_screen.dart` | full-screen assembly, lifecycle, permission states |
| `lib/features/scan/widgets/{viewfinder_frame,hint_chip,step_chips,shot_tray,capture_controls,camera_permission_view}.dart` | presentational pieces |
| `lib/features/camera/camera_screen.dart` (delete in Task 7) | replaced by `ScanScreen` |
| `test/features/scan/…` | one test file per lib file above |

---

### Task 1 (PR A): Upload to the permitted path and gate `/camera` on sign-in

**Files:**

- Modify: `plant_community_mobile/lib/services/firebase_storage_service.dart:38-70`
- Modify: `plant_community_mobile/lib/core/routing/app_router.dart:107-115` (`protectedRoutes`)
- Test: `plant_community_mobile/test/services/firebase_storage_service_test.dart`
- Test: `plant_community_mobile/test/routing/app_router_test.dart:329-365`
- Test: `plant_community_mobile/test/routing/navigation_shell_test.dart:198-245`

**Interfaces:**

- Produces: `static String FirebaseStorageService.plantImagePath(String uid, String imageId, String extension)` → `'plant-identifications/$uid/$imageId$extension'`.
- Produces: `uploadPlantImage` throws `FirebaseStorageServiceException('Sign in to identify plants.')` when `ref.read(currentUserIdProvider)` is null or empty. The check runs **after** the existing extension, size and signature validation (so the existing tests, which build the service without a container, still pass) and **before** `putFile`.

- [ ] **Step 1: Write the failing tests**

```dart
test('plant image path matches the storage rules folder', () {
  expect(
    FirebaseStorageService.plantImagePath('uid123', 'abc', '.jpg'),
    'plant-identifications/uid123/abc.jpg',
  );
});

test('storage rules still allow the folder the app uploads to', () {
  // Drift guard: the 2026-10-24 bug was the app writing plant_images/ while
  // the rules only allowed plant-identifications/{userId}/.
  final rules = File('../firebase/storage.rules').readAsStringSync();
  expect(rules, contains('match /plant-identifications/{userId}/{imageId}'));
});

test('signed-out upload is refused before touching Storage', () async {
  final container = ProviderContainer(
    overrides: [currentUserIdProvider.overrideWithValue(null)],
  );
  addTearDown(container.dispose);
  final file = File('${tempDir.path}/plant.jpg')
    ..writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0, ...List.filled(64, 0)]);
  expect(
    () => container.read(firebaseStorageServiceProvider.notifier)
        .uploadPlantImage(file.path),
    throwsA(isA<FirebaseStorageServiceException>()
        .having((e) => e.message, 'message', contains('Sign in'))),
  );
});
```

Router tests: change `'Should navigate to camera screen'` (signed-out mock) to expect a redirect to `AppRoutes.login`. Add `'Signed-in user reaches the camera'` using `_MockAuthenticatedAuthNotifier`, expecting `AppRoutes.camera`. In `navigation_shell_test.dart`, change both Identify-action tests to `pumpShell(tester, loggedIn: true)`, and add one with `loggedIn: false` asserting `h.path == AppRoutes.login`.

- [ ] **Step 2: Run them and confirm they fail**

Run: `cd plant_community_mobile && flutter test test/services/firebase_storage_service_test.dart test/routing/`
Expected: FAIL. `plantImagePath` is undefined, and the camera route is not redirected.

- [ ] **Step 3: Implement**

Add `plantImagePath`. In `uploadPlantImage`, after `_hasValidImageSignature`, read the uid and throw if absent. Then use `_storage.ref(plantImagePath(uid, imageId, extension))`. Add `AppRoutes.camera` to `protectedRoutes` (`/camera` is on the root navigator, outside the shell, so the redirect is safe; see the comment at `app_router.dart:103`).

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `flutter test test/services/ test/routing/ test/features/camera/`
Expected: PASS.

- [ ] **Step 5: Device check (owner)**

Signed in on a device or simulator: Scan, take a photo, Identify → the results screen, with no "user is not authorized". If it still fails, the deployed rules differ from `firebase/storage.rules`: compare them with `firebase deploy --only storage --dry-run`, or check the console. Stop and report rather than editing rules.

- [ ] **Step 6: Commit, push, open PR A**

```bash
git add plant_community_mobile/lib/services/firebase_storage_service.dart plant_community_mobile/lib/core/routing/app_router.dart plant_community_mobile/test/services/firebase_storage_service_test.dart plant_community_mobile/test/routing/
git commit -m "fix(mobile): upload scans to the user-scoped storage path; sign-in gate /camera"
```

---

### Task 2: Capture steps and copy

**Files:**

- Create: `plant_community_mobile/lib/features/scan/capture_steps.dart`
- Test: `plant_community_mobile/test/features/scan/capture_steps_test.dart`

**Interfaces:**

- Produces: `enum ScanMode { diagnose, identify }`
- Produces: `enum CaptureRole { problem, leaf, whole, flower }`, with `String get chipLabel` (`Problem`, `Leaf`, `Whole`, `Flower`).
- Produces: `List<CaptureRole> stepsFor(ScanMode mode)`. Diagnose → `[problem, leaf, whole, flower]`. Identify → `[leaf, whole, flower]`.
- Produces: `CaptureRole requiredRole(ScanMode mode)`. Diagnose → `problem`. Identify → `leaf`.
- Produces: `String promptFor(CaptureRole role, ScanMode mode)` and `String titleFor(CaptureRole role, ScanMode mode)`, using the Global Constraints copy. The problem step has title "Show me what's wrong" and prompt "Point at the problem". The identify-mode leaf step has prompt "Point at a leaf". Diagnose-mode leaf has title "Now the whole leaf". Whole has title "Whole plant". Flower has title "A flower, if it has one".

- [ ] **Step 1: Write the failing tests**: `stepsFor` order for each mode, `requiredRole` for each mode, the exact copy strings above, and `stepsFor(ScanMode.identify)` not containing `problem`.
- [ ] **Step 2: Run them and confirm they fail.** Run: `flutter test test/features/scan/capture_steps_test.dart`. Expected: FAIL, because the file is missing.
- [ ] **Step 3: Implement `capture_steps.dart`** as top-level functions plus enums with getters (no class needed).
- [ ] **Step 4: Run them and confirm they pass.** Same command. Expected: PASS.
- [ ] **Step 5: Commit.** `feat(mobile): scan capture steps and copy`

---

### Task 3: Capture session state

**Files:**

- Create: `plant_community_mobile/lib/features/scan/capture_session.dart` (+ generated `capture_session.g.dart`)
- Test: `plant_community_mobile/test/features/scan/capture_session_test.dart`

**Interfaces:**

- Consumes: Task 2 enums and functions.
- Produces an immutable `class CaptureSessionState` with:
  - `ScanMode mode`
  - `int stepIndex`
  - `Map<CaptureRole, String> shots` (role → local file path)
  - `CaptureRole get currentRole`
  - `bool get canFinish` (true when the required role has a shot)
  - `bool get isCurrentSkippable` (current role ≠ required role)
  - `bool get hasShotForCurrent`
  - `bool get isLastStep`
  - `copyWith`
- Produces `@riverpod class CaptureSession` (provider `captureSessionProvider`, auto-dispose) with:
  - `build()` → diagnose mode, step 0, no shots
  - `void addShot(String path)`: stores the shot for the current role, then advances to the next step that has no shot. On the last step it stays put.
  - `void skip()`: advances without a shot. A no-op when the current step is required.
  - `void jumpTo(CaptureRole role)`
  - `void retake(CaptureRole role)`: removes that shot and jumps to it
  - `void setMode(ScanMode mode)`: resets to step 0 of the new mode. Keeps an existing shot only when its role exists in the new mode. If the user already has a leaf shot when switching to identify, keep it.
  - `CaptureResult finish()`: throws `StateError` when `!canFinish`.
- Produces `class CaptureResult { final ScanMode mode; final Map<CaptureRole, String> shots; }`. Part 2 sends this as the multi-image payload.

- [ ] **Step 1: Write the failing tests** with a `ProviderContainer`. The cases:
  - Initial state is diagnose, current role `problem`, `canFinish == false`, `isCurrentSkippable == false`.
  - `skip()` on `problem` does nothing.
  - `addShot('p.jpg')` → current role `leaf`, `canFinish == true`, `isCurrentSkippable == true`.
  - `skip()` three times after the problem shot never goes past the last index, and `finish().shots` is exactly `{problem: 'p.jpg'}` (Review Focus 4).
  - `setMode(identify)` with no shots → current role `leaf`, `canFinish == false`.
  - `setMode(identify)` after shots `{problem, leaf}` → `shots == {leaf: …}`.
  - `retake(leaf)` removes the leaf and sets the current role to `leaf`.
  - `finish()` before the required shot throws `StateError`.
- [ ] **Step 2: Run them and confirm they fail.** Run: `flutter test test/features/scan/capture_session_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement**, then run `dart run build_runner build --delete-conflicting-outputs`.
- [ ] **Step 4: Run them and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(mobile): scan capture session state`

---

### Task 4: Frame-quality heuristics and hint stabilizer

**Files:**

- Create: `plant_community_mobile/lib/features/scan/frame_quality.dart`
- Create: `plant_community_mobile/lib/features/scan/hint_stabilizer.dart`
- Test: `plant_community_mobile/test/features/scan/frame_quality_test.dart`
- Test: `plant_community_mobile/test/features/scan/hint_stabilizer_test.dart`

**Interfaces:**

- Produces `class FrameSample`, a downsampled `gridW × gridH` frame:
  - `final int gridW, gridH`
  - `final Uint8List luma` (Y, 0–255)
  - `final Uint8List cb`, `final Uint8List cr` (same grid, 0–255)
  - `factory FrameSample.fromCameraImage(CameraImage image, {int gridW = 64, int gridH = 48})`, which handles `ImageFormatGroup.yuv420`: three planes on Android, and two planes (interleaved CbCr, NV12) on iOS. It block-averages into the grid.
- Produces `enum FrameHint { none, tooDark, holdSteady, moveCloser, good }`.
- Produces `FrameHint assessFrame(FrameSample current, FrameSample? previous, CaptureRole role)`. Checks run in priority order and the first match wins:
  1. `tooDark`: mean luma < `kDarkLuma` (50).
  2. `holdSteady`: `previous != null` and the mean absolute luma diff > `kMotionDiff` (12), **or** the Laplacian variance of the luma grid < `kBlurVar` (60; `kBlurVarProblem` 100 when `role == problem`).
  3. `moveCloser`: subject coverage < `kCoverage` (0.25; 0.35 for `problem`). Coverage is the fraction of cells that are *green* (`cb < 118 && cr < 125`) for leaf and whole. For `problem` it is cells that are *plant-ish* (chroma distance from (128,128) > 10 and `cr < 150`), so yellow and brown lesions count. **`flower` skips this check** (a flower can be any colour).
  4. Otherwise `good`.
- All thresholds are top-level `const`s in `frame_quality.dart`, documented as starting values to tune in Task 8.
- Produces `class HintStabilizer`:
  - `HintStabilizer({Duration hold = const Duration(milliseconds: 400), Duration lockHold = const Duration(milliseconds: 300), DateTime Function()? clock})`
  - `FrameHint? push(FrameHint raw)` returns the hint to display. It changes only after the new raw hint has persisted for `hold`, or `lockHold` for `good`.
  - `bool get justLocked`: true exactly once, on the push where the displayed hint becomes `good`. This is the haptic trigger.
- Produces `@riverpod DateTime Function() hintClock(Ref ref) => DateTime.now;`. `ScanScreen` builds its `HintStabilizer` with this clock, because fake time in widget tests does not move `DateTime.now()`.

- [ ] **Step 1: Write the failing tests** with synthetic samples from a helper `sample({int luma, int cb, int cr, bool checker = false})`. `checker` alternates the luma 0/255 across cells, which gives high Laplacian variance (sharp). Without it the luma is flat (blurry).
  - luma 30, checker → `tooDark`
  - luma 128, flat → `holdSteady`
  - luma 128, checker, the previous sample shifted by +40 luma → `holdSteady`
  - checker, grey chroma (128,128), role `leaf` → `moveCloser`
  - checker, green chroma (100,110), role `leaf` → `good`
  - checker, yellow-brown chroma (90,145), role `problem` → `good`; the same sample with role `leaf` → `moveCloser`
  - grey chroma, role `flower` → `good` (the coverage check is skipped)
  - `fromCameraImage` is **not** unit-tested (it needs a platform `CameraImage`). It is covered by the Task 8 device check.
  - Stabilizer, with an injected clock: push `moveCloser` at t=0 → `null`; at t=450ms → `moveCloser`. Push `good` at 500 and 700 → still `moveCloser`; at 820 → `good`, and `justLocked` is true once, then false on the next push.
- [ ] **Step 2: Run them and confirm they fail.** Run: `flutter test test/features/scan/frame_quality_test.dart test/features/scan/hint_stabilizer_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement.** The Laplacian is the 4-neighbour kernel over the interior cells of the luma grid, and the result is the variance of the responses. This plan says nothing more about it.
- [ ] **Step 4: Run them and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(mobile): scan frame-quality heuristics and hint stabilizer`

---

### Task 5: `ScanCamera` interface and plugin implementation

**Files:**

- Modify: `plant_community_mobile/pubspec.yaml` (`flutter pub add camera`, the latest stable)
- Create: `plant_community_mobile/lib/features/scan/scan_camera.dart` (+ `.g.dart`)
- Create: `plant_community_mobile/test/features/scan/fake_scan_camera.dart` (test helper)
- Test: `plant_community_mobile/test/features/scan/fake_scan_camera_test.dart`
- Modify: `plant_community_mobile/android/app/src/main/AndroidManifest.xml` only if the merged manifest lacks `android.permission.CAMERA`. Check with `./gradlew :app:processDebugManifest` and grep the merged file. iOS `NSCameraUsageDescription` already exists (`ios/Runner/Info.plist:44`).

**Interfaces:**

- Produces:

```dart
enum ScanCameraError { denied, restricted, unavailable }

class ScanCameraException implements Exception {
  ScanCameraException(this.error, [this.detail]);
  final ScanCameraError error;
  final String? detail;
}

abstract interface class ScanCamera {
  Future<void> initialize();              // throws ScanCameraException
  Widget buildPreview();
  bool get hasFlash;
  double get minZoom;
  double get maxZoom;
  Future<String> takePicture();           // local JPEG path
  Future<void> setTorch(bool on);
  Future<void> setFocusPoint(Offset normalized); // 0..1 in preview space
  Future<void> setZoom(double level);     // clamped to [minZoom, maxZoom]
  Future<void> startFrames(void Function(FrameSample sample) onSample);
  Future<void> stopFrames();
  Future<void> dispose();
}
```

- Produces `PluginScanCamera implements ScanCamera`. It uses the back camera, `ResolutionPreset.veryHigh`, `enableAudio: false` and `imageFormatGroup: ImageFormatGroup.yuv420`. `startFrames` throttles to one sample per **200 ms** and drops frames while a sample is being built. `takePicture` pauses the image stream around the capture and resumes it afterwards. Plugin `CameraException` codes map as follows: `CameraAccessDenied` and `CameraAccessDeniedWithoutPrompt` → `denied`, `CameraAccessRestricted` → `restricted`, and everything else (including an empty `availableCameras()`) → `unavailable`. `hasFlash` is `false` when setting the torch throws during `initialize`, which handles devices with no flash (Review Focus 5).
- Produces `@riverpod ScanCamera Function() scanCameraFactory(Ref ref) => PluginScanCamera.new;`. Tests override it.
- Produces the test helper `FakeScanCamera implements ScanCamera`, with:
  - `ScanCameraError? failWith`
  - `bool hasFlash`, `double minZoom = 1`, `double maxZoom = 1`
  - `int initializeCalls`, `int disposeCalls`
  - `void emit(FrameSample s)` to drive `onSample`
  - `String nextPicturePath`
  - `buildPreview()` returns a `ColoredBox` with key `Key('fake-preview')`.

- [ ] **Step 1: Write the failing test** for the fake, which every later widget test depends on: `failWith` makes `initialize` throw `ScanCameraException` with that error, `emit` reaches the registered callback, and `dispose` increments `disposeCalls`.
- [ ] **Step 2: Run it and confirm it fails.** Expected: FAIL.
- [ ] **Step 3: Implement the interface, the plugin class and the provider, then run build_runner.**
- [ ] **Step 4: Run `flutter analyze lib/features/scan` (expected: no issues) and the test (expected: PASS).**
- [ ] **Step 5: Commit.** `feat(mobile): ScanCamera abstraction over the camera plugin`

---

### Task 6: Scan screen: camera, overlays, controls, permission and lifecycle

**Files:**

- Create: `plant_community_mobile/lib/features/scan/scan_screen.dart`
- Create: `plant_community_mobile/lib/features/scan/widgets/viewfinder_frame.dart`, `hint_chip.dart`, `step_chips.dart`, `shot_tray.dart`, `capture_controls.dart`, `camera_permission_view.dart`
- Test: `plant_community_mobile/test/features/scan/scan_screen_test.dart`

**Interfaces:**

- Consumes: `captureSessionProvider` (Task 3), `assessFrame` and `HintStabilizer` (Task 4), `scanCameraFactoryProvider` and `ScanCamera` (Task 5), and the copy from Task 2.
- Produces `class ScanScreen extends ConsumerStatefulWidget`, with a `WidgetsBindingObserver`:
  - `inactive`/`paused` → `stopFrames()` + `dispose()`.
  - `resumed` → a new camera from the factory + `initialize()`. Session state is untouched (Review Focus 2).
- Produces `ScanScreen.onDone`, a `ValueChanged<CaptureResult>?`. When it is null, the screen calls the Task 7 submitter. The callback seam keeps this task testable without Task 7.
- Widget keys (tests depend on them):
  - `ScanScreen.shutterKey`, `skipKey`, `doneKey`, `galleryKey`, `torchKey`, `closeKey`, `modeChipKey`
  - `ValueKey('step-chip-<role.name>')`
  - `ValueKey('tray-<role.name>')`

Layout, from top to bottom over the full-bleed preview:

- the close and torch buttons;
- the title for the current step, and below it a `HintChip` that shows the stabilized hint copy, or the step prompt when the hint is `none`/`good`;
- a `ViewfinderFrame`: a rounded rect, with a neutral outline at Canopy `line` alpha 0.6. When the displayed hint is `good` it switches to Canopy primary green with a ~180 ms scale-in snap. On `justLocked` it fires `HapticFeedback.selectionClick()`;
- the `ShotTray`, one slot per step in the current mode, filled with a thumbnail and a check when shot. Tapping a filled slot calls `retake`;
- the `StepChips` row, where the current step is highlighted and a tap calls `jumpTo`. In diagnose mode the row also has the **"Just identify it"** chip, which calls `setMode(identify)`. In identify mode the same chip slot reads **"Something's wrong?"** and calls `setMode(diagnose)` (the author's call, so the owner can reverse it);
- `CaptureControls`: gallery (left), shutter (centre), and on the right **Skip** when `isCurrentSkippable && !hasShotForCurrent`, otherwise **Done**. **Done** is enabled when `canFinish`.

Other behaviour:

- Tap on the preview → `setFocusPoint`. Pinch → `setZoom`, but only when `maxZoom > minZoom`.
- The torch button is hidden when `!hasFlash`.
- The gallery uses `ImagePicker().pickImage(source: gallery, maxWidth: 1080, maxHeight: 1080, imageQuality: 85)` and treats the result as `addShot`.
- Hints and step changes are wrapped in `Semantics(liveRegion: true)`.
- With reduce motion on, the snap has no animation (the haptic still fires).
- `CameraPermissionView`:
  - `denied`: the copy "Camera access is off. Houseplant MD needs the camera to check your plant." and an **Open Settings** button (`openAppSettings()`).
  - `restricted`: the same copy without the button.
  - `unavailable`: "Camera isn't available on this device." and a **Choose from photos** button, which opens the gallery picker.
  - All three keep the close button.

- [ ] **Step 1: Write the failing widget tests.** Wrap in `ProviderScope(overrides: [scanCameraFactoryProvider.overrideWithValue(() => fake), hintClockProvider.overrideWithValue(() => fakeNow)])`, advancing `fakeNow` alongside `tester.pump`, under `AppTheme.build(Brightness.light, AppDensity.cozy)`.
  - The initial render shows the title "Show me what's wrong", the hint "Point at the problem", `find.byKey(Key('fake-preview'))`, no Skip, and Done disabled.
  - Tapping the shutter (`fake.nextPicturePath = 'p.jpg'`) fills the `tray-problem` slot, shows "Now the whole leaf", shows Skip and enables Done.
  - Skip on leaf → "Whole plant".
  - Tapping `modeChipKey` at the start → "Point at a leaf", and the step chips have no `step-chip-problem`.
  - After `fake.emit` of a green, sharp sample twice, 400 ms apart, the frame shows its locked state (find `ViewfinderFrame` with `locked: true`). Record haptic calls with `tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, …)` and expect exactly one `HapticFeedback.vibrate` call with the argument `'HapticFeedbackType.selectionClick'`.
  - A dark sample, held for 450 ms, shows "Too dark, tap ⚡".
  - `fake.failWith = denied` → the "Open Settings" button. `restricted` → no button. `unavailable` → "Choose from photos" (Review Focus 1).
  - `hasFlash: false` → `torchKey` is absent. A pinch with `minZoom == maxZoom` throws nothing (Review Focus 5).
  - Lifecycle: after one shot, `tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused)` and then `resumed` → `fake.disposeCalls == 1`, the factory has been called twice, and `tray-problem` is still filled (Review Focus 2).
  - Done with only the problem shot calls `onDone` with `shots == {problem: 'p.jpg'}`.
- [ ] **Step 2: Run them and confirm they fail.** Run: `flutter test test/features/scan/scan_screen_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement the widgets and the screen.** Read `plant_community_mobile/docs/patterns/flutter-ui-design.md` first: Canopy tokens, tap targets of 48 or more, and text scaling up to 200% without overflow on the chips and controls.
- [ ] **Step 4: Run them and confirm they pass,** plus `flutter analyze`. Expected: PASS, no issues.
- [ ] **Step 5: Commit.** `feat(mobile): guided in-app scan screen`

---

### Task 7: Interim submission, route swap, retire `CameraScreen`

**Files:**

- Create: `plant_community_mobile/lib/features/scan/scan_submitter.dart` (+ `.g.dart`)
- Modify: `plant_community_mobile/lib/core/routing/app_router.dart:421-429` (the route builds `ScanScreen`)
- Delete: `plant_community_mobile/lib/features/camera/camera_screen.dart`, `plant_community_mobile/test/features/camera/camera_screen_test.dart`
- Modify: `plant_community_mobile/test/routing/navigation_shell_test.dart` (`CameraScreen` → `ScanScreen`), `plant_community_mobile/test/integration/plant_identification_flow_test.dart` (the comments that mention `CameraScreen`)
- Test: `plant_community_mobile/test/features/scan/scan_submitter_test.dart`

**Interfaces:**

- Consumes: `CaptureResult` (Task 3), and the existing `plantIdentificationServiceProvider.notifier.identifyPlant(String imagePath, {Function(double)? onUploadProgress})`.
- Produces `String primaryShotFor(CaptureResult r)`: `leaf`, then `whole`, then `problem`, then `flower`, taking the first one present. **Temporary**, because the endpoint takes one image until Part 2.
- Produces `@riverpod class ScanSubmitter` with state `AsyncValue<double?>` (upload progress), and `Future<Plant> submit(CaptureResult r)`. It ports the old screen's behaviour:
  - fire-and-forget `firestoreServiceProvider.savePlant` when signed in;
  - the same error mapping (`ApiException` → `'API Error: …'`, `PlantIdentificationException` → its message, anything else → `'Failed to identify plant. Please try again.'`).
- `ScanScreen` default `onDone`: shows a full-screen "Checking your plant…" overlay with a **determinate** progress bar from the submitter state (this fixes the unused `_uploadProgress`). On success → `context.pushReplacement(AppRoutes.results, extra: plant)`. On error → a SnackBar, and the overlay hides with the shots still in the tray.

- [ ] **Step 1: Write the failing tests:**
  - `primaryShotFor` for `{problem}` → problem; for `{problem, leaf}` → leaf; for `{problem, whole}` → whole.
  - `submit` with an overridden fake identification service that records the path → called with the leaf path.
  - A fake that throws `PlantIdentificationException('No plant could be identified from this image.')` → `submit` rethrows it, and the state is an error.
  - Navigation shell tests now find `ScanScreen`.
- [ ] **Step 2: Run them and confirm they fail.** Expected: FAIL.
- [ ] **Step 3: Implement. Swap the route, delete the old screen and its test, and fix the references.** Then run `rg -n "CameraScreen|features/camera" plant_community_mobile/lib plant_community_mobile/test`. Expected: no matches.
- [ ] **Step 4: Run the full suite.** Run: `flutter test && flutter analyze`. Expected: all pass, no issues.
- [ ] **Step 5: Commit.** `feat(mobile): route scans through the guided camera; retire CameraScreen`

---

### Task 8: Device tuning and PR B

**Files:**

- Modify (only if tuning changes values): `plant_community_mobile/lib/features/scan/frame_quality.dart` constants, and the matching test samples.

- [ ] **Step 1: Run on a real iPhone and a real Android device** (the simulator has no camera). Check that each hint fires on purpose: cover the lens (too dark), wave the phone (hold steady), aim at a white wall (move closer), aim at a leaf (locks within about 1 s and vibrates once). Do it in a dim room and in daylight. Write the values you chose into the constants' doc comments.
- [ ] **Step 2: Measure.** The preview stays smooth with the analysis running. Run Flutter DevTools' performance overlay for 30 s of aiming: no frames over 16 ms in the UI thread caused by `assessFrame`. If there are, move `FrameSample` building to `compute()`.
- [ ] **Step 3: Check the photo size.** Five captures, each under 5 MB (`ls -l` from the app's temp dir in debug), and an end-to-end identify succeeds.
- [ ] **Step 4: Run the full suite again.** `flutter test && flutter analyze`. Expected: PASS.
- [ ] **Step 5: Commit any tuning, push, open PR B** with screenshots and a short screen recording of a guided capture.
