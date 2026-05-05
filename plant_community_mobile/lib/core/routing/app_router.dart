import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../config/theme_provider.dart';
import '../../core/constants/app_spacing.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/home/home_page.dart';
import '../../features/camera/camera_screen.dart';
import '../../features/results/results_screen.dart';
import '../../models/plant.dart';
import '../../services/auth_service.dart';

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
}

/// Router provider for the app
@riverpod
GoRouter appRouter(Ref ref) {
  final authState = ref.watch(authServiceProvider);

  // Protected routes that require authentication
  const protectedRoutes = {AppRoutes.profile, AppRoutes.garden};
  // Auth routes that authenticated users should not see
  const authOnlyRoutes = {AppRoutes.login, AppRoutes.register};

  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: kDebugMode,
    redirect: (context, state) {
      final isAuthenticated = authState.isAuthenticated;
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
          child: const _PlaceholderScreen(title: 'Login'),
        ),
      ),
      GoRoute(
        path: AppRoutes.register,
        name: 'register',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const _PlaceholderScreen(title: 'Register'),
        ),
      ),
      GoRoute(
        path: AppRoutes.profile,
        name: 'profile',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const _PlaceholderScreen(title: 'Profile'),
        ),
      ),
      GoRoute(
        path: AppRoutes.garden,
        name: 'garden',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const _PlaceholderScreen(title: 'Garden'),
        ),
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

/// Temporary placeholder screen for routes not yet implemented.
class _PlaceholderScreen extends StatelessWidget {
  const _PlaceholderScreen({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(child: Text('$title screen coming soon')),
    );
  }
}

/// Settings screen with core app preferences.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final themeNotifier = ref.read(themeModeProvider.notifier);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            Text('Appearance', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: AppSpacing.md),
            SegmentedButton<ThemeMode>(
              segments: const [
                ButtonSegment(
                  value: ThemeMode.system,
                  icon: Icon(Icons.brightness_auto),
                  label: Text('System'),
                ),
                ButtonSegment(
                  value: ThemeMode.light,
                  icon: Icon(Icons.light_mode),
                  label: Text('Light'),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  icon: Icon(Icons.dark_mode),
                  label: Text('Dark'),
                ),
              ],
              selected: {themeMode},
              onSelectionChanged: (selection) {
                switch (selection.first) {
                  case ThemeMode.light:
                    themeNotifier.setLight();
                  case ThemeMode.dark:
                    themeNotifier.setDark();
                  case ThemeMode.system:
                    themeNotifier.setSystem();
                }
              },
            ),
            const SizedBox(height: AppSpacing.xl),
            Text('About', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: AppSpacing.md),
            const ListTile(
              leading: Icon(Icons.local_florist),
              title: Text('Plant Community'),
              subtitle: Text(
                'Plant identification, care, and community features',
              ),
            ),
            ListTile(
              leading: const Icon(Icons.api),
              title: const Text('Backend API'),
              subtitle: const Text(
                'Configured with API_BASE_URL at build time',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Error screen
class ErrorScreen extends StatelessWidget {
  final Exception? error;

  const ErrorScreen({super.key, this.error});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            const Text('Oops! Something went wrong'),
            if (error != null) ...[
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
