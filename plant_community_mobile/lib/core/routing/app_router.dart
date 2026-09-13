import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../core/theme/theme_preview_screen.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/home/home_page.dart';
import '../../features/auth/login_screen.dart';
import '../../features/auth/register_screen.dart';
import '../../features/camera/camera_screen.dart';
import '../../features/results/results_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/settings/settings_screen.dart';
import '../../features/care/care_screen.dart';
import '../../features/forum/forum_screen.dart';
import '../../features/forum/screens/forum_bookmarks_screen.dart';
import '../../features/forum/screens/forum_topics_screen.dart';
import '../../features/forum/screens/forum_thread_screen.dart';
import '../../features/forum/screens/forum_composer_screen.dart';
import '../../features/forum/screens/forum_conversation_screen.dart';
import '../../features/forum/screens/forum_conversations_screen.dart';
import '../../features/forum/screens/forum_new_group_screen.dart';
import '../../features/forum/screens/forum_notifications_screen.dart';
import '../../features/forum/screens/forum_search_screen.dart';
import '../../features/forum/screens/forum_user_profile_screen.dart';
import '../../features/collection/collection_screen.dart';

import '../../models/plant.dart';
import '../../services/auth_service.dart';
import 'error_screen.dart';
import 'main_shell.dart';
import 'placeholder_screen.dart';

part 'app_router.g.dart';

