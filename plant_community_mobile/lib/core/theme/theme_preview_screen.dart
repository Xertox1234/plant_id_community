import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'app_palettes.dart';
import 'app_theme.dart';
import 'green_thumb_extension.dart';

class ThemePreviewScreen extends StatelessWidget {
  const ThemePreviewScreen({super.key});

  static const routePath = '/debug/theme-preview';

  @override
  Widget build(BuildContext context) {
    assert(kDebugMode, 'ThemePreviewScreen must only be used in debug builds');

    final combinations = [
      for (final palette in AppPaletteChoice.values)
        for (final brightness in Brightness.values)
          for (final density in AppDensity.values)
            (palette: palette, brightness: brightness, density: density),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Theme Preview (24 combinations)')),
      body: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: combinations.length,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (context, i) {
          final c = combinations[i];
          final theme = AppTheme.build(c.palette, c.brightness, c.density);
          final ext = theme.extension<GreenThumbExtension>()!;
          return _CombinationTile(theme: theme, ext: ext, combo: c);
        },
      ),
    );
  }
}

class _CombinationTile extends StatelessWidget {
  const _CombinationTile({
    required this.theme,
    required this.ext,
    required this.combo,
  });

  final ThemeData theme;
  final GreenThumbExtension ext;
  final ({AppPaletteChoice palette, Brightness brightness, AppDensity density})
  combo;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: theme.colorScheme.outline),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '${combo.palette.name} · ${combo.brightness.name} · ${combo.density.name}',
              style: TextStyle(
                color: theme.colorScheme.onSurface,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          _Swatch(color: theme.colorScheme.primary, label: 'primary'),
          const SizedBox(width: 4),
          _Swatch(color: theme.colorScheme.surface, label: 'surface'),
          const SizedBox(width: 4),
          _Swatch(color: ext.clay, label: 'clay'),
        ],
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
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: Colors.black12),
        ),
      ),
    );
  }
}
