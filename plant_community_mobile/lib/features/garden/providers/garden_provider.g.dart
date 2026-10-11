// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'garden_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Everything the garden screen shows: the user's plants and their pending
/// care tasks, fetched together. Mutations invalidate this provider.

@ProviderFor(garden)
final gardenProvider = GardenProvider._();

/// Everything the garden screen shows: the user's plants and their pending
/// care tasks, fetched together. Mutations invalidate this provider.

final class GardenProvider
    extends
        $FunctionalProvider<
          AsyncValue<GardenData>,
          GardenData,
          FutureOr<GardenData>
        >
    with $FutureModifier<GardenData>, $FutureProvider<GardenData> {
  /// Everything the garden screen shows: the user's plants and their pending
  /// care tasks, fetched together. Mutations invalidate this provider.
  GardenProvider._()
    : super(
        from: null,
        argument: null,
        retry: gardenRetry,
        name: r'gardenProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$gardenHash();

  @$internal
  @override
  $FutureProviderElement<GardenData> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<GardenData> create(Ref ref) {
    return garden(ref);
  }
}

String _$gardenHash() => r'7d6f2a17b904c01924a81d1ef573fadd15a5ba5f';
