import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/grain_overlay.dart';
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
    final rawExt = Theme.of(context).extension<GreenThumbExtension>();
    assert(
      rawExt != null,
      'HomePage requires GreenThumbExtension to be registered in the theme. '
      'Ensure AppTheme.build() is used to create the ThemeData.',
    );
    final ext = rawExt!;

    return Scaffold(
      floatingActionButton: FloatingActionButton.small(
        tooltip: 'Settings',
        onPressed: () => context.push(AppRoutes.settings),
        child: const Icon(Icons.settings),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: GrainOverlay(
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

  /// Hero section with eyebrow label, logo, and title
  Widget _buildHeroSection(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final rawExt = Theme.of(context).extension<GreenThumbExtension>();
    assert(
      rawExt != null,
      'HomePage requires GreenThumbExtension to be registered in the theme. '
      'Ensure AppTheme.build() is used to create the ThemeData.',
    );
    final ext = rawExt!;

    return Column(
      children: [
        // Eyebrow label
        Text(
          'PLANT IDENTIFICATION',
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            letterSpacing: 0.06 * 11,
            color: ext.ink3,
          ),
        ),
        SizedBox(height: ext.gapY),

        // Logo with nested circles
        Container(
          width: 128,
          height: 128,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: cs.surfaceContainerLow,
          ),
          child: Center(
            child: Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: cs.primary,
                boxShadow: ext.shadow2,
              ),
              child: const Icon(
                Icons.camera_alt,
                size: 48,
                color: Colors.white,
              ),
            ),
          ),
        ),
        SizedBox(height: ext.gapY),

        // Title
        Text(
          'Welcome to PlantID',
          style: Theme.of(
            context,
          ).textTheme.displayLarge?.copyWith(color: cs.onSurface),
          textAlign: TextAlign.center,
        ),
        SizedBox(height: ext.gapY),

        // Description
        Text(
          'Your pocket botanist for identifying plants, learning care tips, and connecting with fellow plant enthusiasts',
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(color: ext.ink2, height: 1.5),
          textAlign: TextAlign.center,
          maxLines: 3,
        ),
      ],
    );
  }

  /// Features grid with 4 cards
  Widget _buildFeaturesGrid(BuildContext context) {
    final rawExt = Theme.of(context).extension<GreenThumbExtension>();
    assert(
      rawExt != null,
      'HomePage requires GreenThumbExtension to be registered in the theme. '
      'Ensure AppTheme.build() is used to create the ThemeData.',
    );
    final ext = rawExt!;

    final features = [
      _FeatureData(
        icon: Icons.camera_alt,
        title: 'Instant Identification',
        description:
            'Snap a photo and instantly identify any plant with AI-powered recognition',
        type: FeatureType.camera,
      ),
      _FeatureData(
        icon: Icons.book,
        title: 'Care Instructions',
        description:
            'Get personalized care tips for watering, sunlight, and maintenance',
        type: FeatureType.care,
      ),
      _FeatureData(
        icon: Icons.people,
        title: 'Community Forum',
        description:
            'Connect with plant lovers, share experiences, and get expert advice',
        type: FeatureType.community,
      ),
      _FeatureData(
        icon: Icons.auto_awesome,
        title: 'Track Your Collection',
        description:
            'Build your personal plant library and track identification history',
        type: FeatureType.collection,
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
        icon: Icons.arrow_forward,
        fullWidth: true,
        onPressed: () => context.go(AppRoutes.camera),
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

  _FeatureData({
    required this.icon,
    required this.title,
    required this.description,
    required this.type,
  });
}
