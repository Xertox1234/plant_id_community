// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'capture_session.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Keyed by the mode the camera opens in, so that mode is the very first
/// state: no frame ever shows the other mode's steps.

@ProviderFor(CaptureSession)
final captureSessionProvider = CaptureSessionFamily._();

/// Keyed by the mode the camera opens in, so that mode is the very first
/// state: no frame ever shows the other mode's steps.
final class CaptureSessionProvider
    extends $NotifierProvider<CaptureSession, CaptureSessionState> {
  /// Keyed by the mode the camera opens in, so that mode is the very first
  /// state: no frame ever shows the other mode's steps.
  CaptureSessionProvider._({
    required CaptureSessionFamily super.from,
    required ScanMode super.argument,
  }) : super(
         retry: null,
         name: r'captureSessionProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$captureSessionHash();

  @override
  String toString() {
    return r'captureSessionProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  CaptureSession create() => CaptureSession();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(CaptureSessionState value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<CaptureSessionState>(value),
    );
  }

  @override
  bool operator ==(Object other) {
    return other is CaptureSessionProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$captureSessionHash() => r'36896cb3914d9ba99775092093121578a95178a9';

/// Keyed by the mode the camera opens in, so that mode is the very first
/// state: no frame ever shows the other mode's steps.

final class CaptureSessionFamily extends $Family
    with
        $ClassFamilyOverride<
          CaptureSession,
          CaptureSessionState,
          CaptureSessionState,
          CaptureSessionState,
          ScanMode
        > {
  CaptureSessionFamily._()
    : super(
        retry: null,
        name: r'captureSessionProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Keyed by the mode the camera opens in, so that mode is the very first
  /// state: no frame ever shows the other mode's steps.

  CaptureSessionProvider call(ScanMode initialMode) =>
      CaptureSessionProvider._(argument: initialMode, from: this);

  @override
  String toString() => r'captureSessionProvider';
}

/// Keyed by the mode the camera opens in, so that mode is the very first
/// state: no frame ever shows the other mode's steps.

abstract class _$CaptureSession extends $Notifier<CaptureSessionState> {
  late final _$args = ref.$arg as ScanMode;
  ScanMode get initialMode => _$args;

  CaptureSessionState build(ScanMode initialMode);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<CaptureSessionState, CaptureSessionState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<CaptureSessionState, CaptureSessionState>,
              CaptureSessionState,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
  }
}
