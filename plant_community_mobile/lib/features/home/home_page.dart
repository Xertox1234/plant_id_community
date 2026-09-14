import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/widgets/brand_mark.dart';
import '../../shared/widgets/canopy_label.dart';
import '../../shared/widgets/canopy_surfaces.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../shared/widgets/clay_button.dart';
import '../../shared/widgets/feature_card.dart';

/// Home page with hero section and feature cards
///
/// Ported from design_reference/src/components/HomePage.tsx
///
/// Features:
/// - Hero section with logo and title
/// - 4 feature cards (Camera, Care, Community, Collection)
/// - Get Started CTA button
class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    return Scaffold(
      // No Settings FAB: MainShell renders the Identify FAB over every tab, and
      // two FABs on one screen both collide as Heroes and read as clutter.
      // Settings moved under the Profile tab (todo 384).
      // CanopyGround wraps the SCROLLER, not the scrolled content. Its Stack
      // sizes to its non-positioned child, so inside a SingleChildScrollView
      // the `Positioned.fill` glow would fill the CONTENT height and scroll
      // away with it — the web's `.canopy-ground` is `position: fixed`.
      body: CanopyGround(
        child: SafeArea(
          child: SingleChildScrollView(
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: ext.padScreen,
                vertical: ext.padScreen * 2,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Hero Section
                  _buildHeroSection(context),
                  SizedBox(height: ext.gapY * 2),

                  // Features Grid
                  _buildFeaturesGrid(context),
                  SizedBox(height: ext.gapY * 2),

                  // CTA Button
                  _buildCTAButton(context),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// Hero: brand lockup, eyebrow, headline, standfirst, two CTAs.
  ///
  /// Mirrors the web `HeroCard` (eyebrow -> display headline -> description ->
  /// primary + ghost actions), including the accented final word. The
  /// nested-circles logo it replaced was a Flutter-only treatment with a
  /// hardcoded white icon, and showed a camera glyph rather than the product
  /// mark.
  Widget _buildHeroSection(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = context.canopy;

    return CanopyCard(
      radius: AppSpacing.rLg,
      padding: EdgeInsets.all(ext.padCard * 1.5),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const BrandLockup(markSize: 40, showTagline: true),
          SizedBox(height: ext.gapY * 1.5),
          const CanopyLabel('Plant identification community'),
          SizedBox(height: ext.gapY),
          // The web accents the final word in `--gt-primary`.
          Text.rich(
            TextSpan(
              style: AppTypography.h1.copyWith(color: cs.onSurface),
              children: [
                const TextSpan(text: 'Discover the world of '),
                TextSpan(
                  text: 'plants',
                  style: TextStyle(color: cs.primary),
                ),
              ],
            ),
          ),
          SizedBox(height: ext.gapY),
          Text(
            'Identify plants with AI, track your collection, and learn from '
            'other growers.',
            style: AppTypography.body.copyWith(color: ext.ink2),
          ),
          SizedBox(height: ext.gapY * 1.5),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              ClayButton(
                label: 'Identify a plant',
                size: ClayButtonSize.medium,
                onPressed: () => context.push(AppRoutes.camera),
              ),
              ClayButton(
                label: 'Join the forum',
                size: ClayButtonSize.medium,
                variant: ClayButtonVariant.ghost,
                onPressed: () => context.go(AppRoutes.forum),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Features grid with 4 cards
  Widget _buildFeaturesGrid(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    final features = [
      _FeatureData(
        icon: LucideIcons.camera,
        title: 'Instant Identification',
        description:
            'Snap a photo and instantly identify any plant with AI-powered recognition',
        type: FeatureType.camera,
        route: AppRoutes.camera,
        isTab: false,
      ),
      _FeatureData(
        icon: LucideIcons.bookOpen,
        title: 'Care Instructions',
        description:
            'Get personalized care tips for watering, sunlight, and maintenance',
        type: FeatureType.care,
        route: AppRoutes.care,
        isTab: false,
      ),
      _FeatureData(
        icon: LucideIcons.users,
        title: 'Community Forum',
        description:
            'Connect with plant lovers, share experiences, and get expert advice',
        type: FeatureType.community,
        route: AppRoutes.forum,
        isTab: true,
      ),
      _FeatureData(
        icon: LucideIcons.sparkles,
        title: 'Track Your Collection',
        description:
            'Build your personal plant library and track identification history',
        type: FeatureType.collection,
        route: AppRoutes.collection,
        isTab: true,
      ),
    ];

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 600),
      child: Column(
        children: features.map((feature) {
          return Padding(
            padding: EdgeInsets.only(bottom: ext.gapY),
            child: FeatureCard(
              icon: feature.icon,
              title: feature.title,
              description: feature.description,
              type: feature.type,
              onTap: () => feature.isTab
                  ? context.go(feature.route)
                  : context.push(feature.route),
            ),
          );
        }).toList(),
      ),
    );
  }

  /// Get Started CTA button
  Widget _buildCTAButton(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 600),
      child: ClayButton(
        label: 'Get Started',
        icon: LucideIcons.arrowRight,
        fullWidth: true,
        onPressed: () => context.push(AppRoutes.camera),
      ),
    );
  }
}

/// Feature data model
class _FeatureData {
  final IconData icon;
  final String title;
  final String description;
  final FeatureType type;
  final String route;

  /// Whether [route] is a top-level shell tab.
  ///
  /// A card for a tab should SWITCH to it -- `context.go` to a branch location
  /// activates that branch and keeps its own stack. A card for a screen that
  /// lives *inside* a tab must `push`, or `go` replaces the stack and strands
  /// the user on a screen whose AppBar draws no back button (todo 384
  /// finding 5; every one of these four cards used `go`).
  final bool isTab;

  _FeatureData({
    required this.icon,
    required this.title,
    required this.description,
    required this.type,
    required this.route,
    required this.isTab,
  });
}
