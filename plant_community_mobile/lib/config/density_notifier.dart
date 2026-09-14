import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../core/theme/app_theme.dart';
import '../core/theme/green_thumb_extension.dart';

part 'density_notifier.g.dart';

/// Layout density — the only theming dimension left besides light/dark.
///
/// This replaces `PaletteNotifier`, which also carried a four-way palette
/// choice (Loam / Garden / Forest / Heritage). Those palettes were a
/// Flutter-only invention; the design spec §2 retired the palette switcher in
/// favour of one identity, and the web has shipped a single Canopy palette
/// since. See [_migrateRetiredPaletteKey] for what happens to the stored value.
@riverpod
class DensityNotifier extends _$DensityNotifier {
  static const _storage = FlutterSecureStorage();

  /// Unchanged from the previous implementation ON PURPOSE: a user who had
  /// chosen a density keeps it across the upgrade.
  static const densityKey = 'palette_density';

  /// The key the retired palette choice was stored under.
  static const retiredPaletteKey = 'palette_choice';

  @override
  AppDensity build() {
    unawaited(_loadSaved());
    return AppTheme.defaultDensity;
  }

  void setDensity(AppDensity density) {
    state = density;
    unawaited(_write(density));
  }

  Future<void> _write(AppDensity density) async {
    try {
      await _storage.write(key: densityKey, value: density.name);
    } catch (e) {
      debugPrint('[THEME] Failed to save density: $e');
    }
  }

  Future<void> _loadSaved() async {
    try {
      final saved = await _storage.read(key: densityKey);
      // An unrecognised value (a density we no longer ship, a corrupted write)
      // yields null and we keep the default rather than throwing.
      final density = AppDensity.values
          .where((e) => e.name == saved)
          .firstOrNull;
      if (ref.mounted && density != null) state = density;
    } catch (e) {
      debugPrint('[THEME] Failed to load saved density: $e');
    }
    await _migrateRetiredPaletteKey();
  }

  /// One-time cleanup of the retired `palette_choice` key.
  ///
  /// Nothing reads it any more, so an upgrading user is never shown a Loam or
  /// Heritage tint — the value is simply orphaned. Deleting it keeps secure
  /// storage honest and stops a future reader resurrecting a dead setting.
  /// Mirrors the web's equivalent cleanup, which removes the `gt-palette`
  /// localStorage key in `ThemeContext.tsx`.
  ///
  /// Best-effort: a failure here must never block the app or lose the density.
  Future<void> _migrateRetiredPaletteKey() async {
    try {
      if (await _storage.read(key: retiredPaletteKey) != null) {
        await _storage.delete(key: retiredPaletteKey);
        debugPrint('[THEME] Removed retired palette preference.');
      }
    } catch (e) {
      debugPrint('[THEME] Failed to clear retired palette key: $e');
    }
  }
}
