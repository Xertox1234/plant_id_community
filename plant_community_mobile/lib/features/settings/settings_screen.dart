import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../config/density_notifier.dart';
import '../../config/theme_provider.dart';
import '../../core/constants/app_brand.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../core/theme/theme_preview_screen.dart';
import '../../shared/widgets/canopy_label.dart';

/// App settings: theme mode, layout density, and (in debug builds) the theme
/// preview gallery.
///
/// The palette picker is gone. Canopy is one identity (spec §2) — the four
/// palettes it offered (Loam / Garden / Forest / Heritage) were a Flutter-only
/// invention the web never had.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final themeMode = ref.watch(themeModeProvider);
    final themeNotifier = ref.read(themeModeProvider.notifier);
    final density = ref.watch(densityProvider);
    final densityNotifier = ref.read(densityProvider.notifier);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: EdgeInsets.all(ext.padScreen),
          children: [
            // Appearance
            const CanopyLabel('APPEARANCE'),
            SizedBox(height: ext.gapY),
            SegmentedButton<ThemeMode>(
              segments: const [
                ButtonSegment(
                  value: ThemeMode.system,
                  icon: Icon(LucideIcons.monitor),
                  label: Text('System'),
                ),
                ButtonSegment(
                  value: ThemeMode.light,
                  icon: Icon(LucideIcons.sun),
                  label: Text('Light'),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  icon: Icon(LucideIcons.moon),
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

            // Density
            const CanopyLabel('DENSITY'),
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
              selected: {density},
              onSelectionChanged: (s) => densityNotifier.setDensity(s.first),
            ),
            SizedBox(height: ext.gapY * 2),

            // About
            const CanopyLabel('ABOUT'),
            SizedBox(height: ext.gapY),
            ListTile(
              leading: const Icon(LucideIcons.stethoscope),
              title: const Text(AppBrand.name),
              subtitle: const Text(AppBrand.tagline),
            ),

            // Debug
            if (kDebugMode) ...[
              SizedBox(height: ext.gapY * 2),
              const CanopyLabel('DEBUG'),
              SizedBox(height: ext.gapY),
              ListTile(
                leading: const Icon(LucideIcons.palette),
                title: const Text('Theme Preview'),
                subtitle: const Text('Every mode and density combination'),
                trailing: const Icon(LucideIcons.chevronRight),
                onTap: () => context.push(ThemePreviewScreen.routePath),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
