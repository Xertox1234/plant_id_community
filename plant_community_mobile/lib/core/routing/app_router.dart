import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../core/theme/theme_preview_screen.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/home/home_page.dart';
import '../../features/camera/camera_screen.dart';
import '../../features/results/results_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/settings/settings_screen.dart';
import '../../features/care/care_screen.dart';
import '../../features/forum/forum_screen.dart';
import '../../features/collection/collection_screen.dart';
import '../../models/plant.dart';
import '../../services/auth_service.dart';
import 'error_screen.dart';
import 'placeholder_screen.dart';

part 'app_router.g.dart';

/// App route paths
abstract class AppRoutes {
  static const splash = '/';
  static const home = '/home';
  static const camera = '/camera';
  static const results = '/results';
  static const settings = '/settings';
  // Auth routes (screens not yet implemented)
  static const login = '/login';
  static const register = '/register';
  // Protected routes (screens not yet implemented)
  static const profile = '/profile';
  static const garden = '/garden';
  // Phase 2 feature routes
  static const care = '/care';
  static const forum = '/forum';
  static const collection = '/collection';
}

/// Router provider for the app
@riverpod
GoRouter appRouter(Ref ref) {
  // Re-run redirects when auth status flips without rebuilding the whole router.
  // Watching the auth provider here would recreate GoRouter on every auth change
  // and discard navigation state; refreshListenable keeps the instance stable.
  final authChanged = ValueNotifier<int>(0);
  ref.listen(
    authServiceProvider.select((state) => state.isAuthenticated),
    (_, _) => authChanged.value++,
  );
  ref.onDispose(authChanged.dispose);

  // Protected routes that require authentication
  const protectedRoutes = {AppRoutes.profile, AppRoutes.garden};
  // Auth routes that authenticated users should not see
  const authOnlyRoutes = {AppRoutes.login, AppRoutes.register};

  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: kDebugMode,
    refreshListenable: authChanged,
    redirect: (context, state) {
      final isAuthenticated = ref.read(authServiceProvider).isAuthenticated;
      final location = state.uri.path;

      // Redirect unauthenticated users away from protected routes
      if (!isAuthenticated && protectedRoutes.contains(location)) {
        return AppRoutes.login;
      }

      // Redirect authenticated users away from login/register
      if (isAuthenticated && authOnlyRoutes.contains(location)) {
        return AppRoutes.home;
      }

      return null; // No redirect
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        name: 'splash',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const SplashScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.home,
        name: 'home',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const HomePage(),
        ),
      ),
      GoRoute(
        path: AppRoutes.camera,
        name: 'camera',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const CameraScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.results,
        name: 'results',
        pageBuilder: (context, state) {
          final plant = state.extra as Plant?;
          if (plant == null) {
            // If no plant data, show error
            return _buildPageWithTransition(
              context: context,
              state: state,
              child: ErrorScreen(error: Exception('No plant data provided')),
            );
          }
          return _buildPageWithTransition(
            context: context,
            state: state,
            child: ResultsScreen(plant: plant),
          );
        },
      ),
      GoRoute(
        path: AppRoutes.profile,
        name: 'profile',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const ProfileScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.settings,
        name: 'settings',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const SettingsScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.login,
        name: 'login',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const PlaceholderScreen(title: 'Login'),
        ),
      ),
      GoRoute(
        path: AppRoutes.register,
        name: 'register',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const PlaceholderScreen(title: 'Register'),
        ),
      ),
      GoRoute(
        path: AppRoutes.garden,
        name: 'garden',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const PlaceholderScreen(title: 'Garden'),
        ),
      ),
      GoRoute(
        path: AppRoutes.care,
        name: 'care',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const CareScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.forum,
        name: 'forum',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const ForumScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.collection,
        name: 'collection',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const CollectionScreen(),
        ),
      ),
      if (kDebugMode)
        GoRoute(
          path: ThemePreviewScreen.routePath,
          builder: (context, state) => const ThemePreviewScreen(),
        ),
    ],
    errorBuilder: (context, state) => ErrorScreen(error: state.error),
  );
}

/// Build page with fade transition
CustomTransitionPage _buildPageWithTransition({
  required BuildContext context,
  required GoRouterState state,
  required Widget child,
}) {
  return CustomTransitionPage(
    key: state.pageKey,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(opacity: animation, child: child);
    },
  );
}
