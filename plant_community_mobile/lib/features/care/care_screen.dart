import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

/// Plant care guides hub (stub). Lists the core care categories; full guides
/// are not yet implemented.
class CareScreen extends StatelessWidget {
  const CareScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    final eyebrowStyle = Theme.of(
      context,
    ).textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3);

    return Scaffold(
      appBar: AppBar(title: const Text('Plant Care'), centerTitle: true),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(ext.padScreen),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('CARE GUIDES', style: eyebrowStyle),
              SizedBox(height: ext.gapY),
              Text(
                'Keep your plants happy',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              SizedBox(height: ext.gapY),
              Text(
                'Learn everything you need to help your plants thrive — from '
                'watering schedules to the perfect soil mix.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: ext.ink2),
              ),
              SizedBox(height: ext.gapY * 2),
              ..._categories(cs, ext).map(
                (c) => Padding(
                  padding: EdgeInsets.only(bottom: ext.gapY),
                  child: _CategoryCard(category: c, ext: ext),
                ),
              ),
              SizedBox(height: ext.gapY),
              Text(
                'Full care guides coming soon',
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: ext.ink3),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  static List<_Category> _categories(ColorScheme cs, GreenThumbExtension ext) =>
      [
        _Category(
          title: 'Watering',
          subtitle: 'When and how much to water your plants',
          icon: Icons.water_drop,
          accent: ext.sky,
        ),
        _Category(
          title: 'Sunlight',
          subtitle: 'Light requirements for healthy growth',
          icon: Icons.wb_sunny,
          accent: cs.tertiary,
        ),
        _Category(
          title: 'Soil & Fertilising',
          subtitle: 'The right growing medium and nutrients',
          icon: Icons.grass,
          accent: cs.primary,
        ),
        _Category(
          title: 'Temperature',
          subtitle: 'Optimal conditions for your plants',
          icon: Icons.thermostat,
          accent: ext.clay,
        ),
      ];
}

class _Category {
  const _Category({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.accent,
  });
  final String title;
  final String subtitle;
  final IconData icon;
  final Color accent;
}

class _CategoryCard extends StatelessWidget {
  const _CategoryCard({required this.category, required this.ext});
  final _Category category;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding: EdgeInsets.all(ext.padCard),
        leading: Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: category.accent.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(AppSpacing.rSm),
          ),
          child: Icon(category.icon, color: category.accent, size: 24),
        ),
        title: Text(
          category.title,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        subtitle: Text(
          category.subtitle,
          style: Theme.of(
            context,
          ).textTheme.bodySmall?.copyWith(color: ext.ink2),
        ),
        trailing: Icon(Icons.chevron_right, color: ext.ink3),
      ),
    );
  }
}
