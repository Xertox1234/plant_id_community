import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../shared/widgets/canopy_label.dart';
import '../../shared/widgets/canopy_surfaces.dart';
import '../../shared/widgets/clay_button.dart';
import '../constants/app_spacing.dart';
import 'app_theme.dart';
import 'canopy_palette.dart';
import 'green_thumb_extension.dart';

/// Debug-only gallery of every theme combination.
///
/// Six now, not twenty-four: the four palettes are retired, leaving
/// 2 brightnesses × 3 densities. Each tile renders the REAL primitives — a
/// gradient card, all four button variants, an input, chips, an accent tile —
/// so this can be compared side by side with the web's
/// `/debug/theme-preview` page. A grid of colour swatches would prove the
/// tokens exist; this shows what they build.
class ThemePreviewScreen extends StatelessWidget {
  const ThemePreviewScreen({super.key});

  static const routePath = '/debug/theme-preview';

  @override
  Widget build(BuildContext context) {
    assert(kDebugMode, 'ThemePreviewScreen must only be used in debug builds');

    final combinations = [
      for (final brightness in Brightness.values)
        for (final density in AppDensity.values) (brightness, density),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text('Theme preview (${combinations.length} combinations)'),
      ),
      body: ListView.separated(
        padding: const EdgeInsets.all(AppSpacing.md),
        itemCount: combinations.length,
        separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.md),
        itemBuilder: (context, i) {
          final (brightness, density) = combinations[i];
          return _CombinationTile(
            theme: AppTheme.build(brightness, density),
            brightness: brightness,
            density: density,
          );
        },
      ),
    );
  }
}

class _CombinationTile extends StatelessWidget {
  const _CombinationTile({
    required this.theme,
    required this.brightness,
    required this.density,
  });

  final ThemeData theme;
  final Brightness brightness;
  final AppDensity density;

  @override
  Widget build(BuildContext context) {
    // A real Theme + ground, so every child resolves the combination's tokens
    // exactly as it would in the app.
    return Theme(
      data: theme,
      child: Builder(
        builder: (context) {
          final ext = context.canopy;
          return ClipRRect(
            borderRadius: BorderRadius.circular(AppSpacing.rMd),
            child: ColoredBox(
              color: ext.ground,
              child: CanopyGround(
                child: Padding(
                  padding: EdgeInsets.all(ext.padScreen),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      CanopyLabel('${brightness.name} · ${density.name}'),
                      SizedBox(height: ext.gapY),
                      CanopyCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const CanopyTile(icon: LucideIcons.leaf),
                                const SizedBox(width: AppSpacing.sm),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Monstera deliciosa',
                                        style: Theme.of(
                                          context,
                                        ).textTheme.titleMedium,
                                      ),
                                      Text(
                                        'Watered 3 days ago',
                                        style: Theme.of(
                                          context,
                                        ).textTheme.bodySmall,
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            SizedBox(height: ext.gapY),
                            Wrap(
                              spacing: AppSpacing.sm,
                              runSpacing: AppSpacing.sm,
                              children: const [
                                ClayButton(
                                  label: 'Identify',
                                  size: ClayButtonSize.small,
                                ),
                                ClayButton(
                                  label: 'Secondary',
                                  size: ClayButtonSize.small,
                                  variant: ClayButtonVariant.secondary,
                                ),
                                ClayButton(
                                  label: 'Outline',
                                  size: ClayButtonSize.small,
                                  variant: ClayButtonVariant.outline,
                                ),
                                ClayButton(
                                  label: 'Ghost',
                                  size: ClayButtonSize.small,
                                  variant: ClayButtonVariant.ghost,
                                ),
                                ClayButton(
                                  label: 'Disabled',
                                  size: ClayButtonSize.small,
                                  onPressed: null,
                                ),
                              ],
                            ),
                            SizedBox(height: ext.gapY),
                            const TextField(
                              decoration: InputDecoration(
                                labelText: 'Plant name',
                                hintText: 'e.g. Monstera',
                              ),
                            ),
                            SizedBox(height: ext.gapY),
                            Wrap(
                              spacing: AppSpacing.sm,
                              children: [
                                Chip(
                                  label: const Text('Tropical'),
                                  avatar: Icon(
                                    LucideIcons.droplet,
                                    size: AppSpacing.iconSM,
                                    color: ext.sky,
                                  ),
                                ),
                                const Chip(label: Text('Low light')),
                                Chip(
                                  label: const Text('Healthy'),
                                  avatar: Icon(
                                    LucideIcons.circleCheck,
                                    size: AppSpacing.iconSM,
                                    color: ext.statusOk,
                                  ),
                                ),
                              ],
                            ),
                            SizedBox(height: ext.gapY),
                            Row(
                              children: [
                                for (final tone in CanopyTileTone.values) ...[
                                  CanopyTile(
                                    icon: LucideIcons.sprout,
                                    tone: tone,
                                    size: CanopyTileSize.sm,
                                  ),
                                  const SizedBox(width: AppSpacing.sm),
                                ],
                                _Swatch(color: ext.clay, label: 'clay'),
                                const SizedBox(width: AppSpacing.xs),
                                _Swatch(color: ext.berry, label: 'berry'),
                                const SizedBox(width: AppSpacing.xs),
                                _Swatch(
                                  color: theme.colorScheme.error,
                                  label: 'error',
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _Swatch extends StatelessWidget {
  const _Swatch({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(AppSpacing.rXs),
          border: Border.all(color: context.canopy.line),
        ),
      ),
    );
  }
}
