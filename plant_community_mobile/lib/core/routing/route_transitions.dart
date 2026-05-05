import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Custom page transitions for go_router
///
/// This file provides reusable transition builders for consistent
/// navigation animations throughout the app.
///
/// Usage with go_router:
/// ```dart
/// GoRoute(
///   path: '/example',
///   pageBuilder: (context, state) => RouteTransitions.fade(
///     key: state.pageKey,
///     child: const ExampleScreen(),
///   ),
/// )
/// ```

abstract class RouteTransitions {
  /// Standard fade transition duration
  static const Duration _defaultDuration = Duration(milliseconds: 300);

  /// Fast transition duration (for quick navigations)
  static const Duration _fastDuration = Duration(milliseconds: 200);

  /// Slow transition duration (for dramatic effects)
  static const Duration _slowDuration = Duration(milliseconds: 500);

  // ============================================
  // FADE TRANSITIONS
  // ============================================

  /// Fade transition (default)
  ///
  /// Smoothly fades between screens. Best for most navigation scenarios.
  static CustomTransitionPage<T> fade<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = _defaultDuration,
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        return FadeTransition(
          opacity: animation,
          child: child,
        );
      },
    );
  }

  /// Fast fade transition
  ///
  /// Quicker fade for rapid navigation (e.g., tab switches)
  static CustomTransitionPage<T> fadeFast<T>({
    required LocalKey key,
    required Widget child,
  }) {
    return fade<T>(key: key, child: child, duration: _fastDuration);
  }

  /// Slow fade transition
  ///
  /// Slower fade for dramatic effect (e.g., splash screen transitions)
  static CustomTransitionPage<T> fadeSlow<T>({
    required LocalKey key,
    required Widget child,
  }) {
    return fade<T>(key: key, child: child, duration: _slowDuration);
  }

  // ============================================
  // SLIDE TRANSITIONS
  // ============================================

  /// Slide transition from right (iOS-style)
  ///
  /// Slides new screen in from the right, like iOS native navigation.
  static CustomTransitionPage<T> slideFromRight<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = _defaultDuration,
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(1.0, 0.0);
        const end = Offset.zero;
        final tween = Tween(begin: begin, end: end);
        final offsetAnimation = animation.drive(
          tween.chain(CurveTween(curve: Curves.easeInOut)),
        );

        return SlideTransition(
          position: offsetAnimation,
          child: child,
        );
      },
    );
  }

  /// Slide transition from left
  ///
  /// Slides new screen in from the left (reverse direction).
  static CustomTransitionPage<T> slideFromLeft<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = _defaultDuration,
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(-1.0, 0.0);
        const end = Offset.zero;
        final tween = Tween(begin: begin, end: end);
        final offsetAnimation = animation.drive(
          tween.chain(CurveTween(curve: Curves.easeInOut)),
        );

        return SlideTransition(
          position: offsetAnimation,
          child: child,
        );
      },
    );
  }

  /// Slide transition from bottom (Material-style)
  ///
  /// Slides new screen in from the bottom, like Android native navigation.
  static CustomTransitionPage<T> slideFromBottom<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = _defaultDuration,
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(0.0, 1.0);
        const end = Offset.zero;
        final tween = Tween(begin: begin, end: end);
        final offsetAnimation = animation.drive(
          tween.chain(CurveTween(curve: Curves.easeInOut)),
        );

        return SlideTransition(
          position: offsetAnimation,
          child: child,
        );
      },
    );
  }

  // ============================================
  // SCALE TRANSITIONS
  // ============================================

  /// Scale transition (zoom in/out)
  ///
  /// Scales new screen from 0.8 to 1.0 while fading in.
  /// Good for modal-style screens or dialog-like routes.
  static CustomTransitionPage<T> scale<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = _defaultDuration,
    double beginScale = 0.8,
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        final scaleTween = Tween<double>(begin: beginScale, end: 1.0);
        final fadeAnimation = animation.drive(
          CurveTween(curve: Curves.easeInOut),
        );

        return ScaleTransition(
          scale: animation.drive(scaleTween),
          child: FadeTransition(
            opacity: fadeAnimation,
            child: child,
          ),
        );
      },
    );
  }

  // ============================================
  // COMBINED TRANSITIONS
  // ============================================

  /// Slide and fade transition
  ///
  /// Combines slide from right with fade for smooth navigation.
  /// This is the default iOS pattern.
  static CustomTransitionPage<T> slideAndFade<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = _defaultDuration,
    Offset begin = const Offset(0.3, 0.0),
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const end = Offset.zero;
        final tween = Tween(begin: begin, end: end);
        final offsetAnimation = animation.drive(
          tween.chain(CurveTween(curve: Curves.easeInOut)),
        );

        return SlideTransition(
          position: offsetAnimation,
          child: FadeTransition(
            opacity: animation,
            child: child,
          ),
        );
      },
    );
  }

  /// No transition (instant)
  ///
  /// Switches screens without animation. Useful for tab switches
  /// or when animation would be jarring.
  static CustomTransitionPage<T> none<T>({
    required LocalKey key,
    required Widget child,
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: Duration.zero,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        return child;
      },
    );
  }

  // ============================================
  // PLATFORM-ADAPTIVE TRANSITIONS
  // ============================================

  /// Platform-adaptive transition
  ///
  /// Uses native transition for the current platform:
  /// - iOS: slide from right
  /// - Android: slide from bottom
  /// - Other: fade
  static CustomTransitionPage<T> platformAdaptive<T>({
    required LocalKey key,
    required Widget child,
    required TargetPlatform platform,
    Duration duration = _defaultDuration,
  }) {
    switch (platform) {
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        return slideFromRight<T>(key: key, child: child, duration: duration);

      case TargetPlatform.android:
      case TargetPlatform.fuchsia:
        return slideFromBottom<T>(key: key, child: child, duration: duration);

      case TargetPlatform.linux:
      case TargetPlatform.windows:
        return fade<T>(key: key, child: child, duration: duration);
    }
  }
}

/// Extension for BuildContext to easily get current platform
extension PlatformExtension on BuildContext {
  /// Get current platform
  TargetPlatform get platform => Theme.of(this).platform;

  /// Check if running on iOS
  bool get isIOS =>
      platform == TargetPlatform.iOS || platform == TargetPlatform.macOS;

  /// Check if running on Android
  bool get isAndroid =>
      platform == TargetPlatform.android ||
      platform == TargetPlatform.fuchsia;

  /// Check if running on desktop
  bool get isDesktop =>
      platform == TargetPlatform.linux ||
      platform == TargetPlatform.windows ||
      platform == TargetPlatform.macOS;
}
