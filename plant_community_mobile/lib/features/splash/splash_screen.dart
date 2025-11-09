import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';

/// Splash screen with animated logo and progress bar
///
/// Ported from design_reference/src/components/SplashScreen.tsx
///
/// Features:
/// - Gradient background
/// - Rotating leaf logo
/// - Animated progress bar
/// - Auto-navigates to home after 2 seconds
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _rotationController;
  late AnimationController _scaleController;
  late AnimationController _fadeController;
  late Timer _progressTimer;
  double _progress = 0.0;

  @override
  void initState() {
    super.initState();

    // Logo rotation animation (infinite)
    _rotationController = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    )..repeat();

    // Logo scale animation (initial appearance)
    _scaleController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    // Fade animation for text
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    // Start animations
    _scaleController.forward();
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _fadeController.forward();
    });

    // Progress bar animation (0 to 100 over ~2 seconds)
    _progressTimer = Timer.periodic(const Duration(milliseconds: 30), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }

      setState(() {
        if (_progress >= 100) {
          timer.cancel();
          // Navigate to home after completion
          Future.delayed(const Duration(milliseconds: 300), () {
            if (mounted) {
              context.go(AppRoutes.home);
            }
          });
        } else {
          _progress += 2;
        }
      });
    });
  }

  @override
  void dispose() {
    _rotationController.dispose();
    _scaleController.dispose();
    _fadeController.dispose();
    _progressTimer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: isDark
                ? [
                    AppColors.green950, // dark:from-green-950
                    AppColors.emerald950, // dark:to-emerald-950
                  ]
                : [
                    AppColors.green50, // from-green-50
                    AppColors.emerald100, // to-emerald-100
                  ],
          ),
        ),
        child: Center(
          child: ScaleTransition(
            scale: CurvedAnimation(
              parent: _scaleController,
              curve: Curves.easeOut,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Rotating Logo
                RotationTransition(
                  turns: _rotationController,
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
                      Icons.eco, // Leaf icon
                      size: 48,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),

                // App Name
                FadeTransition(
                  opacity: _fadeController,
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.2),
                      end: Offset.zero,
                    ).animate(CurvedAnimation(
                      parent: _fadeController,
                      curve: Curves.easeOut,
                    )),
                    child: Column(
                      children: [
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
                            'PlantID',
                            style: Theme.of(context)
                                .textTheme
                                .headlineLarge
                                ?.copyWith(
                                  fontSize: 48,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        Text(
                          'Discover Nature\'s Secrets',
                          style: TextStyle(
                            color: isDark
                                ? AppColors.green400
                                : AppColors.green700,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl2),

                // Progress Bar
                FadeTransition(
                  opacity: _fadeController,
                  child: SizedBox(
                    width: 200,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                      child: LinearProgressIndicator(
                        value: _progress / 100,
                        minHeight: 4,
                        backgroundColor: isDark
                            ? AppColors.green900.withValues(alpha: 0.3)
                            : AppColors.green200,
                        valueColor: const AlwaysStoppedAnimation<Color>(
                          AppColors.green500,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
