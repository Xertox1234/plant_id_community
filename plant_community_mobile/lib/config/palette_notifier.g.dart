// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'palette_notifier.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(PaletteNotifier)
final paletteProvider = PaletteNotifierProvider._();

final class PaletteNotifierProvider
    extends $NotifierProvider<PaletteNotifier, PaletteSettings> {
  PaletteNotifierProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'paletteProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$paletteNotifierHash();

  @$internal
  @override
  PaletteNotifier create() => PaletteNotifier();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(PaletteSettings value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<PaletteSettings>(value),
    );
  }
}

String _$paletteNotifierHash() => r'b8a612f0cf1386a3145dab152ef7a34b1c5cdae1';

abstract class _$PaletteNotifier extends $Notifier<PaletteSettings> {
  PaletteSettings build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<PaletteSettings, PaletteSettings>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<PaletteSettings, PaletteSettings>,
              PaletteSettings,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
