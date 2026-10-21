import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../shared/widgets/canopy_surfaces.dart';
import '../../core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';

/// The tag the CMS care guides carry (`CARE_GUIDE_TAG` in
/// `backend/apps/blog/care_topics.py`, todo 445).
const String careGuideTag = 'care-guide';

/// Plant care guides hub. Each category card opens the care guides: the
/// published Wagtail blog posts tagged [careGuideTag], so guides are edited
/// in the CMS without an app release (todo 386 owner decision).
///
/// The CMS has one tag for every guide, not one per category, so every card
/// opens the same list, titled for the card that opened it.
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
          padding:
              EdgeInsets.all(ext.padScreen) + MainShell.fabClearanceOf(context),
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
          icon: LucideIcons.droplet,
          accent: ext.sky,
        ),
        _Category(
          title: 'Sunlight',
          subtitle: 'Light requirements for healthy growth',
          icon: LucideIcons.sun,
          accent: cs.tertiary,
        ),
        _Category(
          title: 'Soil & Fertilising',
          subtitle: 'The right growing medium and nutrients',
          icon: LucideIcons.sprout,
          accent: cs.primary,
        ),
        _Category(
          title: 'Temperature',
          subtitle: 'Optimal conditions for your plants',
          icon: LucideIcons.thermometer,
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
    return CanopyCard(
      padding: EdgeInsets.zero,
      child: ListTile(
        onTap: () => context.push(
          Uri(
            path: AppRoutes.blog,
            queryParameters: {'tag': careGuideTag},
          ).toString(),
          extra: '${category.title} guides',
        ),
        contentPadding: EdgeInsets.all(ext.padCard),
        leading: Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: category.accent.withValues(alpha: 0.10),
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
        trailing: Icon(LucideIcons.chevronRight, color: ext.ink3),
      ),
    );
  }
}
