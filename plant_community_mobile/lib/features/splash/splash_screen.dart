import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/grain_overlay.dart';
import '../../core/theme/green_thumb_extension.dart';

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

    _rotationController = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    )..repeat();

    _scaleController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _scaleController.forward();
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _fadeController.forward();
    });

    _progressTimer = Timer.periodic(const Duration(milliseconds: 30), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_progress >= 100) {
        timer.cancel();
        Future.delayed(const Duration(milliseconds: 300), () {
          if (mounted) context.go(AppRoutes.home);
        });
      } else {
        setState(() => _progress += 2);
      }
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
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;

    return Scaffold(
      backgroundColor: cs.surface,
      body: GrainOverlay(
        child: Center(
          child: ScaleTransition(
            scale: CurvedAnimation(
              parent: _scaleController,
              curve: Curves.easeOut,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Rotating logo
                RotationTransition(
                  turns: _rotationController,
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: cs.primary,
                      boxShadow: ext.shadow2,
                    ),
                    child: const Icon(Icons.eco, size: 48, color: Colors.white),
                  ),
                ),
                SizedBox(height: ext.gapY * 2),

                // App name + tagline
                FadeTransition(
                  opacity: _fadeController,
                  child: SlideTransition(
                    position:
                        Tween<Offset>(
                          begin: const Offset(0, 0.2),
                          end: Offset.zero,
                        ).animate(
                          CurvedAnimation(
                            parent: _fadeController,
                            curve: Curves.easeOut,
                          ),
                        ),
                    child: Column(
                      children: [
                        Text(
                          'PlantID',
                          style: Theme.of(context).textTheme.displayLarge
                              ?.copyWith(fontSize: 48, color: cs.onSurface),
                        ),
                        SizedBox(height: ext.gapY),
                        Text(
                          "DISCOVER NATURE'S SECRETS",
                          style: Theme.of(context).textTheme.labelSmall
                              ?.copyWith(
                                letterSpacing: 0.06 * 11,
                                color: ext.ink3,
                              ),
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(height: ext.gapY * 2),

                // Progress bar
                FadeTransition(
                  opacity: _fadeController,
                  child: SizedBox(
                    width: 200,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(AppSpacing.rPill),
                      child: LinearProgressIndicator(
                        value: _progress / 100,
                        minHeight: 4,
                        backgroundColor: cs.surfaceContainerLow,
                        valueColor: AlwaysStoppedAnimation<Color>(cs.primary),
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
