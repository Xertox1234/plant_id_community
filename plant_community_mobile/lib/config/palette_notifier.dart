import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../core/theme/app_palettes.dart';
import '../core/theme/green_thumb_extension.dart';

part 'palette_notifier.g.dart';

class PaletteSettings {
  const PaletteSettings({required this.palette, required this.density});
  const PaletteSettings.defaults()
    : palette = AppPaletteChoice.loam,
      density = AppDensity.cozy;

  final AppPaletteChoice palette;
  final AppDensity density;

  PaletteSettings copyWith({AppPaletteChoice? palette, AppDensity? density}) {
    return PaletteSettings(
      palette: palette ?? this.palette,
      density: density ?? this.density,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is PaletteSettings &&
      other.palette == palette &&
      other.density == density;

  @override
  int get hashCode => Object.hash(palette, density);
}

@riverpod
class PaletteNotifier extends _$PaletteNotifier {
  static const _storage = FlutterSecureStorage();
  static const _paletteKey = 'palette_choice';
  static const _densityKey = 'palette_density';

  @override
  PaletteSettings build() {
    _loadSaved();
    return const PaletteSettings.defaults();
  }

  void setPalette(AppPaletteChoice choice) {
    state = state.copyWith(palette: choice);
    unawaited(_storage.write(key: _paletteKey, value: choice.name));
  }

  void setDensity(AppDensity density) {
    state = state.copyWith(density: density);
    unawaited(_storage.write(key: _densityKey, value: density.name));
  }

  Future<void> _loadSaved() async {
    try {
      final savedPalette = await _storage.read(key: _paletteKey);
      final savedDensity = await _storage.read(key: _densityKey);

      final palette = AppPaletteChoice.values
          .where((e) => e.name == savedPalette)
          .firstOrNull;
      final density = AppDensity.values
          .where((e) => e.name == savedDensity)
          .firstOrNull;

      if (ref.mounted && (palette != null || density != null)) {
        state = state.copyWith(palette: palette, density: density);
      }
    } catch (e) {
      debugPrint('[PALETTE] Failed to load saved settings: $e');
    }
  }
}
