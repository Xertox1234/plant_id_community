// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'scan_camera.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// A factory so tests can override the camera. Screens call the result.

@ProviderFor(scanCameraFactory)
final scanCameraFactoryProvider = ScanCameraFactoryProvider._();

/// A factory so tests can override the camera. Screens call the result.

final class ScanCameraFactoryProvider
    extends
        $FunctionalProvider<
          ScanCamera Function(),
          ScanCamera Function(),
          ScanCamera Function()
        >
    with $Provider<ScanCamera Function()> {
  /// A factory so tests can override the camera. Screens call the result.
  ScanCameraFactoryProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'scanCameraFactoryProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$scanCameraFactoryHash();

  @$internal
  @override
  $ProviderElement<ScanCamera Function()> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  ScanCamera Function() create(Ref ref) {
    return scanCameraFactory(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ScanCamera Function() value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ScanCamera Function()>(value),
    );
  }
}

String _$scanCameraFactoryHash() => r'80537cef81c34825dba174e1f2f1bd5fc4ed0cbc';
