import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/config/palette_notifier.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  group('PaletteSettings', () {
    test('default is loam + cozy', () {
      const s = PaletteSettings.defaults();
      expect(s.palette, AppPaletteChoice.loam);
      expect(s.density, AppDensity.cozy);
    });

    test('copyWith overrides individual fields', () {
      final s = const PaletteSettings.defaults()
          .copyWith(palette: AppPaletteChoice.forest);
      expect(s.palette, AppPaletteChoice.forest);
      expect(s.density, AppDensity.cozy);
    });
  });

  group('PaletteNotifier initial state', () {
    test('starts with defaults before storage loads', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final state = container.read(paletteProvider);
      expect(state.palette, AppPaletteChoice.loam);
      expect(state.density, AppDensity.cozy);
    });
  });
}
