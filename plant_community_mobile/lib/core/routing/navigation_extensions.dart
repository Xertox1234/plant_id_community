import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../models/plant.dart';
import 'app_router.dart';

/// Navigation extensions for common routing patterns
///
/// These extensions provide type-safe, convenient methods for navigation
/// throughout the app. Instead of manually constructing routes, use these
/// helper methods for consistency and to catch errors at compile time.
///
/// Example usage:
/// ```dart
/// // Navigate to camera screen
/// context.goToCamera();
///
/// // Navigate to results with plant data
/// context.goToResults(plant);
///
/// // Navigate to login
/// context.goToLogin();
/// ```
extension NavigationExtensions on BuildContext {
  // ============================================
  // PUBLIC ROUTES (no authentication required)
  // ============================================

  /// Navigate to home screen
  void goToHome() => go(AppRoutes.home);

  /// Navigate to camera screen
  void goToCamera() => go(AppRoutes.camera);

  // ============================================
  // AUTH ROUTES
  // ============================================

  /// Navigate to login screen
  void goToLogin() => go(AppRoutes.login);

  /// Navigate to register screen
  void goToRegister() => go(AppRoutes.register);

  // ============================================
  // PROTECTED ROUTES (authentication required)
  // ============================================

  /// Navigate to results screen with plant data
  ///
  /// This uses `extra` to pass the Plant object to the route.
  /// The router will show an error screen if plant is null.
  void goToResults(Plant plant) => go(AppRoutes.results, extra: plant);

  /// Push results screen (keeps current screen in stack)
  void pushResults(Plant plant) => push(AppRoutes.results, extra: plant);

  /// Navigate to profile screen
  void goToProfile() => go(AppRoutes.profile);

  /// Navigate to garden screen
  void goToGarden() => go(AppRoutes.garden);

  /// Navigate to settings screen
  void goToSettings() => go(AppRoutes.settings);

  // ============================================
  // UTILITY METHODS
  // ============================================

  /// Pop current route
  ///
  /// Returns true if pop was successful, false if this is the last route
  bool popRoute() {
    if (canPop()) {
      pop();
      return true;
    }
    return false;
  }

  /// Pop until home screen
  ///
  /// Useful for "go to home" buttons that should clear the entire stack
  void popToHome() {
    while (canPop()) {
      pop();
    }
    goToHome();
  }

  /// Replace current route with login screen
  ///
  /// Useful when session expires and we need to force login
  void replaceWithLogin() => go(AppRoutes.login);

  /// Replace current route with home screen
  ///
  /// Useful after successful authentication
  void replaceWithHome() => go(AppRoutes.home);
}

/// Route parameter extensions for type-safe navigation
///
/// These extensions help extract and validate route parameters
extension RouteParameterExtensions on GoRouterState {
  /// Get query parameter by key
  ///
  /// Returns null if parameter doesn't exist
  String? getQueryParam(String key) => uri.queryParameters[key];

  /// Get query parameter with default value
  String getQueryParamOrDefault(String key, String defaultValue) =>
      uri.queryParameters[key] ?? defaultValue;

  /// Get required query parameter
  ///
  /// Throws ArgumentError if parameter doesn't exist
  String getRequiredQueryParam(String key) {
    final value = uri.queryParameters[key];
    if (value == null) {
      throw ArgumentError('Required query parameter "$key" is missing');
    }
    return value;
  }

  /// Get path parameter by key
  ///
  /// Returns null if parameter doesn't exist
  String? getPathParam(String key) => pathParameters[key];

  /// Get required path parameter
  ///
  /// Throws ArgumentError if parameter doesn't exist
  String getRequiredPathParam(String key) {
    final value = pathParameters[key];
    if (value == null) {
      throw ArgumentError('Required path parameter "$key" is missing');
    }
    return value;
  }

  /// Safely cast extra data to expected type
  ///
  /// Returns null if extra is null or wrong type
  T? getExtra<T>() {
    final extraData = extra;
    if (extraData is T) {
      return extraData;
    }
    return null;
  }

  /// Get required extra data
  ///
  /// Throws ArgumentError if extra is null or wrong type
  T getRequiredExtra<T>() {
    final extraData = getExtra<T>();
    if (extraData == null) {
      throw ArgumentError(
        'Required extra data of type $T is missing or has wrong type',
      );
    }
    return extraData;
  }
}

/// Deep link helpers for constructing URIs
///
/// These helpers make it easier to construct deep links for push notifications,
/// email links, etc.
abstract class DeepLinks {
  /// Base URI scheme for the app
  static const scheme = 'plantcommunity';

  /// Build URI for home screen
  static Uri home() => Uri(scheme: scheme, path: AppRoutes.home);

  /// Build URI for plant results
  ///
  /// Note: Deep links can't pass complex objects, so we use plant ID
  static Uri results(String plantId) =>
      Uri(scheme: scheme, path: AppRoutes.results, queryParameters: {
        'id': plantId,
      });

  /// Build URI for profile screen
  static Uri profile() => Uri(scheme: scheme, path: AppRoutes.profile);

  /// Build URI for garden screen
  static Uri garden() => Uri(scheme: scheme, path: AppRoutes.garden);

  /// Build URI for specific garden bed
  static Uri gardenBed(String bedId) =>
      Uri(scheme: scheme, path: AppRoutes.garden, queryParameters: {
        'bed_id': bedId,
      });
}
