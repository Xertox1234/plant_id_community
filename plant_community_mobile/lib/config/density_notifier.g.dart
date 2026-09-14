// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'density_notifier.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Layout density — the only theming dimension left besides light/dark.
///
/// This replaces `PaletteNotifier`, which also carried a four-way palette
/// choice (Loam / Garden / Forest / Heritage). Those palettes were a
/// Flutter-only invention; the design spec §2 retired the palette switcher in
/// favour of one identity, and the web has shipped a single Canopy palette
/// since. See [_migrateRetiredPaletteKey] for what happens to the stored value.

@ProviderFor(DensityNotifier)
final densityProvider = DensityNotifierProvider._();

/// Layout density — the only theming dimension left besides light/dark.
///
/// This replaces `PaletteNotifier`, which also carried a four-way palette
/// choice (Loam / Garden / Forest / Heritage). Those palettes were a
/// Flutter-only invention; the design spec §2 retired the palette switcher in
/// favour of one identity, and the web has shipped a single Canopy palette
/// since. See [_migrateRetiredPaletteKey] for what happens to the stored value.
final class DensityNotifierProvider
    extends $NotifierProvider<DensityNotifier, AppDensity> {
  /// Layout density — the only theming dimension left besides light/dark.
  ///
  /// This replaces `PaletteNotifier`, which also carried a four-way palette
  /// choice (Loam / Garden / Forest / Heritage). Those palettes were a
  /// Flutter-only invention; the design spec §2 retired the palette switcher in
  /// favour of one identity, and the web has shipped a single Canopy palette
  /// since. See [_migrateRetiredPaletteKey] for what happens to the stored value.
  DensityNotifierProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'densityProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$densityNotifierHash();

  @$internal
  @override
  DensityNotifier create() => DensityNotifier();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AppDensity value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AppDensity>(value),
    );
  }
}

String _$densityNotifierHash() => r'e32f821657ff3fa9695723586e2cd6667b71f665';

/// Layout density — the only theming dimension left besides light/dark.
///
/// This replaces `PaletteNotifier`, which also carried a four-way palette
/// choice (Loam / Garden / Forest / Heritage). Those palettes were a
/// Flutter-only invention; the design spec §2 retired the palette switcher in
/// favour of one identity, and the web has shipped a single Canopy palette
/// since. See [_migrateRetiredPaletteKey] for what happens to the stored value.

abstract class _$DensityNotifier extends $Notifier<AppDensity> {
  AppDensity build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AppDensity, AppDensity>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AppDensity, AppDensity>,
              AppDensity,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
