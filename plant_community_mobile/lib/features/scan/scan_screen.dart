import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_typography.dart';
import 'capture_session.dart';
import 'capture_steps.dart';
import 'frame_quality.dart';
import 'hint_stabilizer.dart';
import 'scan_camera.dart';
import 'scan_submitter.dart';
import 'widgets/camera_permission_view.dart';
import 'widgets/capture_controls.dart';
import 'widgets/hint_chip.dart';
import 'widgets/shot_tray.dart';
import 'widgets/submit_overlay.dart';
import 'widgets/step_chips.dart';
import 'widgets/viewfinder_frame.dart';

/// The full-screen guided scan: live preview, viewfinder, hints, the shot
/// tray, step chips and capture controls.
///
/// Session state lives in [captureSessionProvider], so the camera can be torn
/// down and rebuilt on app lifecycle changes without losing shots.
class ScanScreen extends ConsumerStatefulWidget {
  const ScanScreen({super.key, this.onDone});

  /// Receives the finished capture. Null means the default submitter.
  final ValueChanged<CaptureResult>? onDone;

  static const shutterKey = Key('scan-shutter');
  static const skipKey = Key('scan-skip');
  static const doneKey = Key('scan-done');
  static const galleryKey = Key('scan-gallery');
  static const torchKey = Key('scan-torch');
  static const closeKey = Key('scan-close');
  static const modeChipKey = Key('scan-mode-chip');

  @override
  ConsumerState<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends ConsumerState<ScanScreen>
    with WidgetsBindingObserver {
  ScanCamera? _camera;

  /// Bumped by every start and teardown; a start that sees it move aborts.
  int _epoch = 0;
  bool _starting = false;

  /// The release of the previous camera; the next start waits for it so two
  /// cameras are never open at once.
  Future<void>? _teardown;
  bool _ready = false;
  ScanCameraError? _error;
  bool _capturing = false;
  bool _torchOn = false;
  bool _submitting = false;
  double _zoom = 1;
  double _zoomAtStart = 1;

  ThemeData? _darkChrome;

  FrameSample? _previous;
  late HintStabilizer _stabilizer;
  FrameHint? _hint;

  @override
  void initState() {
    super.initState();
    // The preview crop assumes portrait; the app itself is not locked.
    unawaited(
      SystemChrome.setPreferredOrientations(const [
        DeviceOrientation.portraitUp,
      ]),
    );
    WidgetsBinding.instance.addObserver(this);
    _resetAnalysis();
    ref.listenManual(
      captureSessionProvider.select((s) => (s.mode, s.stepIndex)),
      (_, _) => setState(_resetAnalysis),
    );
    unawaited(_startCamera());
  }

  @override
  void dispose() {
    unawaited(SystemChrome.setPreferredOrientations(const []));
    WidgetsBinding.instance.removeObserver(this);
    _teardownCamera(rebuild: false);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.inactive ||
          AppLifecycleState.hidden ||
          AppLifecycleState.paused:
        _teardownCamera();
      case AppLifecycleState.resumed:
        if (_camera == null && !_starting) {
          setState(() {});
          unawaited(_startCamera());
        }
      case AppLifecycleState.detached:
        break;
    }
  }

  void _resetAnalysis() {
    _previous = null;
    _stabilizer = HintStabilizer(clock: ref.read(hintClockProvider));
    _hint = null;
  }

  // ── camera lifecycle ─────────────────────────────────────────────────────

  Future<void> _startCamera() async {
    final epoch = ++_epoch;
    // Plain assignment: this runs from initState, where setState is illegal;
    // the resume path schedules its own rebuild.
    _starting = true;
    _ready = false;
    _error = null;
    final previous = _teardown;
    if (previous != null) await previous;
    if (!mounted || epoch != _epoch) return;
    final camera = ref.read(scanCameraFactoryProvider)();
    _camera = camera;
    _starting = false;
    try {
      await camera.initialize();
    } catch (e) {
      // A camera torn down mid-initialize is stale; its error is noise.
      if (!mounted || !identical(_camera, camera)) return;
      _camera = null;
      unawaited(_quietly(camera.dispose));
      setState(
        () => _error = e is ScanCameraException
            ? e.error
            : ScanCameraError.unavailable,
      );
      return;
    }
    if (!mounted || !identical(_camera, camera)) return;
    setState(() {
      _ready = true;
      _zoom = camera.minZoom;
    });
    await _quietly(() => camera.startFrames((s) => _onSample(camera, s)));
  }

  /// Stops and disposes the live camera once; a no-op when there is none.
  void _teardownCamera({bool rebuild = true}) {
    _epoch++; // Cancels a start still waiting on a previous release.
    _starting = false;
    final camera = _camera;
    if (camera == null) return;
    _camera = null;
    _ready = false;
    _torchOn = false;
    _capturing = false;
    final release = () async {
      await _quietly(camera.stopFrames);
      await _quietly(camera.dispose);
    }();
    _teardown = release;
    unawaited(
      release.whenComplete(() {
        if (identical(_teardown, release)) _teardown = null;
      }),
    );
    if (rebuild && mounted) setState(_resetAnalysis);
  }

