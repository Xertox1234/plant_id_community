// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'capture_session.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(CaptureSession)
final captureSessionProvider = CaptureSessionProvider._();

final class CaptureSessionProvider
    extends $NotifierProvider<CaptureSession, CaptureSessionState> {
  CaptureSessionProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'captureSessionProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$captureSessionHash();

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
}

String _$captureSessionHash() => r'8c95ecda1856e9c53988f5540dd213584f456988';

abstract class _$CaptureSession extends $Notifier<CaptureSessionState> {
  CaptureSessionState build();
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
    element.handleCreate(ref, build);
  }
}
