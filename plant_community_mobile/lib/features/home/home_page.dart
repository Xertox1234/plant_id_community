import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../shared/widgets/feature_card.dart';
import '../../shared/widgets/gradient_button.dart';

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
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.xl2,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Hero Section
                _buildHeroSection(context, isDark),
                const SizedBox(height: AppSpacing.xl2),

                // Features Grid
                _buildFeaturesGrid(context),
                const SizedBox(height: AppSpacing.xl2),

                // CTA Button
                _buildCTAButton(context),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Hero section with logo and title
  Widget _buildHeroSection(BuildContext context, bool isDark) {
    return Column(
      children: [
        // Logo with nested gradient circles
        Container(
          width: 128,
          height: 128,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: isDark
                  ? [
                      AppColors.green900.withValues(alpha: 0.3),
                      AppColors.emerald900.withValues(alpha: 0.3),
                    ]
                  : [
                      AppColors.green100,
                      AppColors.emerald100,
                    ],
            ),
          ),
          child: Center(
            child: Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    AppColors.green500,
                    AppColors.emerald600,
                  ],
                ),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.green500.withValues(alpha: 0.3),
                    blurRadius: 20,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: const Icon(
                Icons.camera_alt,
                size: 48,
                color: Colors.white,
              ),
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.xl),

        // Title with gradient
        ShaderMask(
          shaderCallback: (bounds) => LinearGradient(
            colors: isDark
                ? [
                    AppColors.green400,
                    AppColors.emerald400,
                  ]
                : [
                    AppColors.green700,
                    AppColors.emerald700,
                  ],
          ).createShader(bounds),
          child: Text(
            'Welcome to PlantID',
            style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Description
        Text(
          'Your pocket botanist for identifying plants, learning care tips, and connecting with fellow plant enthusiasts',
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Theme.of(context).textTheme.bodySmall?.color,
              ),
          textAlign: TextAlign.center,
          maxLines: 3,
        ),
      ],
    );
  }

  /// Features grid with 4 cards
  Widget _buildFeaturesGrid(BuildContext context) {
    final features = [
      _FeatureData(
        icon: Icons.camera_alt,
        title: 'Instant Identification',
        description: 'Snap a photo and instantly identify any plant with AI-powered recognition',
        type: FeatureType.camera,
      ),
      _FeatureData(
        icon: Icons.book,
        title: 'Care Instructions',
        description: 'Get personalized care tips for watering, sunlight, and maintenance',
        type: FeatureType.care,
      ),
      _FeatureData(
        icon: Icons.people,
        title: 'Community Forum',
        description: 'Connect with plant lovers, share experiences, and get expert advice',
        type: FeatureType.community,
      ),
      _FeatureData(
        icon: Icons.auto_awesome,
        title: 'Track Your Collection',
        description: 'Build your personal plant library and track identification history',
        type: FeatureType.collection,
      ),
    ];

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 600),
      child: Column(
        children: features.map((feature) {
          return Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: FeatureCard(
              icon: feature.icon,
              title: feature.title,
              description: feature.description,
              iconColor: FeatureCardColors.getIconColor(context, feature.type),
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
      child: GradientButton(
        label: 'Get Started',
        icon: Icons.arrow_forward,
        fullWidth: true,
        onPressed: () {
          // Navigate to camera screen
          context.go(AppRoutes.camera);
        },
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