  /// Camera calls are best effort from gestures: never throw to the framework.
  static Future<void> _quietly(Future<void> Function() call) async {
    try {
      await call();
    } catch (_) {}
  }

  // ── frame analysis ───────────────────────────────────────────────────────

  void _onSample(ScanCamera from, FrameSample sample) {
    if (!mounted || !identical(from, _camera)) return;
    final role = ref.read(captureSessionProvider).currentRole;
    final raw = assessFrame(sample, _previous, role);
    _previous = sample;
    final shown = _stabilizer.push(raw);
    if (_stabilizer.justLocked) unawaited(HapticFeedback.selectionClick());
    if (shown != _hint) setState(() => _hint = shown);
  }

  // ── actions ──────────────────────────────────────────────────────────────

  CaptureSession get _session => ref.read(captureSessionProvider.notifier);

  Future<void> _shoot() async {
    final camera = _camera;
    if (camera == null || !_ready || _capturing) return;
    setState(() => _capturing = true);
    unawaited(HapticFeedback.lightImpact());
    String? path;
    try {
      path = await camera.takePicture();
    } catch (_) {
      path = null;
    }
    if (!mounted) return;
    setState(() => _capturing = false);
    // A shot that landed just before a teardown is still a good shot.
    if (path != null) {
      _session.addShot(path);
    } else {
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        const SnackBar(content: Text("Couldn't take that photo. Try again.")),
      );
    }
  }

  Future<void> _pickFromGallery({bool finishWhenReady = false}) async {
    XFile? file;
    try {
      file = await ImagePicker().pickImage(
        source: ImageSource.gallery,
        maxWidth: 1080,
        maxHeight: 1080,
        imageQuality: 85,
      );
    } catch (_) {
      file = null;
    }
    if (!mounted || file == null) return;
    _session.addShot(file.path);
    // With no camera there is nothing more to guide: one photo and go.
    if (finishWhenReady && ref.read(captureSessionProvider).canFinish) {
      _finish();
    }
  }

  void _finish() {
    final result = _session.finish();
    final onDone = widget.onDone;
    if (onDone != null) {
      onDone(result);
      return;
    }
    unawaited(_submit(result));
  }

  Future<void> _submit(CaptureResult result) async {
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      final plant = await ref
          .read(scanSubmitterProvider.notifier)
          .submit(result);
      if (!mounted) return;
      context.pushReplacement(AppRoutes.results, extra: plant);
    } catch (e) {
      if (!mounted) return;
      // The session is untouched, so the shots are still in the tray.
      setState(() => _submitting = false);
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        SnackBar(
          content: Text(scanErrorMessage(e)),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    }
  }

  Future<void> _toggleTorch() async {
    final camera = _camera;
    if (camera == null) return;
    final next = !_torchOn;
    setState(() => _torchOn = next);
    await _quietly(() => camera.setTorch(next));
  }

  void _focusAt(TapUpDetails d, Size size) {
    final camera = _camera;
    if (camera == null || !_ready || size.isEmpty) return;
    final p = focusPointFor(d.localPosition, size, camera.previewAspectRatio);
    unawaited(_quietly(() => camera.setFocusPoint(p)));
  }

  void _zoomBy(ScaleUpdateDetails d) {
    final camera = _camera;
    if (camera == null || !_ready || d.pointerCount < 2) return;
    if (!(camera.maxZoom > camera.minZoom)) return;
    final level = (_zoomAtStart * d.scale)
        .clamp(camera.minZoom, camera.maxZoom)
        .toDouble();
    if (level == _zoom) return;
    _zoom = level;
    unawaited(_quietly(() => camera.setZoom(level)));
  }

  // ── layout ───────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(captureSessionProvider);
    // Watched always, so the auto-dispose submitter outlives a submit.
    final upload = ref.watch(scanSubmitterProvider);
    final theme = Theme.of(context);
    // The chrome sits on a camera image, which is always dark: resolve the
    // Canopy tokens in dark mode so ink stays legible in light mode too.
    final chromeTheme = theme.brightness == Brightness.dark
        ? theme
        : _darkChrome ??= AppTheme.build(
            Brightness.dark,
            AppTheme.defaultDensity,
          );
    return Theme(
      data: chromeTheme,
      // No back-out mid-submit: the request cannot be cancelled.
      child: PopScope(
        canPop: !_submitting,
        child: Scaffold(
          backgroundColor: chromeTheme.colorScheme.scrim,
          body: Stack(
            fit: StackFit.expand,
            children: [
              if (_error == null) _buildPreview(),
              SafeArea(
                child: _error == null
                    ? _buildGuide(session)
                    : _buildError(_error!),
              ),
              if (_submitting)
                SubmitOverlay(progress: upload.hasValue ? upload.value : null),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPreview() {
    final camera = _camera;
    return LayoutBuilder(
      builder: (context, constraints) => Semantics(
        label: 'Camera preview. Tap to focus, pinch to zoom.',
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapUp: (d) => _focusAt(d, constraints.biggest),
          onScaleStart: (_) => _zoomAtStart = _zoom,
          onScaleUpdate: _zoomBy,
          child: camera != null && _ready
              ? _cover(camera, constraints.biggest)
              : const SizedBox.expand(),
        ),
      ),
    );
  }

  /// Full-bleed: the preview covers the screen and the overflow is cropped.
  Widget _cover(ScanCamera camera, Size viewport) {
    final size = coverSize(viewport, camera.previewAspectRatio);
    return ClipRect(
      child: OverflowBox(
        minWidth: size.width,
        maxWidth: size.width,
        minHeight: size.height,
        maxHeight: size.height,
        child: camera.buildPreview(),
      ),
    );
  }

  /// Ignores step changes while a shot is in flight, so it lands on the step
  /// that was showing when the shutter was pressed.
  void Function(T) _unlessCapturing<T>(void Function(T) f) => (v) {
    if (!_capturing) f(v);
  };

  Widget _buildTopBar({required bool showTorch}) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
      child: Row(
        children: [
          IconButton(
            key: ScanScreen.closeKey,
            tooltip: 'Close',
            color: cs.onSurface,
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(LucideIcons.x),
          ),
          const Spacer(),
          if (showTorch)
            IconButton(
              key: ScanScreen.torchKey,
              tooltip: _torchOn ? 'Turn off torch' : 'Turn on torch',
              isSelected: _torchOn,
              color: cs.onSurface,
              onPressed: _toggleTorch,
              icon: Icon(_torchOn ? LucideIcons.zap : LucideIcons.zapOff),
            ),
        ],
      ),
    );
  }

  Widget _buildGuide(CaptureSessionState session) {
    final cs = Theme.of(context).colorScheme;
    final role = session.currentRole;
    final title = titleFor(role, session.mode);
    final prompt = promptFor(role, session.mode);
    // The chip would only repeat the title; the frame shows the lock anyway.
    final showChip = hintCopy(_hint) != null || prompt != title;
    final fade = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 180);
    final camera = _camera;
    return Column(
      children: [
        _buildTopBar(showTorch: _ready && (camera?.hasFlash ?? false)),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          child: Semantics(
            liveRegion: true,
            header: true,
            // Already display-sized: past 1.5x the title would crowd the
            // viewfinder off small screens. Chips and hints scale fully.
            child: MediaQuery.withClampedTextScaling(
              maxScaleFactor: 1.5,
              child: AnimatedSwitcher(
                duration: fade,
                child: Text(
                  title,
                  key: ValueKey(title),
                  textAlign: TextAlign.center,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.h2.copyWith(color: cs.onSurface),
                ),
              ),
            ),
          ),
        ),
        // The chip floats over the top of the frame, so it appearing or
        // going never resizes the viewfinder.
        Expanded(
          child: Stack(
            children: [
              Positioned.fill(
                child: IgnorePointer(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.xl,
                      vertical: AppSpacing.md,
                    ),
                    child: ViewfinderFrame(locked: _hint == FrameHint.good),
                  ),
                ),
              ),
              if (showChip)
                Align(
                  alignment: Alignment.topCenter,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.lg,
                    ),
                    child: HintChip(hint: _hint, prompt: prompt),
                  ),
                ),
            ],
          ),
        ),
        ShotTray(
          mode: session.mode,
          currentRole: role,
          shots: session.shots,
          onRetake: _unlessCapturing(_session.retake),
          onJump: _unlessCapturing(_session.jumpTo),
        ),
        const SizedBox(height: AppSpacing.sm),
        StepChips(
          mode: session.mode,
          currentRole: role,
          shotRoles: session.shots.keys.toSet(),
          modeChipKey: ScanScreen.modeChipKey,
          onJump: _unlessCapturing((CaptureRole r) {
            unawaited(HapticFeedback.selectionClick());
            _session.jumpTo(r);
          }),
          onSwitchMode: () {
            if (_capturing) return;
            unawaited(HapticFeedback.selectionClick());
            _session.setMode(
              session.mode == ScanMode.diagnose
                  ? ScanMode.identify
                  : ScanMode.diagnose,
            );
          },
        ),
        const SizedBox(height: AppSpacing.sm),
        CaptureControls(
          // Skip on the last step would be a dead button (skip() no-ops
          // there), so it becomes Done.
          showSkip:
              session.isCurrentSkippable &&
              !session.hasShotForCurrent &&
              !session.isLastStep,
          canFinish: session.canFinish,
          shutterEnabled: _ready && !_capturing,
          onGallery: _pickFromGallery,
          onShutter: _shoot,
          onSkip: _session.skip,
          onDone: _finish,
          galleryKey: ScanScreen.galleryKey,
          shutterKey: ScanScreen.shutterKey,
          skipKey: ScanScreen.skipKey,
          doneKey: ScanScreen.doneKey,
        ),
        const SizedBox(height: AppSpacing.sm),
      ],
    );
  }

  Widget _buildError(ScanCameraError error) => Column(
    children: [
      _buildTopBar(showTorch: false),
      Expanded(
        child: CameraPermissionView(
          error: error,
          onOpenSettings: () => unawaited(openAppSettings()),
          onChooseFromPhotos: () => _pickFromGallery(finishWhenReady: true),
        ),
      ),
    ],
  );
}