/// App route paths
abstract class AppRoutes {
  static const splash = '/';
  static const home = '/home';
  static const camera = '/camera';
  static const results = '/results';
  static const settings = '/settings';
  // Auth routes. Reachable from the Profile tab's signed-out state; the
  // redirect below bounces an already-authenticated user off both.
  static const login = '/login';
  static const register = '/register';
  // `profile` has a screen and is a shell branch root. `garden` does not:
  // it is still a PlaceholderScreen for the unbuilt garden-calendar
  // feature, and is deliberately not a shell destination (todo 384).
  static const profile = '/profile';
  static const garden = '/garden';
  // Phase 2 feature routes
  static const care = '/care';
  static const forum = '/forum';
  // Auth-only: the notifications feed is the caller's own inbox and the
  // backend 401s an anonymous request, which the screen could only render as
  // a Retry dead-end (audit 2026-09-04 M6).
  static const forumNotifications = '/forum/notifications';
  // Auth-only for the same reason: the DM inbox and every thread under it
  // are the caller's own private messages (todo 339).
  static const forumMessages = '/forum/messages';
  // Auth-only, same reason: group DM threads live under their own prefix so
  // `/forum/messages/:username` can never swallow `new` or a numeric id as
  // a member name (todo 350).
  static const forumGroups = '/forum/groups';
  static const forumNewGroup = '/forum/groups/new';
  // Auth-only: the bookmarks list is the caller's own (todo 341).
  static const forumBookmarks = '/forum/bookmarks';
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
  // NB: AppRoutes.profile is deliberately ABSENT. It is a shell branch root,
  // and redirecting out of a branch root desyncs StatefulShellRoute's branch
  // index. ProfileScreen gates itself and renders a sign-in CTA when signed
  // out -- the same shape CollectionScreen already uses (todo 384).
  const protectedRoutes = {
    AppRoutes.garden,
    AppRoutes.forumNotifications,
    AppRoutes.forumMessages,
    AppRoutes.forumBookmarks,
  };
  // Parameterised protected routes (`/forum/messages/:username`) can't be
  // matched by the exact-path set above; guard them by prefix.
  const protectedPrefixes = {AppRoutes.forumMessages, AppRoutes.forumGroups};
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
      final isProtected =
          protectedRoutes.contains(location) ||
          protectedPrefixes.any((p) => location.startsWith('$p/'));
      if (!isAuthenticated && isProtected) {
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
      // Primary navigation shell. Branch ORDER is index-aligned with
      // MainShell.destinations -- goBranch() addresses branches positionally,
      // so reordering one without the other silently swaps two tabs.
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            MainShell(navigationShell: navigationShell),
        branches: [
          // 0 Home -- /care hangs off the Home feature grid, so it keeps the bar.
          StatefulShellBranch(
            routes: [
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
                path: AppRoutes.care,
                name: 'care',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const CareScreen(),
                ),
              ),
            ],
          ),
          // 1 My Plants
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.collection,
                name: 'collection',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const CollectionScreen(),
                ),
              ),
            ],
          ),
          // 2 Forum -- the whole feature stays in one branch so its own internal
          // navigation (boards, threads, DMs) keeps the nav bar and its own back
          // stack. `forumNewGroup` must stay BEFORE `forumGroupConversation`.
          StatefulShellBranch(
            routes: [
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
                path: '/forum/boards/:slug',
                name: 'forumBoard',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: ForumTopicsScreen(
                    boardSlug: state.pathParameters['slug'] ?? '',
                    boardTitle: state.extra is String
                        ? state.extra as String
                        : null,
                  ),
                ),
              ),
              GoRoute(
                path: '/forum/topics/:id',
                name: 'forumTopic',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: ForumThreadScreen(
                    topicId:
                        int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
                    initialTitle: state.extra is String
                        ? state.extra as String
                        : null,
                    highlightPostId: int.tryParse(
                      state.uri.queryParameters['postId'] ?? '',
                    ),
                  ),
                ),
              ),
              GoRoute(
                path: '/forum/compose',
                name: 'forumCompose',
                pageBuilder: (context, state) {
                  final args = state.extra;
                  return _buildPageWithTransition(
                    context: context,
                    state: state,
                    child: args is ForumComposeArgs
                        ? ForumComposerScreen(args: args)
                        : ErrorScreen(
                            error: Exception('Missing composer arguments'),
                          ),
                  );
                },
              ),
              GoRoute(
                path: AppRoutes.forumNotifications,
                name: 'forumNotifications',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const ForumNotificationsScreen(),
                ),
              ),
              GoRoute(
                path: AppRoutes.forumMessages,
                name: 'forumMessages',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const ForumConversationsScreen(),
                ),
              ),
              GoRoute(
                path: AppRoutes.forumBookmarks,
                name: 'forumBookmarks',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const ForumBookmarksScreen(),
                ),
              ),
              GoRoute(
                path: '${AppRoutes.forumMessages}/:username',
                name: 'forumConversation',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: ForumConversationScreen(
                    username: state.pathParameters['username'] ?? '',
                  ),
                ),
              ),
              // Declared BEFORE the `:id` route: go_router takes the first match, and
              // `:id` would otherwise capture the literal `new`.
              GoRoute(
                path: AppRoutes.forumNewGroup,
                name: 'forumNewGroup',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const ForumNewGroupScreen(),
                ),
              ),
              GoRoute(
                path: '${AppRoutes.forumGroups}/:id',
                name: 'forumGroupConversation',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: ForumConversationScreen(
                    conversationId:
                        int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
                  ),
                ),
              ),
              GoRoute(
                path: '/forum/search',
                name: 'forumSearch',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const ForumSearchScreen(),
                ),
              ),
              // Deliberately NOT in protectedRoutes: the backend's PublicProfileView
              // is AllowAny, so an unauthenticated viewer can see a public profile.
              GoRoute(
                path: '/forum/users/:username',
                name: 'forumUserProfile',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: ForumUserProfileScreen(
                    username: state.pathParameters['username'] ?? '',
                  ),
                ),
              ),
            ],
          ),
          // 3 Profile
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.profile,
                name: 'profile',
                pageBuilder: (context, state) => _buildPageWithTransition(
                  context: context,
                  state: state,
                  child: const ProfileScreen(),
                ),
              ),
            ],
          ),
        ],
      ),
      // OUTSIDE the shell, on the root navigator: these cover the nav bar
      // entirely. Capture and auth are full-screen tasks, and popping returns
      // to whichever tab the user came from with its stack intact.
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
          child: const LoginScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.register,
        name: 'register',
        pageBuilder: (context, state) => _buildPageWithTransition(
          context: context,
          state: state,
          child: const RegisterScreen(),
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
      if (kDebugMode)
        GoRoute(
          path: ThemePreviewScreen.routePath,
          builder: (context, state) => const ThemePreviewScreen(),
        ),
    ],
    errorBuilder: (context, state) => ErrorScreen(error: state.error),
  );
}

/// Build page with fade transition.
///
/// The fade length here is coupled to `test/routing/navigation_shell_test.dart`,
/// which pumps past it (`_settle`) to see the shell mount. Lengthen the
/// transition beyond that and those tests start reporting "no NavigationBar"
/// when the truth is "not yet" -- bump `_settle` in the same change.
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
