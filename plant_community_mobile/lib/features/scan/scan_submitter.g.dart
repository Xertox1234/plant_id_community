// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'scan_submitter.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Interim submitter: identifies the plant from [primaryShotFor]. State is the
/// upload progress (0..1), null until the first progress report.

@ProviderFor(ScanSubmitter)
final scanSubmitterProvider = ScanSubmitterProvider._();

/// Interim submitter: identifies the plant from [primaryShotFor]. State is the
/// upload progress (0..1), null until the first progress report.
final class ScanSubmitterProvider
    extends $NotifierProvider<ScanSubmitter, AsyncValue<double?>> {
  /// Interim submitter: identifies the plant from [primaryShotFor]. State is the
  /// upload progress (0..1), null until the first progress report.
  ScanSubmitterProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'scanSubmitterProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$scanSubmitterHash();

  @$internal
  @override
  ScanSubmitter create() => ScanSubmitter();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AsyncValue<double?> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AsyncValue<double?>>(value),
    );
  }
}

String _$scanSubmitterHash() => r'af1e8cfb013877b5c34e800b419beec0043b74ed';

/// Interim submitter: identifies the plant from [primaryShotFor]. State is the
/// upload progress (0..1), null until the first progress report.

abstract class _$ScanSubmitter extends $Notifier<AsyncValue<double?>> {
  AsyncValue<double?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<double?>, AsyncValue<double?>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<double?>, AsyncValue<double?>>,
              AsyncValue<double?>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
