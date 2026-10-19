// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'live_updates_settings.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The per-device "Live updates" switch: on by default, and on whenever the
/// stored value can't be read. Follows `ThemeModeNotifier`.

@ProviderFor(LiveUpdatesSetting)
final liveUpdatesSettingProvider = LiveUpdatesSettingProvider._();

/// The per-device "Live updates" switch: on by default, and on whenever the
/// stored value can't be read. Follows `ThemeModeNotifier`.
final class LiveUpdatesSettingProvider
    extends $NotifierProvider<LiveUpdatesSetting, bool> {
  /// The per-device "Live updates" switch: on by default, and on whenever the
  /// stored value can't be read. Follows `ThemeModeNotifier`.
  LiveUpdatesSettingProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'liveUpdatesSettingProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$liveUpdatesSettingHash();

  @$internal
  @override
  LiveUpdatesSetting create() => LiveUpdatesSetting();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(bool value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<bool>(value),
    );
  }
}

String _$liveUpdatesSettingHash() =>
    r'6da97e2fe6e4f00f72dda345e6120d9a77235646';

/// The per-device "Live updates" switch: on by default, and on whenever the
/// stored value can't be read. Follows `ThemeModeNotifier`.

abstract class _$LiveUpdatesSetting extends $Notifier<bool> {
  bool build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<bool, bool>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<bool, bool>,
              bool,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
