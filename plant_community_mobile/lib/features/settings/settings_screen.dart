import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../config/palette_notifier.dart';
import '../../config/theme_provider.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/app_palettes.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../core/theme/theme_preview_screen.dart';

/// App settings: theme mode, Green Thumb palette, layout density, and (in debug
/// builds) the theme preview gallery.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final cs = Theme.of(context).colorScheme;
    final themeMode = ref.watch(themeModeProvider);
    final themeNotifier = ref.read(themeModeProvider.notifier);
    final palette = ref.watch(paletteProvider);
    final paletteNotifier = ref.read(paletteProvider.notifier);

    final eyebrowStyle = Theme.of(
      context,
    ).textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: EdgeInsets.all(ext.padScreen),
          children: [
            // Appearance
            Text('APPEARANCE', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            SegmentedButton<ThemeMode>(
              segments: const [
                ButtonSegment(
                  value: ThemeMode.system,
                  icon: Icon(Icons.brightness_auto),
                  label: Text('System'),
                ),
                ButtonSegment(
                  value: ThemeMode.light,
                  icon: Icon(Icons.light_mode),
                  label: Text('Light'),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  icon: Icon(Icons.dark_mode),
                  label: Text('Dark'),
                ),
              ],
              selected: {themeMode},
              onSelectionChanged: (s) {
                switch (s.first) {
                  case ThemeMode.light:
                    themeNotifier.setLight();
                  case ThemeMode.dark:
                    themeNotifier.setDark();
                  case ThemeMode.system:
                    themeNotifier.setSystem();
                }
              },
            ),
            SizedBox(height: ext.gapY * 2),

            // Palette
            Text('PALETTE', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: AppPaletteChoice.values.map((choice) {
                final isSelected = palette.palette == choice;
                final swatchColor = _paletteSwatchColor(choice);
                return InkWell(
                  onTap: () => paletteNotifier.setPalette(choice),
                  borderRadius: BorderRadius.circular(AppSpacing.rSm),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: swatchColor,
                      borderRadius: BorderRadius.circular(AppSpacing.rSm),
                      border: isSelected
                          ? Border.all(color: cs.primary, width: 2)
                          : null,
                    ),
                    child: Text(
                      _paletteLabel(choice),
                      style: TextStyle(
                        color: _paletteTextColor(choice),
                        fontWeight: isSelected
                            ? FontWeight.bold
                            : FontWeight.normal,
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
            SizedBox(height: ext.gapY * 2),

            // Density
            Text('DENSITY', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            SegmentedButton<AppDensity>(
              segments: const [
                ButtonSegment(
                  value: AppDensity.comfortable,
                  label: Text('Comfortable'),
                ),
                ButtonSegment(value: AppDensity.cozy, label: Text('Cozy')),
                ButtonSegment(
                  value: AppDensity.compact,
                  label: Text('Compact'),
                ),
              ],
              selected: {palette.density},
              onSelectionChanged: (s) => paletteNotifier.setDensity(s.first),
            ),
            SizedBox(height: ext.gapY * 2),

            // About
            Text('ABOUT', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            const ListTile(
              leading: Icon(Icons.local_florist),
              title: Text('Plant Community'),
              subtitle: Text(
                'Plant identification, care, and community features',
              ),
            ),

            // Debug
            if (kDebugMode) ...[
              SizedBox(height: ext.gapY * 2),
              Text('DEBUG', style: eyebrowStyle),
              SizedBox(height: ext.gapY),
              ListTile(
                leading: const Icon(Icons.palette),
                title: const Text('Theme Preview'),
                subtitle: const Text('All 24 palette combinations'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push(ThemePreviewScreen.routePath),
              ),
            ],
          ],
        ),
      ),
    );
  }

  static Color _paletteSwatchColor(AppPaletteChoice c) => switch (c) {
    AppPaletteChoice.loam => const Color(0xFF4A7034),
    AppPaletteChoice.garden => const Color(0xFF2F6B3A),
    AppPaletteChoice.forest => const Color(0xFFB8DC7C),
    AppPaletteChoice.heritage => const Color(0xFF3D5A22),
  };

  static Color _paletteTextColor(AppPaletteChoice c) => switch (c) {
    AppPaletteChoice.forest => const Color(0xFF0F1A12),
    _ => const Color(0xFFF4F1DF),
  };

  static String _paletteLabel(AppPaletteChoice c) => switch (c) {
    AppPaletteChoice.loam => 'Loam',
    AppPaletteChoice.garden => 'Garden',
    AppPaletteChoice.forest => 'Forest',
    AppPaletteChoice.heritage => 'Heritage',
  };
}
