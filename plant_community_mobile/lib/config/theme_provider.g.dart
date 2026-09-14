// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'theme_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Theme mode notifier that manages theme state.
///
/// Defaults to DARK, matching the web (`ThemeContext.tsx` seeds `mode: 'dark'`;
/// `:root` carries the dark values). Dark is Canopy's identity, not a
/// preference — spec §3.4.
///
/// [ThemeMode.system] stays selectable. That is the one deliberate divergence
/// from the web, which offers only light/dark: following the OS setting is a
/// strong mobile platform convention, and the task explicitly allows a
/// "platform-appropriate theme selector". It changes no colour value — both
/// branches resolve to the same Canopy palette.

@ProviderFor(ThemeModeNotifier)
final themeModeProvider = ThemeModeNotifierProvider._();

/// Theme mode notifier that manages theme state.
///
/// Defaults to DARK, matching the web (`ThemeContext.tsx` seeds `mode: 'dark'`;
/// `:root` carries the dark values). Dark is Canopy's identity, not a
/// preference — spec §3.4.
///
/// [ThemeMode.system] stays selectable. That is the one deliberate divergence
/// from the web, which offers only light/dark: following the OS setting is a
/// strong mobile platform convention, and the task explicitly allows a
/// "platform-appropriate theme selector". It changes no colour value — both
/// branches resolve to the same Canopy palette.
final class ThemeModeNotifierProvider
    extends $NotifierProvider<ThemeModeNotifier, ThemeMode> {
  /// Theme mode notifier that manages theme state.
  ///
  /// Defaults to DARK, matching the web (`ThemeContext.tsx` seeds `mode: 'dark'`;
  /// `:root` carries the dark values). Dark is Canopy's identity, not a
  /// preference — spec §3.4.
  ///
  /// [ThemeMode.system] stays selectable. That is the one deliberate divergence
  /// from the web, which offers only light/dark: following the OS setting is a
  /// strong mobile platform convention, and the task explicitly allows a
  /// "platform-appropriate theme selector". It changes no colour value — both
  /// branches resolve to the same Canopy palette.
  ThemeModeNotifierProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'themeModeProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$themeModeNotifierHash();

  @$internal
  @override
  ThemeModeNotifier create() => ThemeModeNotifier();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ThemeMode value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ThemeMode>(value),
    );
  }
}

String _$themeModeNotifierHash() => r'6ed819953e4c37cd3921452d6ee8f20164e0e1b1';

/// Theme mode notifier that manages theme state.
///
/// Defaults to DARK, matching the web (`ThemeContext.tsx` seeds `mode: 'dark'`;
/// `:root` carries the dark values). Dark is Canopy's identity, not a
/// preference — spec §3.4.
///
/// [ThemeMode.system] stays selectable. That is the one deliberate divergence
/// from the web, which offers only light/dark: following the OS setting is a
/// strong mobile platform convention, and the task explicitly allows a
/// "platform-appropriate theme selector". It changes no colour value — both
/// branches resolve to the same Canopy palette.

abstract class _$ThemeModeNotifier extends $Notifier<ThemeMode> {
  ThemeMode build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<ThemeMode, ThemeMode>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<ThemeMode, ThemeMode>,
              ThemeMode,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
